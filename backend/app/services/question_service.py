"""题目服务：生成（AI 优先 / 内置题库降级）与批改."""
import json
import random
import re
from typing import List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import Answer, KnowledgePoint, Question, User
from app.services.llm_service import llm_service


# ==================== 内置题库（LLM 不可用时的降级方案 & 演示数据） ====================

BANK: List[dict] = [
    # ---- 集合 ----
    {"kp": "集合", "type": "single_choice", "difficulty": "easy",
     "content": "设 A = {1, 2, 3}，B = {2, 3, 4}，则 A ∩ B = ？",
     "options": ["{1, 2, 3, 4}", "{2, 3}", "{1, 4}", "∅"],
     "answer": "B", "explanation": "A ∩ B 取两个集合共同的元素 {2, 3}。"},
    {"kp": "集合", "type": "true_false", "difficulty": "easy",
     "content": "空集是任何集合的真子集。",
     "options": None, "answer": "错误",
     "explanation": "空集是任何集合的子集，但不是自身的真子集，正确说法是：空集是任何非空集合的真子集。"},
    {"kp": "集合", "type": "single_choice", "difficulty": "medium",
     "content": "设 |A| = 5，|B| = 3，且 B ⊆ A，则 A − B 的元素个数为？",
     "options": ["2", "3", "5", "8"],
     "answer": "A", "explanation": "A − B 是从 A 中去掉 B 的元素，5 − 3 = 2。"},
    # ---- 关系 ----
    {"kp": "关系", "type": "single_choice", "difficulty": "easy",
     "content": "若关系 R 同时是自反的、对称的、传递的，则 R 是？",
     "options": ["偏序关系", "等价关系", "函数关系", "恒等关系"],
     "answer": "B", "explanation": "同时满足自反、对称、传递三个性质的关系称为等价关系。"},
    {"kp": "关系", "type": "true_false", "difficulty": "medium",
     "content": "任何集合上的关系都既是对称的又是反对称的。",
     "options": None, "answer": "错误",
     "explanation": "对称与反对称可以同时成立（如恒等关系），但并非任何关系都满足，例如 < 在整数集上反对称但不对称。"},
    {"kp": "关系", "type": "single_choice", "difficulty": "medium",
     "content": "设 A = {1, 2, 3}，R = {<1,2>, <2,1>}，则 R 在 A 上是？",
     "options": ["自反的", "对称的", "传递的", "等价关系"],
     "answer": "B", "explanation": "R 中 <1,2> 与 <2,1> 互为逆序，满足对称性；但缺少 <1,1> 不自反，也因缺 <1,1> 不传递。"},
    # ---- 函数 ----
    {"kp": "函数", "type": "single_choice", "difficulty": "easy",
     "content": "函数 f: A → B 是双射当且仅当？",
     "options": ["f 是单射", "f 是满射", "f 既是单射又是满射", "|A| = |B|"],
     "answer": "C", "explanation": "双射 = 单射 + 满射，即一一对应。"},
    {"kp": "函数", "type": "true_false", "difficulty": "medium",
     "content": "f(x) = x² 在实数集 R 上是单射。",
     "options": None, "answer": "错误",
     "explanation": "f(1) = f(−1) = 1，不同输入有相同输出，不满足单射定义。"},
    {"kp": "函数", "type": "single_choice", "difficulty": "hard",
     "content": "设 |A| = m，|B| = n，则 A 到 B 的不同函数个数为？",
     "options": ["m^n", "n^m", "m·n", "C(m, n)"],
     "answer": "B", "explanation": "A 中每个元素有 n 种对应方式，共 m 个元素，因此为 n^m。"},
    # ---- 图论 ----
    {"kp": "图论", "type": "single_choice", "difficulty": "medium",
     "content": "下列关于割点（cut vertex）的描述正确的是？",
     "options": [
         "删除割点后图仍然是连通的",
         "删除割点及其关联边后，图的连通分量数增加",
         "割点一定是度为 1 的顶点",
         "每个连通图都至少有一个割点",
     ],
     "answer": "B",
     "explanation": "割点的定义：删除该顶点及其关联边后，连通分量数量增加。A 与定义相反；C 度为 1 的顶点（叶子）删除后不增加分量，通常不是割点；D 完全图 K_n（n≥2）没有割点。"},
    {"kp": "图论", "type": "single_choice", "difficulty": "easy",
     "content": "完全图 K₅ 的边数为？",
     "options": ["5", "10", "20", "4"],
     "answer": "B", "explanation": "n 个顶点的完全图边数为 n(n−1)/2 = 5×4/2 = 10。"},
    {"kp": "图论", "type": "true_false", "difficulty": "medium",
     "content": "在连通图中，删除一条割边（桥）会使图变得不连通。",
     "options": None, "answer": "正确",
     "explanation": "割边（桥）的定义：删除该边后图的连通分量数增加。对连通图而言即变为不连通。"},
    {"kp": "图论", "type": "short_answer", "difficulty": "medium",
     "content": "简述什么是割点，并举一个例子。",
     "options": None,
     "answer": "割点 连通分量 例子 删除 顶点",
     "explanation": "割点（割顶）是指删除该顶点及其所有关联边后，图的连通分量数量增加的顶点。例如路径图 a—b—c 中，删除 b 后得到两个孤立顶点 a 和 c，因此 b 是割点。"},
    # ---- 树 ----
    {"kp": "树", "type": "single_choice", "difficulty": "easy",
     "content": "n 个顶点的树包含多少条边？",
     "options": ["n", "n − 1", "n + 1", "2n"],
     "answer": "B", "explanation": "树是无回路连通图，n 个顶点恰有 n − 1 条边。"},
    {"kp": "树", "type": "true_false", "difficulty": "easy",
     "content": "树中任意两个顶点之间存在唯一的路径。",
     "options": None, "answer": "正确",
     "explanation": "连通性保证路径存在，无回路保证路径唯一，这是树的等价定义之一。"},
    {"kp": "树", "type": "single_choice", "difficulty": "medium",
     "content": "下列哪一项不是树的等价定义？",
     "options": [
         "无回路且连通的无向图",
         "任意两点之间存在唯一路径的图",
         "边数等于顶点数减 1 且连通的图",
         "任意两点之间存在至少两条不同路径的图",
     ],
     "answer": "D",
     "explanation": "树中任意两点之间路径唯一，「至少两条不同路径」意味着存在回路，与树的定义矛盾。"},
    # ---- 命题逻辑（补充科目内容，使科目筛选更丰富） ----
    {"kp": "命题逻辑", "type": "single_choice", "difficulty": "easy",
     "content": "命题 P → Q 的逆否命题是？",
     "options": ["Q → P", "¬Q → ¬P", "¬P → ¬Q", "P ↔ Q"],
     "answer": "B", "explanation": "P → Q 的逆否命题为 ¬Q → ¬P，两者逻辑等价。"},
    {"kp": "命题逻辑", "type": "true_false", "difficulty": "medium",
     "content": "命题公式 (P ∧ ¬P) 是矛盾式（永假式）。",
     "options": None, "answer": "正确",
     "explanation": "P 与 ¬P 不可能同时为真，因此 P ∧ ¬P 对任何赋值都为假，是矛盾式。"},
    {"kp": "命题逻辑", "type": "short_answer", "difficulty": "hard",
     "content": "用真值表说明 P → Q 与 ¬P ∨ Q 的等价性。",
     "options": None,
     "answer": "真值表 等价 蕴含 四种赋值",
     "explanation": "对 P、Q 的四种赋值组合逐一验证：当 P=T,Q=F 时两者都为假，其余三种情况都为真，真值表完全相同，故 P → Q ≡ ¬P ∨ Q。"},
    # ---- 多选题（LLM 不可用时的多选题兜底样本，答案均为 3 个正确项） ----
    {"kp": "集合", "type": "multiple_choice", "difficulty": "easy",
     "content": "设 A = {1, 2, 3}，B = {3, 4}，下列命题正确的有？",
     "options": ["3 ∈ A ∩ B", "1 ∈ A ∪ B", "A − B = {3}", "A ∪ B = {1, 2, 3, 4}"],
     "answer": "ABD",
     "explanation": "A ∩ B = {3}，故 A 正确；A ∪ B = {1,2,3,4}，故 B、D 正确；A − B = {1,2}，故 C 错误。"},
    {"kp": "关系", "type": "multiple_choice", "difficulty": "medium",
     "content": "设 R 是集合 A 上的二元关系，若 R 是等价关系，则它必须具备下列哪些性质？",
     "options": ["自反性", "反对称性", "对称性", "传递性"],
     "answer": "ACD",
     "explanation": "等价关系要求自反、对称、传递；反对称性是偏序关系的性质，不是等价关系必须具备的。"},
    {"kp": "函数", "type": "multiple_choice", "difficulty": "hard",
     "content": "设 f: A → B，g: B → C，下列命题正确的有？",
     "options": [
         "若 f、g 都是单射，则 g∘f 是单射",
         "若 g∘f 是满射，则 f 必是满射",
         "若 g∘f 是单射，则 f 必是单射",
         "若 f、g 都是满射，则 g∘f 是满射",
     ],
     "answer": "ACD",
     "explanation": "单射复合仍单射（A）；满射复合仍满射（D）；g∘f 单射可推出 f 单射（C）。B 错误：g∘f 满射只能推出 g 满射，f 未必满射。"},
    {"kp": "图论", "type": "multiple_choice", "difficulty": "medium",
     "content": "下列关于二分图与欧拉回路的说法，正确的有？",
     "options": [
         "树都是二分图",
         "完全二分图 K₃,₃ 不是平面图",
         "每个连通图都存在欧拉回路",
         "无向连通图存在欧拉回路当且仅当所有顶点的度数都是偶数",
     ],
     "answer": "ABD",
     "explanation": "树无回路，按层染色即为二分图（A）；K₃,₃ 含 K₃,₃ 细分结构，非平面（B）；欧拉回路存在性由欧拉定理保证（D）。C 错误，例如只有一条边的 K₂ 连通但两顶点度数均为 1，不存在欧拉回路。"},
    {"kp": "树", "type": "multiple_choice", "difficulty": "easy",
     "content": "关于树的性质，下列正确的有？",
     "options": [
         "n 个顶点的树恰有 n − 1 条边",
         "树中一定存在回路",
         "树中任意两个顶点之间恰有一条路径",
         "在树上添加一条边一定会产生回路",
     ],
     "answer": "ACD",
     "explanation": "树的定义包含无回路、连通，故有 n−1 条边（A）、路径唯一（C）；任意两点已有唯一路径，添加新边即形成回路（D）。B 与树的定义矛盾。"},
    {"kp": "命题逻辑", "type": "multiple_choice", "difficulty": "medium",
     "content": "下列命题公式中是重言式（永真式）的有？",
     "options": ["P ∨ ¬P", "P ∧ ¬P", "P → (Q → P)", "P ↔ ¬¬P"],
     "answer": "ACD",
     "explanation": "P ∨ ¬P 是排中律（A）；P → (Q → P) 前件真时后件恒真（C）；P 与 ¬¬P 等价（D）。B 是矛盾式，永远为假。"},
]


