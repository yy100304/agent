"""题目服务：生成（AI 优先 / 内置题库降级）与批改."""
import json
import random
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
]


class GeneratedQuestion(BaseModel):
    """LLM 生成题目的结构化输出."""

    content: str
    question_type: str = Field(pattern="^(single_choice|true_false|short_answer)$")
    options: Optional[List[str]] = None
    answer: str
    explanation: str = ""
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class GeneratedQuestions(BaseModel):
    questions: List[GeneratedQuestion]


class QuestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ===== 生成 =====

    def generate(
        self,
        user: User,
        knowledge_point_id: Optional[int],
        subject: Optional[str],
        count: int,
        difficulty: Optional[str],
        mastery_hint: Optional[float] = None,
    ) -> List[Question]:
        """生成题目：优先 LLM，失败降级内置题库."""
        kp = self._resolve_kp(knowledge_point_id, subject)
        if kp is None:
            raise ValueError("未找到对应知识点，请先选择有效的知识点或科目")

        effective_difficulty = difficulty or self._suggest_difficulty(mastery_hint)

        questions: List[Question] = []
        if llm_service.available:
            questions = self._generate_by_llm(kp, count, effective_difficulty)
        if not questions:
            questions = self._generate_from_bank(kp, count)

        for q in questions:
            self.db.add(q)
        self.db.commit()
        for q in questions:
            self.db.refresh(q)
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

    def _generate_by_llm(
        self, kp: KnowledgePoint, count: int, difficulty: str
    ) -> List[Question]:
        prompt = (
            f"你是离散数学出题专家。请围绕知识点「{kp.subject} - {kp.name}」出 {count} 道题。\n"
            f"难度要求：{difficulty}（easy=简单, medium=中等, hard=困难）。\n"
            "题型在单选题(single_choice)、判断题(true_false)、简答题(short_answer)中合理搭配。\n"
            "单选题 options 提供 4 个选项，answer 填正确选项字母（如 'A'）。\n"
            "判断题 answer 填 '正确' 或 '错误'，options 为 null。\n"
            "简答题 answer 提供包含关键词的参考答案，options 为 null。\n"
            "所有题目必须提供 explanation 解析。"
        )
        result = llm_service.structured_output(
            [{"role": "user", "content": prompt}], GeneratedQuestions
        )
        if not result:
            return []
        questions = []
        for q in result.questions[:count]:
            questions.append(
                Question(
                    knowledge_point_id=kp.id,
                    content=q.content,
                    question_type=q.question_type,
                    options=json.dumps(q.options, ensure_ascii=False) if q.options else None,
                    answer=q.answer,
                    explanation=q.explanation,
                    difficulty=q.difficulty or difficulty,
                    source="ai",
                )
            )
        logger.info(f"LLM 生成 {len(questions)} 道题（kp={kp.name}）")
        return questions

    def _generate_from_bank(
        self, kp: KnowledgePoint, count: int
    ) -> List[Question]:
        """从内置题库随机抽题（未配置 LLM 时的降级方案）."""
        pool = [q for q in BANK if q["kp"] == kp.name] or BANK
        picked = random.sample(pool, min(count, len(pool)))
        questions = [
            Question(
                knowledge_point_id=kp.id,
                content=item["content"],
                question_type=item["type"],
                options=json.dumps(item["options"], ensure_ascii=False) if item["options"] else None,
                answer=item["answer"],
                explanation=item["explanation"],
                difficulty=item["difficulty"],
                source="bank",
            )
            for item in picked
        ]
        logger.info(f"题库生成 {len(questions)} 道题（kp={kp.name}）")
        return questions

    # ===== 批改 =====

    def grade(self, question: Question, user_answer: str) -> tuple[bool, float]:
        """批改答案，返回 (is_correct, score 0~1)."""
        answer = (user_answer or "").strip()
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

    def _keyword_grade(self, reference: str, user_answer: str) -> tuple[bool, float]:
        """关键词覆盖率评分（无 LLM 时的降级方案）."""
        keywords = [w for w in reference.split() if len(w) >= 2]
        if not keywords:
            return (len(user_answer) > 10, 0.5)
        hit = sum(1 for k in keywords if k in user_answer)
        score = round(hit / len(keywords), 2)
        return score >= 0.5, score