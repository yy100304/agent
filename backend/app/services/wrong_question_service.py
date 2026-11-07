"""错题服务：AI 分析（降级）、筛选查询、标记掌握、重新练习."""
import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import (
    Answer,
    KnowledgePoint,
    Question,
    User,
    WrongQuestion,
)
from app.services.llm_service import llm_service
from app.services.learning_service import LearningService


class WrongAnalysis(BaseModel):
    """LLM 错题分析的结构化输出."""

    reason: str
    suggestion: str


class WrongQuestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ===== 创建（答题错误后调用）=====

    def create_wrong_question(
        self, user: User, question: Question, user_answer: str
    ) -> WrongQuestion:
        """保存错题并生成错误原因分析."""
        # 若已存在同一题的错题，仅更新时间（避免重复记录）
        existing = (
            self.db.query(WrongQuestion)
            .filter(
                WrongQuestion.user_id == user.id,
                WrongQuestion.question_id == question.id,
            )
            .order_by(WrongQuestion.created_at.desc())
            .first()
        )
        if existing:
            existing.updated_at = datetime.utcnow()
            existing.mastered = False  # 又做错了，回到未掌握
            self.db.commit()
            return existing

        reason, suggestion = self._analyze_error(question, user_answer)
        wrong = WrongQuestion(
            user_id=user.id,
            question_id=question.id,
            reason=reason,
            suggestion=suggestion,
            mastered=False,
            review_count=0,
        )
        self.db.add(wrong)
        self.db.commit()
        self.db.refresh(wrong)
        logger.info(f"新增错题 user={user.id} question={question.id}")
        return wrong

    def _analyze_error(self, question: Question, user_answer: str) -> tuple[str, str]:
        """AI 分析错误原因；无 LLM 时降级为规则模板."""
        kp_name = question.knowledge_point.name if question.knowledge_point else "未知"
        if llm_service.available:
            prompt = (
                f"学科知识点：{kp_name}\n"
                f"题目：{question.content}\n"
                f"学生答案：{user_answer}\n"
                f"正确答案：{question.answer}\n"
                "请分析学生的错误原因并给出学习建议。"
                '输出 JSON：{"reason": "一句话错误原因", "suggestion": "一句话学习建议"}'
            )
            result = llm_service.structured_output(
                [{"role": "user", "content": prompt}], WrongAnalysis
            )
            if result:
                return result.reason, result.suggestion

        # 规则降级模板
        if question.question_type == "short_answer":
            reason = f"简答题回答不完整，涉及「{kp_name}」的关键概念表述不到位。"
        else:
            reason = f"对「{kp_name}」相关概念理解不准确，混淆了易错点。"
        suggestion = f"建议重新学习「{kp_name}」的相关概念，然后完成针对性练习。"
        return reason, suggestion

    # ===== 查询 =====

    @staticmethod
    def _status_of(w: WrongQuestion) -> str:
        if w.mastered:
            return "mastered"
        if w.review_count > 0:
            return "reviewing"
        return "unmastered"

    def _latest_answer_map(self, user_id: int) -> dict:
        """每个 question 的最近一次用户答案."""
        sub = (
            self.db.query(
                Answer.question_id.label("qid"),
                func.max(Answer.id).label("aid"),
            )
            .filter(Answer.user_id == user_id)
            .group_by(Answer.question_id)
            .subquery()
        )
        rows = (
            self.db.query(Answer)
            .join(sub, Answer.id == sub.c.aid)
            .all()
        )
        return {a.question_id: a for a in rows}

    def list_wrong_questions(
        self,
        user: User,
        subject: Optional[str] = None,
        knowledge_point_id: Optional[int] = None,
        status: Optional[str] = None,  # unmastered / reviewing / mastered / all
        difficulty: Optional[str] = None,
    ) -> List[dict]:
        """带筛选的错题列表（含题目信息与我的答案）."""
        query = (
            self.db.query(WrongQuestion, Question, KnowledgePoint)
            .join(Question, WrongQuestion.question_id == Question.id)
            .join(KnowledgePoint, Question.knowledge_point_id == KnowledgePoint.id)
            .filter(WrongQuestion.user_id == user.id)
        )
        if subject and subject != "all":
            query = query.filter(KnowledgePoint.subject == subject)
        if knowledge_point_id:
            query = query.filter(KnowledgePoint.id == knowledge_point_id)
        if difficulty and difficulty != "all":
            query = query.filter(Question.difficulty == difficulty)
        if status == "mastered":
            query = query.filter(WrongQuestion.mastered == True)  # noqa: E712
        elif status == "reviewing":
            query = query.filter(
                WrongQuestion.mastered == False,  # noqa: E712
                WrongQuestion.review_count > 0,
            )
        elif status == "unmastered":
            query = query.filter(
                WrongQuestion.mastered == False,  # noqa: E712
                WrongQuestion.review_count == 0,
            )

        rows = query.order_by(WrongQuestion.created_at.desc()).all()
        answer_map = self._latest_answer_map(user.id)

        items = []
        for w, q, kp in rows:
            ans = answer_map.get(q.id)
            items.append(
                {
                    "id": w.id,
                    "question_id": q.id,
                    "subject": kp.subject,
                    "knowledge_point_id": kp.id,
                    "knowledge_point_name": kp.name,
                    "content": q.content,
                    "question_type": q.question_type,
                    "difficulty": q.difficulty,
                    "my_answer": ans.user_answer if ans else "（未记录）",
                    "correct_answer": q.answer,
                    "reason": w.reason,
                    "suggestion": w.suggestion,
                    "mastered": w.mastered,
                    "review_count": w.review_count,
                    "status": self._status_of(w),
                    "created_at": w.created_at,
                    "explanation": q.explanation,
                    "options": self._parse_options(q.options),
                }
            )
        return items

    @staticmethod
    def _parse_options(raw: Optional[str]) -> Optional[list]:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def get_stats(self, user: User) -> dict:
        """错题统计：总数 / 未掌握 / 复习中 / 已掌握."""
        rows = (
            self.db.query(WrongQuestion).filter(WrongQuestion.user_id == user.id).all()
        )
        mastered = sum(1 for w in rows if w.mastered)
        reviewing = sum(1 for w in rows if not w.mastered and w.review_count > 0)
        return {
            "total": len(rows),
            "unmastered": len(rows) - mastered - reviewing,
            "reviewing": reviewing,
            "mastered": mastered,
        }

    def get_detail(self, user: User, wrong_id: int) -> Optional[dict]:
        for item in self.list_wrong_questions(user):
            if item["id"] == wrong_id:
                return item
        return None

    # ===== 操作 =====

    def mark_mastered(self, user: User, wrong_id: int) -> Optional[dict]:
        """标记已掌握：更新 wrong_questions.mastered 并温和提升画像掌握度."""
        w = (
            self.db.query(WrongQuestion)
            .filter(WrongQuestion.id == wrong_id, WrongQuestion.user_id == user.id)
            .first()
        )
        if not w:
            return None
        w.mastered = True
        w.review_count += 1
        w.updated_at = datetime.utcnow()

        # 画像增量更新（+5%，封顶 95%），不直接置 100%
        question = self.db.get(Question, w.question_id)
        new_mastery = 0.0
        if question:
            svc = LearningService(self.db)
            new_mastery = svc.increase_mastery(
                user.id, question.knowledge_point_id, delta=0.05
            )
            svc.add_record(user.id, question.knowledge_point_id, 5, source="wrong_review")
        self.db.commit()
        return {"success": True, "new_mastery": new_mastery}

    def mark_reviewed(self, user: User, wrong_id: int) -> Optional[WrongQuestion]:
        """记录一次复习（重新练习后调用），状态变为'复习中'."""
        w = (
            self.db.query(WrongQuestion)
            .filter(WrongQuestion.id == wrong_id, WrongQuestion.user_id == user.id)
            .first()
        )
        if not w:
            return None
        w.review_count += 1
        w.updated_at = datetime.utcnow()
        self.db.commit()
        return w

    def similar_questions(self, user: User, wrong_id: int, count: int = 3) -> List[Question]:
        """根据错题生成类似题（供'重新练习'）."""
        from app.services.question_service import QuestionService

        w = (
            self.db.query(WrongQuestion)
            .filter(WrongQuestion.id == wrong_id, WrongQuestion.user_id == user.id)
            .first()
        )
        if not w:
            raise ValueError("错题不存在")
        question = self.db.get(Question, w.question_id)
        if not question:
            raise ValueError("原题不存在")

        # 记录复习次数（状态 -> 复习中）
        self.mark_reviewed(user, wrong_id)

        q_service = QuestionService(self.db)
        return q_service.generate(
            user=user,
            knowledge_point_id=question.knowledge_point_id,
            subject=None,
            count=count,
            difficulty=None,
            mastery_hint=None,
        )