class GeneratedQuestion(BaseModel):
    """LLM 生成题目的结构化输出（保留供旧调用方使用）."""

    content: str
    question_type: str = Field(
        pattern="^(single_choice|multiple_choice|true_false|short_answer)$"
    )
    options: Optional[List[str]] = None
    answer: str
    explanation: str = ""
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class GeneratedQuestions(BaseModel):
    questions: List[GeneratedQuestion]


# ==================== 生成结果归一化（服务层与 Agent 共用） ====================
#
# LLM 输出的原始 JSON 由逐条解析 + 归一化处理，而不是整批 Pydantic 校验：
# 单条题目字段异常只丢弃该条，不会让整批结果作废（这是"数量不达标"的常见原因）。

TYPE_ALIASES = {
    "single_choice": "single_choice", "single": "single_choice",
    "singlechoice": "single_choice", "choice": "single_choice",
    "单选": "single_choice", "单选题": "single_choice", "单项选择": "single_choice",
    "multiple_choice": "multiple_choice", "multiple": "multiple_choice",
    "multiplechoice": "multiple_choice", "multi": "multiple_choice",
    "多选": "multiple_choice", "多选题": "multiple_choice", "多项选择": "multiple_choice",
    "true_false": "true_false", "truefalse": "true_false", "judge": "true_false",
    "boolean": "true_false", "判断": "true_false", "判断题": "true_false",
    "short_answer": "short_answer", "shortanswer": "short_answer",
    "short": "short_answer", "essay": "short_answer",
    "简答": "short_answer", "简答题": "short_answer", "问答题": "short_answer",
}

