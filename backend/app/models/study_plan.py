"""学习计划与学习任务模型."""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class StudyPlan(Base, TimestampMixin):
    """学习计划."""

    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    exam_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="active", nullable=False
    )  # active / completed / archived
    # Agent 调整记录（JSON 文本），前端展示"为什么调整"
    adjustment_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tasks: Mapped[list["StudyTask"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<StudyPlan id={self.id} {self.title} status={self.status}>"


class StudyTask(Base, TimestampMixin):
    """学习任务：属于某个计划，安排在某天."""

    __tablename__ = "study_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("study_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    plan: Mapped[StudyPlan] = relationship(back_populates="tasks")

    def __repr__(self) -> str:
        return f"<StudyTask id={self.id} {self.title} done={self.completed}>"