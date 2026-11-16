"""结果验证 Agent（Result Validation Agent）.

职责：对上游 Agent 的输出做**双层可解释校验**，为 Self-Loop / 主控 Agent 提供
"是否可用 + 哪里不对 + 怎么改" 的确定性结论。

- 程序化校验（默认，确定性、不消耗额度）：
  - question_set：数量达标、success/partial/failed 与数量自洽、题干/解析/答案完整性、
    题型与选项合法性、去重、难度合法性、**落库明细逐题一致**；
  - study_plan：必填字段、考试日期合法性、任务非空与任务内容、每日时长按天汇总不超限、
    任务日期范围、落库与归属一致性、计划字段与数据库一致；
  - learning_analysis：结构完整、数值非负、数据不足时是否如实标注、
    **报告结论是否有真实数据支撑**（与数据库答题/记录/任务交叉校验）；
  - knowledge_retrieval：未命中是否如实返回、命中条数与条目自洽、
    **知识来源是否可追溯**（context/definition）、相关度是否合法；
  - generic：按调用方给出的 required_fields 做通用字段校验。
- LLM 辅助校验（可选，opt-in）：对结果与需求的契合度打分，仅作补充，不替代规则层。

设计约束：
- **只读**：只做查询比对，绝不修改或写入数据库；
- **不抛异常**（身份校验除外）：payload 缺失/类型错误都返回 passed=False 的诊断结果；
- 校验失败必须给出可执行的修正建议，供上游 Agent 重新生成。
"""
import json
import re
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.agents.core.base import AgentContext, BaseAgent
from app.agents.core.schemas import AgentTask
from app.models import Answer, LearningRecord, Question, StudyPlan, StudyTask
from app.models.question import DIFFICULTIES, QUESTION_TYPES
from app.services.llm_service import llm_service


class _LLMReview(BaseModel):
    """LLM 契合度评分的结构化输出."""

    score: float
    feedback: str = ""


