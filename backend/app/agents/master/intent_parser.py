"""自然语言意图识别（IntentParser）.

设计原则：
1. **规则优先**：中文学习场景的意图与参数高度模式化，规则解析确定性强、
   不消耗额度、可单测；解析结果可解释（source="rule"）。
2. **LLM 兜底**：仅当规则完全无法识别意图、且 LLMService 可用时才调用一次
   结构化输出；失败静默降级（不阻塞主流程，也不编造参数）。
3. **不擅自假设**：用户没说的关键参数（考试日期 / 每日时长）记为
   missing_params，由主控 Agent 追问；允许使用默认值的地方（如题量）
   写入 assumptions 如实告知。

只读：除查询知识点/学科名称外不访问数据库。
"""
import re
from datetime import date, timedelta
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.master.schemas import (
    ALL_INTENTS,
    INTENT_ANALYSIS,
    INTENT_PLAN,
    INTENT_QUESTIONS,
    INTENT_RETRIEVAL,
    INTENT_VALIDATION,
    TARGET_ANALYSIS,
    TARGET_PLAN,
    TARGET_QUESTION_SET,
    MasterIntent,
)
from app.core.logging import logger
from app.models import KnowledgePoint
from app.services.llm_service import llm_service
from app.services.question_service import normalize_question_type


class _LLMIntent(BaseModel):
    """LLM 兜底解析的结构化输出."""

    intents: list[str] = []
    subject: Optional[str] = None
    knowledge_point: Optional[str] = None
    days: Optional[int] = None
    daily_minutes: Optional[int] = None
    question_count: Optional[int] = None
    question_types: list[str] = []
    difficulty: Optional[str] = None
    goal: str = ""


