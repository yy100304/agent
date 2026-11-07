"""Dashboard 服务：基于真实学习数据构建学习看板."""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import KnowledgePoint, LearningProfile, StudyPlan, StudyTask, User
from app.services.learning_service import LearningService


def _greeting_for(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 11:
        return "早上好"
    if 11 <= hour < 14:
        return "中午好"
    if 14 <= hour < 18:
        return "下午好"
    if 18 <= hour < 23:
        return "晚上好"
    return "夜深了"


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.learning = LearningService(db)

    def build_summary(self, user: User) -> dict:
        today = date.today()
        now = datetime.now()

        # ---- 学习第 N 天 ----
        created = user.created_at.date() if user.created_at else today
        study_day_count = max((today - created).days + 1, 1)

        # ---- 考试倒计时（最近的进行中计划）----
        exam = None
        plan = (
            self.db.query(StudyPlan)
            .filter(
                StudyPlan.user_id == user.id,
                StudyPlan.status == "active",
                StudyPlan.exam_date >= today,
            )
            .order_by(StudyPlan.exam_date.asc())
            .first()
        )
        if plan and plan.exam_date:
            exam = {
                "plan_id": plan.id,
                "subject": plan.subject,
                "title": plan.title,
                "exam_date": plan.exam_date,
                "days_left": (plan.exam_date - today).days,
            }

        # ---- 今日任务 ----
        task_rows = (
            self.db.query(StudyTask, KnowledgePoint)
            .outerjoin(KnowledgePoint, StudyTask.knowledge_point_id == KnowledgePoint.id)
            .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
            .filter(
                StudyPlan.user_id == user.id,
                StudyTask.scheduled_date == today,
            )
            .order_by(StudyTask.completed.asc(), StudyTask.id.asc())
            .all()
        )
        today_tasks = [
            {
                "id": t.id,
                "title": t.title,
                "knowledge_point_id": t.knowledge_point_id,
                "knowledge_point_name": kp.name if kp else None,
                "estimated_minutes": t.estimated_minutes,
                "completed": t.completed,
            }
            for t, kp in task_rows
        ]
        task_total = len(today_tasks)
        task_done = sum(1 for t in today_tasks if t["completed"])

        # ---- 数据概览 ----
        today_minutes = self.learning.today_minutes(user.id)
        recent_accuracy = self.learning.recent_accuracy(user.id)
        weak_points = self.learning.weak_points(user.id)

        # ---- 趋势 ----
        minutes_map = self.learning.minutes_by_day(user.id, 7)
        accuracy_map = self.learning.accuracy_by_day(user.id, 7)
        study_time_trend = [
            {"date": d, "value": v} for d, v in minutes_map.items()
        ]
        accuracy_trend = [
            {"date": d, "value": v} for d, v in accuracy_map.items()
        ]

        # ---- Agent 建议（基于真实数据，规则生成；接入 LLM 后可升级）----
        suggestion = self._build_suggestion(user.id, weak_points, recent_accuracy)

        return {
            "greeting": f"{_greeting_for(now)}，{user.username}",
            "username": user.username,
            "study_day_count": study_day_count,
            "exam": exam,
            "today_tasks": today_tasks,
            "stats": {
                "today_minutes": today_minutes,
                "today_task_total": task_total,
                "today_task_completed": task_done,
                "today_completion_rate": round(task_done / task_total, 4) if task_total else 0.0,
                "recent_accuracy": recent_accuracy,
                "weak_points": weak_points[:4],
            },
            "study_time_trend": study_time_trend,
            "accuracy_trend": accuracy_trend,
            "agent_suggestion": suggestion,
        }

    def _build_suggestion(
        self, user_id: int, weak_points: list, recent_accuracy: Optional[float]
    ) -> dict:
        """基于画像 + 错题分布生成 Agent 建议（Agent 联动数据能力的展示）."""
        analysis = self.learning.analyze_learning(user_id)
        wrong_dist = analysis.get("wrong_question_distribution", {})

        # 最薄弱知识点 = 掌握度最低（有答题记录）
        profile = (
            self.db.query(LearningProfile, KnowledgePoint)
            .join(KnowledgePoint, LearningProfile.knowledge_point_id == KnowledgePoint.id)
            .filter(
                LearningProfile.user_id == user_id,
                LearningProfile.confidence > 0,
            )
            .order_by(LearningProfile.mastery_score.asc())
            .first()
        )

        if profile:
            p, kp = profile
            pct = round(p.mastery_score * 100)
            wrong_cnt = wrong_dist.get(kp.name, 0)
            parts = [f"根据你最近的学习数据，「{kp.name}」的掌握度为 {pct}%"]
            if wrong_cnt:
                parts.append(f"累计错题 {wrong_cnt} 道")
            if recent_accuracy is not None:
                parts.append(f"最近正确率 {round(recent_accuracy * 100)}%")
            text = "，".join(parts) + f"。建议今天增加 20 分钟「{kp.name}」专项练习。"
            return {
                "text": text,
                "weak_knowledge_point_id": kp.id,
                "weak_knowledge_point_name": kp.name,
            }

        if weak_points:
            name = weak_points[0]
            return {
                "text": f"你在「{name}」上还有提升空间，建议今天完成一组针对性练习。",
                "weak_knowledge_point_id": None,
                "weak_knowledge_point_name": name,
            }

        return {
            "text": "暂时还没有足够的学习数据，先完成一组练习，我会据此为你规划学习任务。",
            "weak_knowledge_point_id": None,
            "weak_knowledge_point_name": None,
        }
