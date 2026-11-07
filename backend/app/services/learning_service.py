"""学习数据服务：画像读写、掌握度增量更新、学习统计与错题分析.

该模块是 Agent 的核心数据能力：
- get_learning_profile 数据来源
- analyze_learning 数据来源（含错题分布）
- Dashboard / 错题复习都会调用此服务更新画像
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import (
    Answer,
    KnowledgePoint,
    LearningProfile,
    LearningRecord,
    Question,
    StudyTask,
    StudyPlan,
    User,
    WrongQuestion,
)

# 难度权重：难题答对加成更高，答错扣得更少
DIFFICULTY_WEIGHT = {"easy": 0.9, "medium": 1.0, "hard": 1.15}


class LearningService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ===== 画像 =====

    def get_profiles(self, user_id: int) -> List[LearningProfile]:
        return (
            self.db.query(LearningProfile)
            .filter(LearningProfile.user_id == user_id)
            .all()
        )

    def get_or_create_profile(
        self, user_id: int, knowledge_point_id: int
    ) -> LearningProfile:
        profile = (
            self.db.query(LearningProfile)
            .filter(
                LearningProfile.user_id == user_id,
                LearningProfile.knowledge_point_id == knowledge_point_id,
            )
            .first()
        )
        if not profile:
            profile = LearningProfile(
                user_id=user_id,
                knowledge_point_id=knowledge_point_id,
                mastery_score=0.0,
                confidence=0,
            )
            self.db.add(profile)
        return profile

    def update_mastery_on_answer(
        self, user_id: int, knowledge_point_id: int, is_correct: bool, difficulty: str
    ) -> float:
        """答题后增量更新掌握度.

        公式：mastery = 0.6 * 历史掌握度 + 0.4 * 难度加权表现
        """
        profile = self.get_or_create_profile(user_id, knowledge_point_id)
        weight = DIFFICULTY_WEIGHT.get(difficulty, 1.0)
        performance = (1.0 if is_correct else 0.0) * weight
        performance = min(performance, 1.0)

        old = profile.mastery_score
        new_mastery = round(0.6 * old + 0.4 * performance, 4)
        new_mastery = max(0.0, min(new_mastery, 1.0))

        profile.mastery_score = new_mastery
        profile.confidence += 1
        profile.last_updated = datetime.utcnow()
        self.db.commit()

        logger.info(
            f"画像更新 user={user_id} kp={knowledge_point_id} "
            f"{old:.2f} -> {new_mastery:.2f} (correct={is_correct})"
        )
        return new_mastery

    def increase_mastery(
        self, user_id: int, knowledge_point_id: int, delta: float = 0.05
    ) -> float:
        """错题复习等场景的温和增量更新（不会直接设成 100%）."""
        profile = self.get_or_create_profile(user_id, knowledge_point_id)
        new_mastery = min(profile.mastery_score + delta, 0.95)
        profile.mastery_score = round(new_mastery, 4)
        profile.confidence += 1
        profile.last_updated = datetime.utcnow()
        self.db.commit()
        return new_mastery

    # ===== 学习记录 =====

    def add_record(
        self,
        user_id: int,
        knowledge_point_id: Optional[int],
        study_minutes: int,
        source: str = "practice",
    ) -> LearningRecord:
        mastery = 0.0
        if knowledge_point_id:
            profile = self.get_or_create_profile(user_id, knowledge_point_id)
            mastery = profile.mastery_score
        record = LearningRecord(
            user_id=user_id,
            knowledge_point_id=knowledge_point_id,
            study_minutes=study_minutes,
            mastery_score=mastery,
            source=source,
        )
        self.db.add(record)
        self.db.commit()
        return record

    # ===== 统计（供 Dashboard / Agent 使用）=====

    def today_minutes(self, user_id: int) -> int:
        start = datetime.combine(date.today(), datetime.min.time())
        value = (
            self.db.query(func.coalesce(func.sum(LearningRecord.study_minutes), 0))
            .filter(
                LearningRecord.user_id == user_id,
                LearningRecord.created_at >= start,
            )
            .scalar()
        )
        return int(value or 0)

    def recent_accuracy(self, user_id: int, limit: int = 20) -> Optional[float]:
        """最近 N 题的正确率，无答题记录返回 None."""
        rows = (
            self.db.query(Answer.is_correct)
            .filter(Answer.user_id == user_id)
            .order_by(Answer.created_at.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            return None
        correct = sum(1 for (c,) in rows if c)
        return round(correct / len(rows), 4)

    def accuracy_by_day(self, user_id: int, days: int = 7) -> Dict[date, Optional[float]]:
        """最近 N 天每日正确率（无答题的日期为 None）."""
        start = date.today() - timedelta(days=days - 1)
        rows = (
            self.db.query(
                func.date(Answer.created_at).label("d"),
                Answer.is_correct,
            )
            .filter(
                Answer.user_id == user_id,
                func.date(Answer.created_at) >= start,
            )
            .all()
        )
        grouped: Dict[date, List[bool]] = {}
        for d, correct in rows:
            grouped.setdefault(d, []).append(bool(correct))
        return {
            start + timedelta(days=i): (
                round(sum(v) / len(v), 4) if (v := grouped.get(start + timedelta(days=i))) else None
            )
            for i in range(days)
        }

    def minutes_by_day(self, user_id: int, days: int = 7) -> Dict[date, int]:
        start = date.today() - timedelta(days=days - 1)
        rows = (
            self.db.query(
                func.date(LearningRecord.created_at).label("d"),
                func.sum(LearningRecord.study_minutes),
            )
            .filter(
                LearningRecord.user_id == user_id,
                func.date(LearningRecord.created_at) >= start,
            )
            .group_by("d")
            .all()
        )
        mapping = {d: int(m or 0) for d, m in rows}
        return {
            start + timedelta(days=i): mapping.get(start + timedelta(days=i), 0)
            for i in range(days)
        }

    def weak_points(self, user_id: int, threshold: float = 0.65) -> List[str]:
        """掌握度低于阈值的知识点（Agent / Dashboard 使用）."""
        profiles = (
            self.db.query(LearningProfile)
            .filter(LearningProfile.user_id == user_id)
            .order_by(LearningProfile.mastery_score.asc())
            .all()
        )
        return [
            p.knowledge_point.name
            for p in profiles
            if p.mastery_score < threshold and p.confidence > 0
        ]

    def get_learning_profile_summary(self, user_id: int) -> dict:
        """Tool: get_learning_profile 的数据来源."""
        profiles = self.get_profiles(user_id)
        mastery_map = {
            p.knowledge_point.name: round(p.mastery_score, 2)
            for p in profiles
            if p.confidence > 0
        }
        accuracy = self.recent_accuracy(user_id)
        wrong_total = (
            self.db.query(func.count(WrongQuestion.id))
            .filter(WrongQuestion.user_id == user_id)
            .scalar()
        )
        total_minutes = (
            self.db.query(func.coalesce(func.sum(LearningRecord.study_minutes), 0))
            .filter(LearningRecord.user_id == user_id)
            .scalar()
        )
        recent_records = (
            self.db.query(LearningRecord)
            .filter(LearningRecord.user_id == user_id)
            .order_by(LearningRecord.created_at.desc())
            .limit(10)
            .all()
        )
        return {
            "mastery": mastery_map,
            "recent_accuracy": accuracy,
            "wrong_question_count": int(wrong_total or 0),
            "total_study_minutes": int(total_minutes or 0),
            "recent_records": [
                {
                    "date": r.created_at.isoformat(),
                    "minutes": r.study_minutes,
                    "source": r.source,
                }
                for r in recent_records
            ],
        }

    def analyze_learning(self, user_id: int) -> dict:
        """Tool: analyze_learning 的数据来源（含错题分布，供 Agent 联动）."""
        # 各知识点错题分布
        wrong_rows = (
            self.db.query(
                KnowledgePoint.name,
                func.count(WrongQuestion.id),
            )
            .join(Question, WrongQuestion.question_id == Question.id)
            .join(KnowledgePoint, Question.knowledge_point_id == KnowledgePoint.id)
            .filter(WrongQuestion.user_id == user_id, WrongQuestion.mastered == False)  # noqa: E712
            .group_by(KnowledgePoint.name)
            .all()
        )
        wrong_by_kp = {name: int(cnt) for name, cnt in wrong_rows}

        # 任务完成率（最近 7 天）
        start = date.today() - timedelta(days=6)
        tasks = (
            self.db.query(StudyTask)
            .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
            .filter(
                StudyPlan.user_id == user_id,
                StudyTask.scheduled_date >= start,
            )
            .all()
        )
        task_total = len(tasks)
        task_done = sum(1 for t in tasks if t.completed)

        total_questions = (
            self.db.query(func.count(Answer.id))
            .filter(Answer.user_id == user_id)
            .scalar()
        )
        accuracy = self.recent_accuracy(user_id)

        # 薄弱知识点：结合掌握度与错题数排序
        weak = self.weak_points(user_id)
        # 错题多的知识点优先
        weak_sorted = sorted(set(weak + list(wrong_by_kp.keys())), key=lambda n: -(wrong_by_kp.get(n, 0)))

        strong = [
            p.knowledge_point.name
            for p in self.get_profiles(user_id)
            if p.mastery_score >= 0.85 and p.confidence >= 3
        ]

        return {
            # minutes_by_day(30) 已含今日，不可再叠加 today_minutes（否则重复计数）
            "total_study_minutes": sum(self.minutes_by_day(user_id, 30).values()),
            "recent_accuracy": accuracy,
            "total_questions": int(total_questions or 0),
            "task_total": task_total,
            "task_completed": task_done,
            "task_completion_rate": round(task_done / task_total, 4) if task_total else None,
            "wrong_question_distribution": wrong_by_kp,
            "weak_points": weak_sorted,
            "strong_points": strong,
        }