DIFFICULTY_ALIASES = {
    "easy": "easy", "简单": "easy", "基础": "easy", "低": "easy",
    "medium": "medium", "中等": "medium", "中": "medium", "普通": "medium",
    "hard": "hard", "困难": "hard", "难": "hard", "高": "hard", "提高": "hard",
}


def normalize_question_type(raw: object) -> Optional[str]:
    """题型归一化：兼容中文名/英文别名，无法识别返回 None."""
    text = str(raw or "").strip().lower().replace("-", "_").replace(" ", "")
    return TYPE_ALIASES.get(text)


def normalize_difficulty(raw: object) -> str:
    """难度归一化，非法值回落 medium（不因难度写错丢弃整题）."""
    text = str(raw or "").strip().lower()
    return DIFFICULTY_ALIASES.get(text, "medium")


def extract_option_letters(text: str) -> List[str]:
    return [c.upper() for c in re.findall(r"[A-Ea-e]", text or "")]


def normalize_true_false(text: str) -> Optional[str]:
    value = (text or "").strip().lower()
    if value in {"true", "正确", "对", "t", "yes", "是", "√"}:
        return "正确"
    if value in {"false", "错误", "错", "f", "no", "否", "×"}:
        return "错误"
    return None


def question_content_key(content: str) -> str:
    """题干归一化：去空白与常见标点，用于判重."""
    return re.sub(r"[\s，。？！,\.\?\!；;：:、“”\"'（）()\[\]【】]", "", content or "").lower()