class ResultValidationAgent(BaseAgent):
    """结果验证专业 Agent（只读、规则优先）."""

    name = "result_validation"
    description = "程序化校验上游结果的数量/字段/一致性，可选 LLM 辅助评分"
    task_type = "result_validation"
    max_retries = 0        # 只读校验：重试无意义
    timeout_s = 60.0

    SUPPORTED_TARGETS = (
        "question_set", "study_plan", "learning_analysis",
        "knowledge_retrieval", "generic",
    )
    # 上游 Agent 名 → 校验目标类型
    TARGET_BY_AGENT = {
        "question_generation": "question_set",
        "study_planning": "study_plan",
        "learning_analysis": "learning_analysis",
        "knowledge_retrieval": "knowledge_retrieval",
    }
    # 输入别名 → 标准目标类型
    TARGET_ALIASES = {
        "questions": "question_set", "question": "question_set",
        "quiz": "question_set", "practice": "question_set",
        "plan": "study_plan", "study_task": "study_plan",
        "report": "learning_analysis", "learning_report": "learning_analysis",
        "retrieval": "knowledge_retrieval", "knowledge": "knowledge_retrieval",
    }

    CHOICE_TYPES = ("single_choice", "multiple_choice")
    MIN_CONTENT_CHARS = 5
    MIN_TASK_MINUTES = 15
    LLM_THRESHOLD = 0.6
    MAX_LLM_CHARS = 2000

    # 失败项 → 修正建议（按检查名关键词匹配）
    SUGGESTIONS = (
        ("数量", "数量未达标：请补齐到期望数量后再提交校验。"),
        ("题干", "补齐每道题的题干（至少 5 个字符）。"),
        ("解析", "为每道题补充 explanation 解析。"),
        ("题型", "题型只能是 single_choice/multiple_choice/true_false/short_answer。"),
        ("选项", "选择题需提供 2~5 个非空选项，答案字母须落在选项范围内。"),
        ("答案", "答案需按题型规范：单选 1 个字母、多选至少 2 个字母、判断为「正确/错误」。"),
        ("重复", "删除归一化后重复的题干，补充新题。"),
        ("难度", "难度只能是 easy/medium/hard。"),
        ("必填", "按约定字段名补齐缺失字段。"),
        ("任务", "学习计划至少包含 1 个任务，且任务时长与日期需合法。"),
        ("时长", "按天压缩任务时长，确保不超过每日可用上限。"),
        ("落库", "确认数据写入成功后再提交校验。"),
        ("归属", "计划归属用户不一致，请检查 user_id。"),
        ("标注", "数据不足时应如实返回 sufficient=False 并列出缺失项。"),
        ("编造", "数据不足时不得输出报告：report 置空并如实列出 missing。"),
        ("超出真实数据", "报告统计数字不得大于数据库真实数量，请按真实数据重新统计。"),
        ("真实数据依据", "报告缺少真实数据支撑，请基于真实答题/学习记录重新生成。"),
        ("与数据一致", "统计口径与数据库不一致，请以数据库真实计数为准。"),
        ("结构", "按约定结构补齐结果字段。"),
        ("命中", "检索命中时应返回非空 results，未命中时 found=False。"),
        ("契合", "结果与需求契合度不足，请针对需求重新生成。"),
    )

    def __init__(self, logger: Optional[Any] = None, use_llm: bool = False) -> None:
        super().__init__(logger)
        # LLM 辅助校验默认关闭：保证测试与主流程确定性、不消耗额度
        self.use_llm = use_llm

    # ==================== 统一执行入口 ====================

    async def execute(self, task: AgentTask, context: AgentContext) -> dict:
        if task.user_id != context.user_id:
            raise ValueError("任务用户与当前登录用户不一致，已拒绝执行")

        data = task.input_data or {}
        payload = self._resolve_payload(data, context)
        target = self._resolve_target(data, payload)
        db: Optional[Session] = context.db

        if payload is None or (isinstance(payload, (dict, list, str)) and not payload):
            self.logger.log(
                task.task_id, self.name, "待校验结果为空", level="warning"
            )
            checks = [self._check(
                "结果存在性", False,
                "未从 payload / context.shared 取得待校验结果",
            )]
            return self._assemble(target, checks, db_checked=False)

        handler = {
            "question_set": self._check_question_set,
            "study_plan": self._check_study_plan,
            "learning_analysis": self._check_learning_analysis,
            "knowledge_retrieval": self._check_knowledge_retrieval,
            "generic": self._check_generic,
        }.get(target, self._check_generic)

        checks, db_checked = handler(payload, data, db, task.user_id)

        # ---- LLM 辅助（可选）----
        llm_score: Optional[float] = None
        llm_feedback = ""
        if self._llm_enabled(data):
            review = self._llm_review(target, payload, self._requirement(data))
            if review is not None:
                llm_score, llm_feedback = review
                checks.append(self._check(
                    "需求契合度（LLM）",
                    llm_score >= self.LLM_THRESHOLD,
                    f"评分 {llm_score:.2f}（阈值 {self.LLM_THRESHOLD}）"
                    + (f"：{llm_feedback}" if llm_feedback else ""),
                    critical=False,
                ))

        self.logger.log(
            task.task_id, self.name,
            f"校验完成 target={target} db_checked={db_checked}",
        )
        return self._assemble(
            target, checks,
            db_checked=db_checked,
            llm_score=llm_score,
            llm_feedback=llm_feedback,
        )

    # ==================== 输入解析 ====================

    @staticmethod
    def _resolve_payload(data: dict, context: AgentContext) -> Any:
        """取得待校验结果：显式 payload 优先，其次 shared / result."""
        if "payload" in data:
            return data.get("payload")
        key = data.get("shared_key") or data.get("target_agent")
        if key:
            shared = context.shared.get(str(key))
            if shared is not None:
                return shared
        if "result" in data:
            return data.get("result")
        return None

    def _resolve_target(self, data: dict, payload: Any) -> str:
        raw = str(data.get("target") or data.get("target_type") or "").strip().lower()
        raw = self.TARGET_ALIASES.get(raw, raw)
        if raw in self.SUPPORTED_TARGETS:
            return raw

        if isinstance(payload, dict):
            agent = str(payload.get("agent") or "").strip()
            if agent in self.TARGET_BY_AGENT:
                return self.TARGET_BY_AGENT[agent]
            if "plan_id" in payload or "daily_summary" in payload:
                return "study_plan"
            if "question_ids" in payload or "questions" in payload:
                return "question_set"
            if "report" in payload and "sufficient" in payload:
                return "learning_analysis"
            if "results" in payload and "found" in payload:
                return "knowledge_retrieval"
        if isinstance(payload, list):
            return "question_set"
        return "generic"

    def _llm_enabled(self, data: dict) -> bool:
        return bool(data.get("use_llm", self.use_llm))

    @staticmethod
    def _requirement(data: dict) -> str:
        for key in ("goal", "requirement", "request", "message"):
            value = data.get(key)
            if value:
                return str(value).strip()
        return ""

    # ==================== 校验：题目集合 ====================

    def _check_question_set(
        self, payload: Any, data: dict, db: Optional[Session], user_id: int
    ) -> tuple[list[dict], bool]:
        items, ids, meta = self._normalize_questions(payload)
        checks: list[dict] = []
        db_checked = False

        # ---- 数量 ----
        declared = meta.get("actual_count")
        if declared is None:
            declared = len(items) if items else len(ids)
        try:
            declared = int(declared or 0)
        except (TypeError, ValueError):
            declared = 0

        requested = meta.get("requested_count")
        if requested is None:
            requested = data.get("expected_count", data.get("count"))
        try:
            requested = int(requested) if requested is not None else None
        except (TypeError, ValueError):
            requested = None

        has_content = bool(items or ids or declared)
        checks.append(self._check(
            "结果非空", has_content,
            "未取得任何题目" if not has_content else f"声明 {declared} 道",
        ))

        if requested is None:
            checks.append(self._check(
                "数量达标", True,
                "调用方未提供期望数量，跳过该项", critical=False,
            ))
        else:
            count_ok = (
                declared == requested
                and meta.get("count_met", True) is not False
                and (not items or len(items) == requested)
            )
            checks.append(self._check(
                "数量达标", count_ok,
                f"期望 {requested} 道，实际 {declared} 道"
                + (f"（明细 {len(items)} 道）" if items and len(items) != declared else ""),
            ))

        # ---- 状态与数量自洽（严禁把 partial 报成 success）----
        status = str(meta.get("status") or "").strip().lower()
        if status in ("success", "partial", "failed"):
            if status == "success":
                status_ok = requested is None or declared >= requested
                expect = f"success 要求实际 ≥ 要求数（{declared}/{requested}）"
            elif status == "partial":
                status_ok = 0 < declared and (requested is None or declared < requested)
                expect = f"partial 要求 0 < 实际 < 要求数（{declared}/{requested}）"
            else:
                status_ok = declared == 0
                expect = f"failed 要求实际数为 0（实际 {declared}）"
            checks.append(self._check("状态与数量自洽", status_ok, expect))

        if not has_content:
            return checks, db_checked

        # ---- 落库比对：缺明细时用数据库记录补齐（只读）----
        rows: list[Question] = []
        if db is not None and ids:
            db_checked = True
            rows = db.query(Question).filter(Question.id.in_(ids)).all()
            missing_ids = sorted(set(ids) - {r.id for r in rows})
            checks.append(self._check(
                "落库记录完整", not missing_ids,
                "全部可查询" if not missing_ids else f"缺失 id：{missing_ids}",
            ))
            checks.append(self._check(
                "落库数量一致", len(rows) == len(set(ids)),
                f"数据库 {len(rows)} 条 / 声明 {len(set(ids))} 条",
            ))
            if not items:
                items = [self._question_from_row(r) for r in rows]

        if not items:
            return checks, db_checked

        # ---- 明细与数据库记录逐题一致（防"返回一套、入库一套"）----
        if rows and any(isinstance(i, dict) and i.get("id") for i in items):
            row_map = {r.id: r for r in rows}
            mismatched: list[int] = []
            for idx, item in enumerate(items, 1):
                if not isinstance(item, dict):
                    continue
                qid = item.get("id")
                row = row_map.get(qid) if qid else None
                if row is None:
                    continue
                if (
                    self._content_key(str(item.get("content") or ""))
                    != self._content_key(row.content or "")
                    or str(item.get("question_type") or "") != row.question_type
                    or str(item.get("answer") or "").strip() != (row.answer or "").strip()
                ):
                    mismatched.append(idx)
            checks.append(self._check(
                "落库内容一致", not mismatched,
                "明细与数据库一致" if not mismatched
                else f"第 {mismatched} 题明细与数据库记录不一致",
            ))

        # ---- 逐题字段 ----
        no_content: list[int] = []
        no_explanation: list[int] = []
        bad_type: list[int] = []
        bad_answer: list[int] = []
        bad_options: list[int] = []
        bad_difficulty: list[int] = []

        for idx, item in enumerate(items, 1):
            if not isinstance(item, dict):
                no_content.append(idx)
                continue
            content = str(item.get("content") or "").strip()
            qtype = str(item.get("question_type") or "").strip()
            answer = str(item.get("answer") or "").strip()
            explanation = str(item.get("explanation") or "").strip()
            difficulty = str(item.get("difficulty") or "").strip().lower()

            if len(content) < self.MIN_CONTENT_CHARS:
                no_content.append(idx)
            if not explanation:
                no_explanation.append(idx)
            if qtype not in QUESTION_TYPES:
                bad_type.append(idx)
                continue
            if difficulty and difficulty not in DIFFICULTIES:
                bad_difficulty.append(idx)

            if qtype in self.CHOICE_TYPES:
                options = self._parse_options(item.get("options"))
                if options is None or not 2 <= len(options) <= 5:
                    bad_options.append(idx)
                    continue
                letters = self._extract_letters(answer)
                valid = {"ABCDE"[i] for i in range(len(options))}
                if not letters or any(ch not in valid for ch in letters):
                    bad_answer.append(idx)
                elif qtype == "single_choice" and len(letters) != 1:
                    bad_answer.append(idx)
                elif qtype == "multiple_choice" and len(set(letters)) < 2:
                    bad_answer.append(idx)
            elif qtype == "true_false":
                if answer not in ("正确", "错误"):
                    bad_answer.append(idx)
            else:  # short_answer
                if not answer:
                    bad_answer.append(idx)

        checks.append(self._check(
            "题干完整性", not no_content,
            "全部完整" if not no_content else f"第 {no_content} 题题干缺失或过短",
        ))
        checks.append(self._check(
            "解析完整性", not no_explanation,
            "全部含解析" if not no_explanation else f"第 {no_explanation} 题缺少 explanation",
        ))
        checks.append(self._check(
            "题型合法性", not bad_type,
            "题型均合法" if not bad_type else f"第 {bad_type} 题题型非法",
        ))
        checks.append(self._check(
            "选项合法性", not bad_options,
            "选项均合法" if not bad_options else f"第 {bad_options} 题选项数量/格式非法",
        ))
        checks.append(self._check(
            "答案合法性", not bad_answer,
            "答案均合法" if not bad_answer else f"第 {bad_answer} 题答案与题型不匹配",
        ))

        # ---- 去重 ----
        keys = [self._content_key(str(i.get("content") or "")) for i in items if isinstance(i, dict)]
        dup = len(keys) - len(set(keys))
        checks.append(self._check(
            "题干去重", dup == 0,
            "无重复题干" if dup == 0 else f"存在 {dup} 道重复题干",
        ))

        checks.append(self._check(
            "难度合法性", not bad_difficulty,
            "难度均合法" if not bad_difficulty else f"第 {bad_difficulty} 题难度非法",
            critical=False,
        ))
        return checks, db_checked

    @staticmethod
    def _normalize_questions(payload: Any) -> tuple[list[dict], list[int], dict]:
        """把上游各种形态的题目结果统一成 (明细列表, id 列表, 元信息)."""
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)], [], {}
        if not isinstance(payload, dict):
            return [], [], {}

        items: list[dict] = []
        for key in ("questions", "items", "question_list"):
            value = payload.get(key)
            if isinstance(value, list):
                items = [x for x in value if isinstance(x, dict)]
                break

        ids: list[int] = []
        raw_ids = payload.get("question_ids") or payload.get("ids") or []
        if isinstance(raw_ids, list):
            for value in raw_ids:
                try:
                    ids.append(int(value))
                except (TypeError, ValueError):
                    continue
        return items, ids, payload

    @staticmethod
    def _question_from_row(row: Question) -> dict:
        options = row.options
        if isinstance(options, str):
            try:
                options = json.loads(options)
            except (ValueError, TypeError):
                options = None
        return {
            "id": row.id,
            "content": row.content,
            "question_type": row.question_type,
            "options": options,
            "answer": row.answer,
            "explanation": row.explanation or "",
            "difficulty": row.difficulty,
        }

    @staticmethod
    def _parse_options(raw: Any) -> Optional[list]:
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                return None
        if not isinstance(raw, list):
            return None
        options = [str(o).strip() for o in raw if str(o).strip()]
        return options

    @staticmethod
    def _extract_letters(text: str) -> list[str]:
        return [c.upper() for c in re.findall(r"[A-Ea-e]", text or "")]

    @staticmethod
    def _content_key(content: str) -> str:
        return re.sub(r"[\s，。？！,\.\?\!；;：:、“”\"'（）()\[\]【】]", "", content).lower()

    # ==================== 校验：学习计划 ====================

    def _check_study_plan(
        self, payload: Any, data: dict, db: Optional[Session], user_id: int
    ) -> tuple[list[dict], bool]:
        checks: list[dict] = []
        db_checked = False

        if not isinstance(payload, dict):
            checks.append(self._check("结构合法性", False, "学习计划结果必须是字典结构"))
            return checks, db_checked

        plan_id = payload.get("plan_id", payload.get("id"))
        try:
            plan_id = int(plan_id) if plan_id is not None else None
        except (TypeError, ValueError):
            plan_id = None

        required = ("title", "subject", "exam_date", "daily_minutes", "days", "task_count")
        missing = [k for k in required if payload.get(k) in (None, "", [])]
        if plan_id is None:
            missing.insert(0, "plan_id")
        checks.append(self._check(
            "必填字段完整", not missing,
            "字段齐全" if not missing else f"缺少：{'、'.join(missing)}",
        ))

        # ---- 考试日期：格式合法 + 未过期 ----
        exam_date: Optional[date] = None
        raw_exam_date = payload.get("exam_date")
        if raw_exam_date:
            try:
                exam_date = self._as_date(raw_exam_date)
            except (ValueError, TypeError):
                exam_date = None
        checks.append(self._check(
            "考试日期合法", exam_date is not None,
            f"{exam_date.isoformat()}" if exam_date else f"无法解析考试日期：{raw_exam_date}",
        ))
        if exam_date is not None:
            checks.append(self._check(
                "考试日期未过期", exam_date >= date.today(),
                f"考试日期 {exam_date.isoformat()}（今天 {date.today().isoformat()}）",
                critical=False,
            ))

        try:
            days = int(payload.get("days") or 0)
        except (TypeError, ValueError):
            days = 0
        try:
            task_count = int(payload.get("task_count") or 0)
        except (TypeError, ValueError):
            task_count = 0
        try:
            daily_minutes = int(payload.get("daily_minutes") or 0)
        except (TypeError, ValueError):
            daily_minutes = 0

        checks.append(self._check(
            "任务非空", task_count >= 1,
            f"任务数 {task_count}" if task_count >= 1 else "任务数为 0",
        ))
        checks.append(self._check(
            "天数合法", days >= 1, f"{days} 天" if days >= 1 else f"天数非法（{days}）",
        ))
        checks.append(self._check(
            "每日时长合法", daily_minutes >= self.MIN_TASK_MINUTES,
            f"每日上限 {daily_minutes} 分钟",
        ))

        # ---- 每日时长不超限（结果自带汇总）----
        summary = payload.get("daily_summary")
        over_days: list[str] = []
        if isinstance(summary, dict):
            for day, info in summary.items():
                if not isinstance(info, dict):
                    continue
                total = info.get("total")
                limit = info.get("limit", daily_minutes)
                try:
                    if int(total) > int(limit):
                        over_days.append(f"{day}({total}>{limit})")
                except (TypeError, ValueError):
                    over_days.append(f"{day}(数据异常)")
        checks.append(self._check(
            "每日时长不超限", not over_days,
            "每日均在上限内" if not over_days else f"超限：{'、'.join(over_days)}",
        ))

        # ---- 落库校验（只读）----
        if db is None or plan_id is None:
            return checks, db_checked

        db_checked = True
        plan = db.get(StudyPlan, plan_id)
        checks.append(self._check(
            "落库存在", plan is not None,
            f"plan_id={plan_id}" if plan else f"数据库中不存在 plan_id={plan_id}",
        ))
        if plan is None:
            return checks, db_checked

        checks.append(self._check(
            "归属正确", plan.user_id == user_id,
            f"plan.user_id={plan.user_id} / 当前用户 {user_id}",
        ))

        # ---- 结果与数据库字段一致（考试日期/每日预算/标题）----
        if exam_date is not None:
            db_exam = self._as_date(plan.exam_date) if plan.exam_date else None
            checks.append(self._check(
                "考试日期与数据库一致", db_exam == exam_date,
                f"结果 {exam_date.isoformat()} / 数据库 "
                f"{db_exam.isoformat() if db_exam else 'NULL'}",
            ))

        payload_title = str(payload.get("title") or "").strip()
        fields_ok = plan.daily_minutes == daily_minutes and (
            not payload_title or (plan.title or "").strip() == payload_title
        )
        checks.append(self._check(
            "计划字段与数据库一致", fields_ok,
            f"每日上限 结果 {daily_minutes} / 数据库 {plan.daily_minutes}；"
            f"标题 结果 {payload_title or '(未提供)'} / 数据库 {plan.title}",
        ))

        rows = (
            db.query(
                StudyTask.scheduled_date,
                func.sum(StudyTask.estimated_minutes),
                func.count(StudyTask.id),
                func.min(StudyTask.estimated_minutes),
            )
            .filter(StudyTask.plan_id == plan_id)
            .group_by(StudyTask.scheduled_date)
            .all()
        )
        db_total = sum(int(count) for _, _, count, _ in rows)
        checks.append(self._check(
            "任务数量一致", db_total == task_count,
            f"数据库 {db_total} 个 / 结果声明 {task_count} 个",
        ))

        # ---- 无效任务：标题为空 / 时长异常 ----
        blank_tasks = int(
            db.query(func.count(StudyTask.id))
            .filter(
                StudyTask.plan_id == plan_id,
                or_(StudyTask.title.is_(None), func.trim(StudyTask.title) == ""),
            )
            .scalar()
            or 0
        )
        checks.append(self._check(
            "任务内容完整", blank_tasks == 0,
            "任务均有标题" if blank_tasks == 0 else f"{blank_tasks} 个任务缺少标题",
        ))

        over_db = [
            f"{self._as_date(day).isoformat()}({int(total or 0)}>{plan.daily_minutes})"
            for day, total, _, _ in rows
            if int(total or 0) > plan.daily_minutes
        ]
        checks.append(self._check(
            "落库每日时长未超限", not over_db,
            "数据库每日汇总均在上限内" if not over_db else f"超限：{'、'.join(over_db)}",
        ))

        min_minutes = min((int(m or 0) for _, _, _, m in rows), default=0)
        checks.append(self._check(
            "任务时长合法", min_minutes >= self.MIN_TASK_MINUTES,
            f"最小任务 {min_minutes} 分钟（下限 {self.MIN_TASK_MINUTES}）",
        ))

        # ---- 任务日期应落在计划开始日与考试日之间 ----
        start = self._as_date(plan.created_at) if plan.created_at else date.today()
        out_of_range = [
            self._as_date(day).isoformat()
            for day, _, _, _ in rows
            if plan.exam_date and not (start <= self._as_date(day) < plan.exam_date)
        ]
        checks.append(self._check(
            "任务日期范围", not out_of_range,
            "日期均落在计划区间内" if not out_of_range else f"越界：{'、'.join(out_of_range)}",
        ))

        checks.append(self._check(
            "调整记录可解析", self._is_json(plan.adjustment_log),
            "adjustment_log 可解析" if self._is_json(plan.adjustment_log) else "adjustment_log 不是合法 JSON",
            critical=False,
        ))
        return checks, db_checked

    @staticmethod
    def _as_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _real_counts(db: Session, user_id: int) -> tuple[int, int, int]:
        """当前用户在数据库中的真实数据量：答题 / 学习记录 / 学习任务."""
        answers = int(
            db.query(func.count(Answer.id))
            .filter(Answer.user_id == user_id)
            .scalar()
            or 0
        )
        records = int(
            db.query(func.count(LearningRecord.id))
            .filter(LearningRecord.user_id == user_id)
            .scalar()
            or 0
        )
        tasks = int(
            db.query(func.count(StudyTask.id))
            .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
            .filter(StudyPlan.user_id == user_id)
            .scalar()
            or 0
        )
        return answers, records, tasks

    @staticmethod
    def _is_json(text: Optional[str]) -> bool:
        if not text:
            return True
        try:
            json.loads(text)
            return True
        except (ValueError, TypeError):
            return False

    # ==================== 校验：学情分析 ====================

    def _check_learning_analysis(
        self, payload: Any, data: dict, db: Optional[Session], user_id: int
    ) -> tuple[list[dict], bool]:
        checks: list[dict] = []
        db_checked = False
        if not isinstance(payload, dict):
            checks.append(self._check("结构合法性", False, "学情结果必须是字典结构"))
            return checks, db_checked

        sufficient = payload.get("sufficient")
        checks.append(self._check(
            "结构完整性", isinstance(sufficient, bool),
            "含 sufficient 标记" if isinstance(sufficient, bool) else "缺少布尔型 sufficient 标记",
        ))

        # 数据不足属于"如实上报"，不应判失败
        if sufficient is False:
            missing = payload.get("missing") or []
            checks.append(self._check(
                "数据不足已标注", bool(missing),
                f"缺少：{'、'.join(map(str, missing))}" if missing
                else "声明数据不足但未列出缺少项",
            ))
            checks.append(self._check(
                "无编造报告", payload.get("report") in (None, {}),
                "数据不足时未输出报告" if payload.get("report") in (None, {})
                else "数据不足却输出了学情报告",
                critical=False,
            ))
            if db is not None:
                answers, records, tasks = self._real_counts(db, user_id)
                db_checked = True
                checks.append(self._check(
                    "不足说明与数据一致",
                    answers == 0 and records == 0 and tasks == 0,
                    f"数据库 答题 {answers} / 学习记录 {records} / 任务 {tasks}",
                    critical=False,
                ))
            return checks, db_checked

        if sufficient is not True:
            return checks, db_checked

        report = payload.get("report")
        if not isinstance(report, dict):
            checks.append(self._check("结构完整性", False, "sufficient=True 但缺少 report"))
            return checks, db_checked

        missing = [
            k for k in ("overview", "mastery", "weak_points", "strong_points")
            if k not in report
        ]
        checks.append(self._check(
            "报告字段完整", not missing,
            "报告字段齐全" if not missing else f"report 缺少：{'、'.join(missing)}",
        ))

        overview = report.get("overview")
        checks.append(self._check(
            "概览结构", isinstance(overview, dict),
            "overview 为字典" if isinstance(overview, dict) else "overview 缺失或类型错误",
        ))

        numeric_ok = True
        detail = "数值合法"
        if isinstance(overview, dict):
            for key in ("total_study_minutes", "total_questions", "task_total", "task_completed"):
                value = overview.get(key)
                if value is None:
                    continue
                try:
                    if int(value) < 0:
                        numeric_ok = False
                        detail = f"{key} 为负（{value}）"
                except (TypeError, ValueError):
                    numeric_ok = False
                    detail = f"{key} 非数值（{value}）"
        checks.append(self._check("数值合法性", numeric_ok, detail, critical=False))

        # ---- 与数据库交叉校验：结论必须有真实数据支撑（防编造）----
        if db is not None:
            answers, records, tasks = self._real_counts(db, user_id)
            db_checked = True
            checks.append(self._check(
                "真实数据依据",
                answers > 0 or records > 0 or tasks > 0,
                f"答题 {answers} 条 / 学习记录 {records} 条 / 任务 {tasks} 个",
            ))
            if isinstance(overview, dict):
                claimed_questions = self._as_int(overview.get("total_questions"))
                if claimed_questions is not None:
                    checks.append(self._check(
                        "结论不超出真实数据", claimed_questions <= answers,
                        f"报告 {claimed_questions} 道答题 / 数据库 {answers} 道",
                    ))
                claimed_tasks = self._as_int(overview.get("task_total"))
                if claimed_tasks is not None:
                    checks.append(self._check(
                        "任务数与真实数据一致", claimed_tasks <= tasks,
                        f"报告 {claimed_tasks} 个任务 / 数据库 {tasks} 个",
                    ))

        checks.append(self._check(
            "摘要可读", bool(str(payload.get("summary") or "").strip()),
            "summary 非空" if str(payload.get("summary") or "").strip() else "summary 为空",
            critical=False,
        ))
        return checks, db_checked

    # ==================== 校验：知识检索 ====================

    def _check_knowledge_retrieval(
        self, payload: Any, data: dict, db: Optional[Session], user_id: int
    ) -> tuple[list[dict], bool]:
        checks: list[dict] = []
        if not isinstance(payload, dict):
            checks.append(self._check("结构合法性", False, "检索结果必须是字典结构"))
            return checks, False

        found = payload.get("found")
        checks.append(self._check(
            "结构完整性", isinstance(found, bool),
            "含 found 标记" if isinstance(found, bool) else "缺少布尔型 found 标记",
        ))

        results = payload.get("results") or []
        if not isinstance(results, list):
            checks.append(self._check("命中结构", False, "results 必须是列表"))
            return checks, False

        if found is False:
            checks.append(self._check(
                "未命中已标注", not results and bool(str(payload.get("summary") or "").strip()),
                f"results={len(results)}，已返回说明" if not results
                else "found=False 但仍返回了检索结果",
            ))
            return checks, False

        checks.append(self._check(
            "命中结果非空", bool(results),
            f"{len(results)} 条" if results else "found=True 但 results 为空",
        ))

        no_title = [
            i for i, item in enumerate(results, 1)
            if not isinstance(item, dict) or not str(item.get("title") or "").strip()
        ]
        checks.append(self._check(
            "条目字段完整", not no_title,
            "条目均含标题" if not no_title else f"第 {no_title} 条缺少 title",
        ))

        try:
            declared = int(payload.get("count")) if payload.get("count") is not None else len(results)
        except (TypeError, ValueError):
            declared = -1
        checks.append(self._check(
            "条数自洽", declared == len(results),
            f"声明 {declared} 条 / 实际 {len(results)} 条",
        ))
        return checks, False

    # ==================== 校验：通用 ====================

    def _check_generic(
        self, payload: Any, data: dict, db: Optional[Session], user_id: int
    ) -> tuple[list[dict], bool]:
        checks: list[dict] = [self._check(
            "结果非空", payload not in (None, "", [], {}),
            f"类型 {type(payload).__name__}",
        )]

        fields = data.get("required_fields") or []
        if isinstance(fields, str):
            fields = [fields]
        if fields:
            missing = [f for f in fields if not self._get_field(payload, str(f))]
            checks.append(self._check(
                "必填字段完整", not missing,
                "字段齐全" if not missing else f"缺少：{'、'.join(missing)}",
            ))
        return checks, False

    @staticmethod
    def _get_field(payload: Any, path: str) -> Any:
        current = payload
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    # ==================== LLM 辅助校验 ====================

    def _llm_review(
        self, target: str, payload: Any, requirement: str
    ) -> Optional[tuple[float, str]]:
        """对结果与需求的契合度打分；不可用时返回 None（由规则层独立给结论）."""
        if not llm_service.available:
            return None
        try:
            text = json.dumps(payload, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(payload)
        prompt = (
            f"你是结果质量评审员。上游 Agent 产出了「{target}」类型的结果，"
            "请评估其结果结构完整性与对用户需求的契合度（允许表述差异，不要臆造事实）。\n"
            f"用户需求：{requirement or '未提供，仅评估结构合理性'}\n"
            f"结果（JSON）：{text[: self.MAX_LLM_CHARS]}\n"
            "只输出 JSON："
            '{"score": 0~1的小数, "feedback": "一句话改进意见（高分时可为空）"}'
        )
        try:
            result = llm_service.structured_output(
                [{"role": "user", "content": prompt}], _LLMReview, temperature=0.0
            )
        except Exception:
            return None
        if result is None:
            return None
        return max(0.0, min(float(result.score), 1.0)), result.feedback

    # ==================== 结果组装 ====================

    @staticmethod
    def _check(name: str, passed: bool, detail: str = "", critical: bool = True) -> dict:
        return {
            "name": name,
            "passed": bool(passed),
            "critical": bool(critical),
            "detail": detail,
        }

    def _assemble(
        self, target: str, checks: list[dict], db_checked: bool,
        llm_score: Optional[float] = None, llm_feedback: str = "",
    ) -> dict:
        total = len(checks)
        passed_count = sum(1 for c in checks if c["passed"])
        failed = [c for c in checks if not c["passed"]]
        critical_failed = [c for c in failed if c["critical"]]

        passed = bool(checks) and not critical_failed
        # LLM 层作为补充门槛：仅在其真正执行并低于阈值时否决
        if passed and llm_score is not None and llm_score < self.LLM_THRESHOLD:
            passed = False

        issues = [f"{c['name']}：{c['detail']}" for c in failed]
        suggestions = self._suggestions(failed)
        score = round(passed_count / total, 3) if total else 0.0

        if passed:
            message = f"校验通过（{passed_count}/{total} 项）"
            if llm_score is not None:
                message += f"，LLM 契合度 {llm_score:.2f}"
            message += "。"
        else:
            message = (
                f"校验未通过：{len(failed)} 项异常"
                f"（关键 {len(critical_failed)} 项）。"
            )

        return {
            "agent": self.name,
            "target": target,
            "passed": passed,
            "score": score,
            "check_count": total,
            "passed_count": passed_count,
            "failed_count": len(failed),
            "critical_failed": [c["name"] for c in critical_failed],
            "checks": checks,
            "issues": issues,
            "suggestions": suggestions,
            "llm_score": llm_score,
            "llm_feedback": llm_feedback,
            "db_checked": db_checked,
            "message": message,
            "reason": "；".join(issues),
        }

    def _suggestions(self, failed: list[dict]) -> list[str]:
        result: list[str] = []
        for check in failed:
            name = check["name"]
            for keyword, advice in self.SUGGESTIONS:
                if keyword in name and advice not in result:
                    result.append(advice)
                    break
        if failed and not result:
            result.append("请根据上述校验问题修正结果后重新提交。")
        return result