class IntentParser:
    """把用户自然语言解析为 MasterIntent（意图 + 参数）."""

    # ---- 关键词表（命中即算，可叠加多意图）----
    PLAN_WORDS = (
        "计划", "规划", "复习安排", "安排复习", "备考", "日程", "复习方案", "学习安排",
    )
    ANALYSIS_WORDS = (
        "学情", "学习情况", "学习分析", "学习报告", "学习数据", "最近学得",
        "分析一下我的", "我的学习", "学习状态", "学习效果",
    )
    RETRIEVAL_WORDS = (
        "解释", "讲解", "介绍", "什么是", "什么叫", "定义", "概念", "检索",
        "知识点是", "讲讲", "说说",
    )
    QUESTION_WORDS = (
        "出题", "练习题", "刷题", "做题", "测验", "测试题", "练习", "习题", "题目",
        "单选题", "多选题", "判断题", "简答题", "选择题", "道题",
    )
    VALIDATION_WORDS = ("检查", "校验", "验证", "核对", "是否合理", "有没有问题")
    CREATION_WORDS = (
        "制定", "生成", "安排", "规划", "帮我做", "做一份", "定一个", "出题", "来一份",
    )
    WEAK_WORDS = ("薄弱", "弱项", "短板", "不擅长", "易错", "掌握不好", "较差")

    TYPE_WORDS = (
        ("single_choice", ("单选", "单项选择", "single_choice")),
        ("multiple_choice", ("多选", "多项选择", "multiple_choice")),
        ("true_false", ("判断", "true_false")),
        ("short_answer", ("简答", "问答", "short_answer")),
    )

    DIFFICULTY_WORDS = (
        ("偏难", "hard"), ("困难", "hard"), ("提高", "hard"), ("中等", "medium"),
        ("普通", "medium"), ("基础", "easy"), ("简单", "easy"), ("容易", "easy"),
    )

    # 与专业 Agent 保持一致的边界
    MAX_QUESTION_COUNT = 20
    DEFAULT_QUESTION_COUNT = 5
    MIN_DAILY_MINUTES = 15
    MAX_DAILY_MINUTES = 1440

    def __init__(self, use_llm: bool = True) -> None:
        # 仅在规则完全识别不出意图时才会用到 LLM
        self.use_llm = use_llm

    # ==================== 入口 ====================

    def parse(
        self, message: str, db: Optional[Session] = None, user_id: Optional[int] = None
    ) -> MasterIntent:
        text = (message or "").strip()
        intent = MasterIntent(message=text, goal=text)

        intents, check_targets, weak_driven = self._detect_intents(text)
        intent.intents = intents
        intent.check_targets = check_targets
        intent.weak_points_driven = weak_driven

        # ---- 把用户口语映射到数据库中的真实学科/知识点 ----
        kp_name, kp_subject = self._match_knowledge_point(db, text)
        intent.knowledge_point = kp_name
        intent.subject = kp_subject or self._match_subject(db, text)

        # ---- 参数抽取 ----
        intent.exam_date = self._extract_exam_date(text)
        intent.days = self._extract_days(text)
        intent.daily_minutes = self._extract_daily_minutes(text)
        intent.question_types = self._extract_question_types(text)
        intent.difficulty = self._extract_difficulty(text)
        topic = self._extract_topic(text)
        intent.query = topic or kp_name or intent.subject or text

        # 用户给的是"还有 N 天"，换算成考试日期（两者都没给才算缺失）
        if intent.exam_date is None and intent.days:
            intent.exam_date = date.today() + timedelta(days=intent.days)

        # ---- 题量：未指定则用默认值，并如实告知 ----
        if INTENT_QUESTIONS in intents:
            raw_count = self._extract_question_count(text)
            if raw_count is None:
                intent.question_count = self.DEFAULT_QUESTION_COUNT
                intent.assumptions.append(
                    f"未指定题目数量，按默认 {self.DEFAULT_QUESTION_COUNT} 道生成"
                )
            else:
                intent.question_count = min(raw_count, self.MAX_QUESTION_COUNT)
                if raw_count > self.MAX_QUESTION_COUNT:
                    intent.assumptions.append(
                        f"题目数量超过单次上限，按 {self.MAX_QUESTION_COUNT} 道处理"
                    )
            if not intent.question_types:
                intent.assumptions.append("未指定题型，按单选/多选/判断/简答混合生成")
            if intent.difficulty is None:
                intent.assumptions.append("未指定难度，按学情掌握度自动选择")

        # ---- 必要参数缺失 → 追问，不擅自编造 ----
        intent.missing_params = self._missing_params(intent)

        # ---- 规则完全无法识别时用 LLM 兜底 ----
        if not intent.intents:
            parsed = self._llm_parse(text) if self.use_llm else None
            if parsed is not None:
                self._merge_llm_intent(intent, parsed)
            if not intent.intents:
                # 仍无法识别：按"知识点问答"处理（检索 Agent 会如实返回未命中）
                intent.intents = [INTENT_RETRIEVAL]
                intent.source = "fallback"
                intent.query = intent.query or text

        self._log(text, intent)
        return intent

    def apply_overrides(
        self, intent: MasterIntent, overrides: Optional[dict]
    ) -> MasterIntent:
        """把调用方显式传入的参数合并进解析结果（接口层可选，优先级最高）.

        只补参数、不改意图：用于前端表单/接口直调时精确指定考试日期、每日时长、
        题量等信息，避免为了参数再拼一句自然语言。
        """
        data = overrides or {}

        raw_exam = data.get("exam_date")
        if raw_exam:
            try:
                intent.exam_date = date.fromisoformat(str(raw_exam)[:10])
            except ValueError:
                parsed = self._extract_exam_date(str(raw_exam))
                if parsed:
                    intent.exam_date = parsed

        raw_days = data.get("days")
        if raw_days is not None and intent.exam_date is None:
            try:
                intent.days = int(raw_days)
                intent.exam_date = date.today() + timedelta(days=intent.days)
            except (TypeError, ValueError):
                pass

        raw_daily = data.get("daily_minutes")
        if raw_daily is not None:
            try:
                value = int(raw_daily)
                if self.MIN_DAILY_MINUTES <= value <= self.MAX_DAILY_MINUTES:
                    intent.daily_minutes = value
            except (TypeError, ValueError):
                pass

        raw_count = data.get("question_count", data.get("count"))
        if raw_count is not None:
            try:
                intent.question_count = min(
                    max(1, int(raw_count)), self.MAX_QUESTION_COUNT
                )
            except (TypeError, ValueError):
                pass

        raw_types = data.get("question_types")
        if raw_types:
            values = (
                raw_types if isinstance(raw_types, (list, tuple, set)) else [raw_types]
            )
            types = [
                qtype for qtype in (normalize_question_type(v) for v in values) if qtype
            ]
            if types:
                intent.question_types = types

        raw_difficulty = data.get("difficulty")
        if raw_difficulty:
            level = str(raw_difficulty).strip().lower()
            if level in ("easy", "medium", "hard"):
                intent.difficulty = level

        for key in ("subject", "knowledge_point"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                setattr(intent, key, value.strip())
        if intent.knowledge_point and not intent.query:
            intent.query = intent.knowledge_point

        intent.missing_params = self._missing_params(intent)
        return intent

    # ==================== 意图判定 ====================

    def _detect_intents(self, text: str) -> tuple[list[str], list[str], bool]:
        weak_driven = any(w in text for w in self.WEAK_WORDS)
        creation = any(w in text for w in self.CREATION_WORDS)
        wants_validation = any(w in text for w in self.VALIDATION_WORDS)
        # "N 道…题" 是本场景最稳定的信号，其次是题型/练习类关键词
        wants_questions = (
            bool(re.search(r"(?:生成|出|来|做)\s*\d*\s*(?:道|个)\s*题", text))
            or bool(re.search(r"\d+\s*道", text))
            or any(w in text for w in self.QUESTION_WORDS)
        )
        wants_plan = (
            any(w in text for w in self.PLAN_WORDS)
            or ("考试" in text and bool(re.search(r"\d+\s*[天周]", text)))
        )
        wants_analysis = any(w in text for w in self.ANALYSIS_WORDS)
        wants_retrieval = any(w in text for w in self.RETRIEVAL_WORDS)

        # 仅"检查已有结果"：没有创建类动词，也没有要求生成练习
        if wants_validation and not creation and not wants_questions:
            targets: list[str] = []
            if "计划" in text:
                targets.append(TARGET_PLAN)
            if "题" in text:
                targets.append(TARGET_QUESTION_SET)
            if not targets:
                targets = [TARGET_ANALYSIS] if wants_analysis else [TARGET_PLAN]
            return [INTENT_VALIDATION], targets, weak_driven

        intents: list[str] = []
        if wants_plan:
            intents.append(INTENT_PLAN)
        if wants_questions:
            intents.append(INTENT_QUESTIONS)
        if wants_analysis:
            intents.append(INTENT_ANALYSIS)
        if wants_retrieval:
            intents.append(INTENT_RETRIEVAL)
        if wants_validation and intents:
            intents.append(INTENT_VALIDATION)
        return [i for i in ALL_INTENTS if i in intents], [], weak_driven

    # ==================== 数据库辅助（只读）====================

    @staticmethod
    def _load_catalog(db: Optional[Session]) -> tuple[list[tuple[str, str]], list[str]]:
        """读取知识点名与学科列表（用于把用户口语映射到真实数据）."""
        if db is None:
            return [], []
        try:
            rows = db.query(KnowledgePoint.name, KnowledgePoint.subject).all()
        except Exception as exc:  # 数据库不可用时不影响意图解析
            logger.warning(f"[master] 读取知识点目录失败：{exc}")
            return [], []
        kps = [(str(name), str(subject)) for name, subject in rows if name]
        return kps, sorted({subject for _, subject in kps})

    @classmethod
    def _match_knowledge_point(
        cls, db: Optional[Session], text: str
    ) -> tuple[Optional[str], Optional[str]]:
        kps, _ = cls._load_catalog(db)
        # 长名优先，避免"关系"抢先命中"等价关系"
        for name, subject in sorted(kps, key=lambda item: -len(item[0])):
            if name and name in text:
                return name, subject
        return None, None

    @classmethod
    def _match_subject(cls, db: Optional[Session], text: str) -> Optional[str]:
        _, subjects = cls._load_catalog(db)
        for subject in sorted(subjects, key=len, reverse=True):
            if subject and subject in text:
                return subject
        return None

    # ==================== 参数抽取 ====================

    @staticmethod
    def _extract_days(text: str) -> Optional[int]:
        match = re.search(r"(\d+)\s*天", text)
        if match:
            return int(match.group(1))
        match = re.search(r"(\d+)\s*个?\s*(?:星期|周)", text)
        if match:
            return int(match.group(1)) * 7
        return None

    @staticmethod
    def _extract_exam_date(text: str) -> Optional[date]:
        match = re.search(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})", text)
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                return None
        match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", text)
        if match:
            today = date.today()
            try:
                candidate = date(today.year, int(match.group(1)), int(match.group(2)))
            except ValueError:
                return None
            return candidate if candidate >= today else candidate.replace(year=today.year + 1)
        return None

    @classmethod
    def _extract_daily_minutes(cls, text: str) -> Optional[int]:
        patterns = (
            r"(?:每天|每日)[^0-9]{0,10}(\d+(?:\.\d+)?)\s*(小时|个小时|h|H|分钟|min)",
            r"(\d+(?:\.\d+)?)\s*(小时|个小时|分钟)\s*(?:每天|每日|/天|一天)",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            value = float(match.group(1))
            unit = match.group(2)
            if "小时" in unit or unit in ("h", "H"):
                minutes = int(round(value * 60))
            else:
                minutes = int(value)
            if cls.MIN_DAILY_MINUTES <= minutes <= cls.MAX_DAILY_MINUTES:
                return minutes
            return None
        return None

    @staticmethod
    def _extract_question_count(text: str) -> Optional[int]:
        match = re.search(r"(\d+)\s*道", text)
        if not match:
            match = re.search(r"(?:生成|出|来|做)\s*(\d+)\s*(?:个|道)?", text)
        if not match:
            return None
        try:
            value = int(match.group(1))
        except (TypeError, ValueError):
            return None
        return value if value >= 1 else None

    @classmethod
    def _extract_question_types(cls, text: str) -> list[str]:
        found: list[str] = []
        for canonical, words in cls.TYPE_WORDS:
            if any(word in text for word in words) and canonical not in found:
                found.append(canonical)
        return found

    @classmethod
    def _extract_difficulty(cls, text: str) -> Optional[str]:
        if "不容易" in text or "不难" in text:
            text = text.replace("不容易", "").replace("不难", "")
        for word, level in cls.DIFFICULTY_WORDS:
            if word in text:
                return level
        lowered = text.lower()
        for level in ("easy", "medium", "hard"):
            if level in lowered:
                return level
        return None

    @staticmethod
    def _extract_topic(text: str) -> str:
        """抽取"要解释/检索的主题"，如"解释一下离散数学中的关系与闭包" → "关系与闭包"."""
        patterns = (
            r"[「《\"']([^」》\"']{2,40})[」》\"']",
            r"(?:中的|里的|关于|对于)\s*([^，。；;？?！!\n]{2,40})",
            r"(?:解释|讲解|介绍|讲讲|说说)(?:一下)?\s*([^，。；;？?！!\n]{2,40})",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                topic = match.group(1).strip()
                topic = re.sub(r"^(?:请问|帮我|请|一下|这个|那个)+", "", topic).strip()
                if topic:
                    return topic
        return ""

    @classmethod
    def _missing_params(cls, intent: MasterIntent) -> list[str]:
        if INTENT_PLAN not in intent.intents:
            return []
        missing: list[str] = []
        if intent.exam_date is None:
            missing.append("exam_date")
        if intent.daily_minutes is None:
            missing.append("daily_minutes")
        return missing

    # ==================== LLM 兜底 ====================

    def _llm_parse(self, text: str) -> Optional[_LLMIntent]:
        if not self.use_llm or not llm_service.available:
            return None
        prompt = (
            "你是学习助手的需求解析器。请从用户消息中识别其学习需求。\n"
            f"可用意图：{list(ALL_INTENTS)}\n"
            "参数说明：days=距离考试的剩余天数；daily_minutes=每天可用学习分钟数；"
            "question_types 只能取 single_choice/multiple_choice/true_false/short_answer；"
            "difficulty 只能取 easy/medium/hard。\n"
            "不要臆造用户未提供的数值，未提及的字段留空。\n"
            f"用户消息：{text}"
        )
        try:
            parsed = llm_service.structured_output(
                [{"role": "user", "content": prompt}], _LLMIntent, temperature=0.0
            )
        except Exception as exc:  # 兜底失败不影响主流程
            logger.warning(f"[master] LLM 意图解析失败：{exc}")
            return None
        return parsed

    @staticmethod
    def _merge_llm_intent(intent: MasterIntent, parsed: _LLMIntent) -> None:
        """把 LLM 结果并入规则结果：只补空缺，不覆盖已抽到的真实数据."""
        intent.source = "llm"
        intents = [i for i in ALL_INTENTS if i in set(parsed.intents)]
        if intents:
            intent.intents = intents
        if intent.daily_minutes is None and parsed.daily_minutes:
            try:
                value = int(parsed.daily_minutes)
                if IntentParser.MIN_DAILY_MINUTES <= value <= IntentParser.MAX_DAILY_MINUTES:
                    intent.daily_minutes = value
            except (TypeError, ValueError):
                pass
        if intent.days is None and parsed.days:
            try:
                intent.days = int(parsed.days)
            except (TypeError, ValueError):
                pass
        if intent.exam_date is None and intent.days:
            intent.exam_date = date.today() + timedelta(days=intent.days)
        if intent.question_count is None and parsed.question_count:
            try:
                intent.question_count = min(
                    max(1, int(parsed.question_count)), IntentParser.MAX_QUESTION_COUNT
                )
            except (TypeError, ValueError):
                pass
        if not intent.question_types:
            intent.question_types = [
                qtype for qtype in (
                    normalize_question_type(raw) for raw in parsed.question_types
                ) if qtype
            ]
        if intent.difficulty is None and parsed.difficulty:
            level = str(parsed.difficulty).strip().lower()
            if level in ("easy", "medium", "hard"):
                intent.difficulty = level
        if parsed.subject and not intent.subject:
            intent.subject = parsed.subject
        if parsed.knowledge_point and not intent.knowledge_point:
            intent.knowledge_point = parsed.knowledge_point
        if parsed.goal:
            intent.goal = parsed.goal
        intent.missing_params = IntentParser._missing_params(intent)

    # ==================== 日志 ====================

    @staticmethod
    def _log(text: str, intent: MasterIntent) -> None:
        logger.info(
            f"[master] 意图解析 source={intent.source} "
            f"intents={intent.intents} subject={intent.subject} "
            f"kp={intent.knowledge_point} days={intent.days} "
            f"daily={intent.daily_minutes} count={intent.question_count} "
            f"missing={intent.missing_params} | {text[:40]}"
        )