def normalize_options(value: object) -> Optional[List[str]]:
    """把选项统一成列表：支持 ["..."], {"A": "..."}, JSON 字符串, [{"A": "..."}]."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None

    if isinstance(value, dict):
        # 模型常按 {"A": "...", "B": "..."} 输出，按字母顺序还原为列表
        ordered = sorted(value.items(), key=lambda item: str(item[0]).strip().upper())
        return [str(v).strip() for _, v in ordered if str(v).strip()]

    if isinstance(value, list):
        collected: list[str] = []
        for item in value:
            if isinstance(item, dict):
                ordered = sorted(item.items(), key=lambda kv: str(kv[0]).strip().upper())
                collected.extend(str(v).strip() for _, v in ordered if str(v).strip())
            else:
                text = str(item).strip()
                if text:
                    collected.append(text)
        return collected

    return None


def normalize_generated_item(raw: object) -> Optional[dict]:
    """把模型返回的一条原始题目归一化为可落库结构；不合法返回 None."""
    if not isinstance(raw, dict):
        return None

    content = str(
        raw.get("content") or raw.get("question") or raw.get("stem") or ""
    ).strip()
    if len(content) < 5:
        return None

    qtype = normalize_question_type(raw.get("question_type") or raw.get("type"))
    if qtype is None:
        return None

    answer = str(raw.get("answer") or raw.get("correct_answer") or "").strip()
    options = raw.get("options") or raw.get("choices")

    if qtype in ("single_choice", "multiple_choice"):
        options = normalize_options(options)
        if options is None:
            return None
        if not 2 <= len(options) <= 5:
            return None
        letters = extract_option_letters(answer)
        valid = {"ABCDE"[i] for i in range(len(options))}
        if not letters or any(ch not in valid for ch in letters):
            return None
        if qtype == "single_choice":
            if len(letters) != 1:
                return None
            answer = letters[0]
        else:
            if len(set(letters)) < 2:
                return None
            answer = "".join(sorted(set(letters)))
    elif qtype == "true_false":
        answer = normalize_true_false(answer)
        if answer is None:
            return None
        options = None
    else:  # short_answer
        if not answer:
            return None
        options = None

    return {
        "content": content,
        "question_type": qtype,
        "options": options,
        "answer": answer,
        "explanation": str(
            raw.get("explanation") or raw.get("analysis") or ""
        ).strip(),
        "difficulty": normalize_difficulty(raw.get("difficulty")),
        "source": "ai",
    }


def parse_questions_json(text: str) -> List[dict]:
    """从模型文本中宽容地解析题目数组：支持代码块包裹/前后夹带说明文字."""
    def _strip_fence(value: str) -> str:
        value = (value or "").strip()
        if value.startswith("```"):
            value = value.strip("`").strip()
            if value.lower().startswith("json"):
                value = value[4:].strip()
        return value

    text = _strip_fence(text)
    if not text:
        return []

    candidates = [text]
    left, right = text.find("{"), text.rfind("}")
    if left != -1 and right > left:
        candidates.append(text[left:right + 1])
    left, right = text.find("["), text.rfind("]")
    if left != -1 and right > left:
        candidates.append(text[left:right + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            for key in ("questions", "items", "data", "question_list"):
                value = data.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
            continue
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    return []


class QuestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ===== 生成 =====

    # 单次请求的题量上限：题量过大易导致 JSON 被截断（整批解析失败）
    LLM_CHUNK = 5
    # LLM 补题轮次上限：不足时按缺口继续请求，直到达标或用尽轮次
    LLM_MAX_ROUNDS = 3

    def generate(
        self,
        user: User,
        knowledge_point_id: Optional[int],
        subject: Optional[str],
        count: int,
        difficulty: Optional[str],
        mastery_hint: Optional[float] = None,
    ) -> List[Question]:
        """生成题目：LLM 多轮补足 → 题库兜底，尽力保证数量达标.

        数量保证策略：
        1. 每轮最多请求 LLM_CHUNK 道，逐条解析（单条非法只丢弃该条）；
        2. 不足时把缺口继续请求，最多 LLM_MAX_ROUNDS 轮；
        3. 仍不足时从内置题库按「本知识点 → 同学科 → 全库」补齐（题干去重）；
        4. 题库也无更多不重复题目时，如实返回实际数量（不编造题目）。
        """
        kp = self._resolve_kp(knowledge_point_id, subject)
        if kp is None:
            raise ValueError("未找到对应知识点，请先选择有效的知识点或科目")

        count = max(1, int(count or 1))
        effective_difficulty = normalize_difficulty(
            difficulty or self._suggest_difficulty(mastery_hint)
        )

        items: List[dict] = []
        seen: set[str] = set()
        if llm_service.available:
            items = self._collect_from_llm(kp, count, effective_difficulty, seen)
        if len(items) < count:
            items.extend(self._bank_items(kp, count - len(items), seen))

        questions = [self._to_question(kp, item) for item in items[:count]]
        if questions:
            self.db.add_all(questions)
            self.db.commit()
            for q in questions:
                self.db.refresh(q)

        sources = {q.source for q in questions}
        logger.info(
            f"生成 {len(questions)}/{count} 道题"
            f"（kp={kp.name}, difficulty={effective_difficulty}, source={sorted(sources)}）"
        )
        return questions

    def _resolve_kp(
        self, knowledge_point_id: Optional[int], subject: Optional[str]
    ) -> Optional[KnowledgePoint]:
        if knowledge_point_id:
            return self.db.get(KnowledgePoint, knowledge_point_id)
        query = self.db.query(KnowledgePoint)
        if subject:
            query = query.filter(KnowledgePoint.subject == subject)
        return query.first()

    def _suggest_difficulty(self, mastery: Optional[float]) -> str:
        """根据掌握度动态决定难度."""
        if mastery is None:
            return "medium"
        if mastery < 0.5:
            return "easy"
        if mastery > 0.8:
            return "hard"
        return "medium"

    def _collect_from_llm(
        self, kp: KnowledgePoint, count: int, difficulty: str, seen: set[str]
    ) -> List[dict]:
        """多轮向 LLM 补题，直到数量达标或用尽轮次（逐条解析、题干去重）."""
        selected: List[dict] = []
        for round_index in range(1, self.LLM_MAX_ROUNDS + 1):
            if len(selected) >= count:
                break
            need = min(count - len(selected), self.LLM_CHUNK)
            raw_items = self._request_llm_batch(
                kp, need, difficulty, [item["content"] for item in selected]
            )
            if not raw_items:
                # 调用失败/无法解析：不再重试，交由题库兜底
                break

            added = 0
            for raw in raw_items:
                if len(selected) >= count:
                    break
                item = normalize_generated_item(raw)
                if item is None:
                    continue
                key = question_content_key(item["content"])
                if key in seen:
                    continue
                seen.add(key)
                selected.append(item)
                added += 1
            logger.info(
                f"LLM 第 {round_index} 轮：请求 {need} 道，新增 {added} 道，"
                f"累计 {len(selected)}/{count}（kp={kp.name}）"
            )
            if added == 0:
                break   # 本轮无有效增量，避免原地空转

        return selected

    def _request_llm_batch(
        self, kp: KnowledgePoint, count: int, difficulty: str,
        existing_contents: List[str],
    ) -> List[dict]:
        """请求一批题目原始 JSON；失败返回空列表（由调用方降级）."""
        existing_hint = "；".join(existing_contents[:20]) or "无"
        prompt = (
            f"你是{kp.subject}出题专家。请围绕知识点「{kp.name}」出 {count} 道题。\n"
            f"难度要求：{difficulty}（easy=简单, medium=中等, hard=困难）。\n"
            "题型只能从：单选题(single_choice)、多选题(multiple_choice)、"
            "判断题(true_false)、简答题(short_answer) 中选择。\n"
            "格式要求：\n"
            "1) 单选题：options 提供 4 个选项，answer 为单个正确选项字母（如 'A'）；\n"
            "2) 多选题：options 提供 4 个选项，answer 为多个正确选项字母（如 'AC'）；\n"
            "3) 判断题：answer 填 '正确' 或 '错误'，options 为 null；\n"
            "4) 简答题：answer 提供参考答案，options 为 null；\n"
            "5) 每题必须有完整题干、答案和 explanation 解析；\n"
            f"6) 不要与以下已生成题目重复：{existing_hint}\n"
            '只输出 JSON：{"questions": [ {...}, ... ]}，不要输出其他文字。'
        )
        try:
            content = llm_service.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=max(3000, count * 800),
            )
        except Exception:
            return []
        return parse_questions_json(content or "")

    def _bank_items(
        self, kp: KnowledgePoint, need: int, seen: set[str],
        question_types: Optional[List[str]] = None,
    ) -> List[dict]:
        """题库兜底补齐：本知识点 → 同学科 → 全库，跳过已出现题干/题型不符的题目."""
        if need <= 0:
            return []

        pools: List[List[dict]] = [[q for q in BANK if q["kp"] == kp.name]]
        siblings = {
            row.name
            for row in self.db.query(KnowledgePoint)
            .filter(KnowledgePoint.subject == kp.subject)
            .all()
        }
        pools.append([q for q in BANK if q["kp"] in siblings and q["kp"] != kp.name])
        pools.append(list(BANK))

        picked: List[dict] = []
        used: set[str] = set()
        for pool in pools:
            for entry in pool:
                if len(picked) >= need:
                    return picked
                if question_types and entry["type"] not in question_types:
                    continue
                key = question_content_key(entry["content"])
                if key in seen or key in used:
                    continue
                used.add(key)
                picked.append({
                    "content": entry["content"],
                    "question_type": entry["type"],
                    "options": entry["options"],
                    "answer": entry["answer"],
                    "explanation": entry["explanation"],
                    "difficulty": entry["difficulty"],
                    "source": "bank",
                })
        return picked

    def bank_fallback_items(
        self, kp: KnowledgePoint, count: int,
        exclude_contents: Optional[List[str]] = None,
        exclude_keys: Optional[set] = None,
        question_types: Optional[List[str]] = None,
    ) -> List[dict]:
        """内置题库兜底（供 generate / 练习生成 Agent 共用）.

        - exclude_contents：待排除的题干原文（会做归一化）；
        - exclude_keys：已归一化的题干 key（如数据库中已有题目，避免重复入库）；
        - question_types：只返回指定题型的题目。

        返回题目字典列表（含 source="bank"），按「本知识点 → 同学科 → 全库」
        顺序挑选；题库不足时返回实际条数。
        """
        seen = {question_content_key(c) for c in (exclude_contents or [])}
        if exclude_keys:
            seen |= set(exclude_keys)
        return self._bank_items(kp, count, seen, question_types=question_types)

    def _generate_from_bank(
        self, kp: KnowledgePoint, count: int, exclude: Optional[List[str]] = None
    ) -> List[Question]:
        """从内置题库抽题（未配置 LLM 时的降级方案）."""
        picked = self.bank_fallback_items(kp, count, exclude)
        if picked and len(picked) > 1:
            random.shuffle(picked)
        questions = [self._to_question(kp, item) for item in picked]
        logger.info(f"题库生成 {len(questions)}/{count} 道题（kp={kp.name}）")
        return questions

    def save_questions(
        self, kp: KnowledgePoint, items: List[dict]
    ) -> List[Question]:
        """批量保存已校验的题目（供 Agent 复用；只增不删）.

        单一事务：内部 commit，失败由调用方 rollback。
        items 结构：content / question_type / options / answer /
        explanation / difficulty / source(可选)。
        """
        if not items:
            return []
        objs = [self._to_question(kp, item) for item in items]
        self.db.add_all(objs)
        self.db.commit()
        for obj in objs:
            self.db.refresh(obj)
        logger.info(f"保存 {len(objs)} 道题目（kp={kp.name}）")
        return objs

    @staticmethod
    def _to_question(kp: KnowledgePoint, item: dict) -> Question:
        options = item.get("options")
        return Question(
            knowledge_point_id=kp.id,
            content=item["content"],
            question_type=item["question_type"],
            options=json.dumps(options, ensure_ascii=False) if options else None,
            answer=item["answer"],
            explanation=item.get("explanation") or "",
            difficulty=item.get("difficulty") or "medium",
            source=item.get("source") or "ai",
        )

    # ===== 批改 =====

    def grade(self, question: Question, user_answer: str) -> tuple[bool, float]:
        """批改答案，返回 (is_correct, score 0~1)."""
        answer = (user_answer or "").strip()
        if question.question_type == "multiple_choice":
            return self._grade_multiple_choice(question.answer, answer)
        if question.question_type in ("single_choice", "true_false"):
            correct = answer == question.answer.strip()
            return correct, 1.0 if correct else 0.0
        # 简答题：LLM 评分，降级为关键词匹配
        if llm_service.available:
            prompt = (
                f"题目：{question.content}\n"
                f"参考答案：{question.answer}\n"
                f"学生答案：{answer}\n"
                "请判断学生答案是否正确（允许表述差异）。"
                '只输出 JSON：{"correct": true/false, "score": 0~1 的小数}'
            )
            result = llm_service.chat([{"role": "user", "content": prompt}], temperature=0)
            if result:
                try:
                    data = json.loads(result.strip().strip("`"))
                    score = float(data.get("score", 0))
                    return bool(data.get("correct")), max(0.0, min(score, 1.0))
                except Exception:
                    pass
        return self._keyword_grade(question.answer, answer)

    @staticmethod
    def _grade_multiple_choice(reference: str, user_answer: str) -> tuple[bool, float]:
        """多选题批改：忽略分隔符/大小写，比较选项集合是否完全一致."""
        ref = sorted(set(re.findall(r"[A-Ea-e]", reference or "")))
        usr = sorted(set(re.findall(r"[A-Ea-e]", user_answer or "")))
        if not ref:
            return False, 0.0
        correct = ref == usr
        return correct, 1.0 if correct else 0.0

    def _keyword_grade(self, reference: str, user_answer: str) -> tuple[bool, float]:
        """关键词覆盖率评分（无 LLM 时的降级方案）."""
        keywords = [w for w in reference.split() if len(w) >= 2]
        if not keywords:
            return (len(user_answer) > 10, 0.5)
        hit = sum(1 for k in keywords if k in user_answer)
        score = round(hit / len(keywords), 2)
        return score >= 0.5, score