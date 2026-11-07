"""学习记录与学习画像模型."""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class LearningRecord(Base):
    """学习行为记录：来源可以是任务、练习、错题复习等."""

    __tablename__ = "learning_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True
    )
    study_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 记录时的掌握度快照（0~1）
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # task / practice / wrong_review / agent
    source: Mapped[str] = mapped_column(String(32), default="practice", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )


class LearningProfile(Base):
    """学习画像：用户对每个知识点的掌握度（Agent 的核心数据源）.

    注意：该表不再有独立的前端页面展示，
    但 Agent / Dashboard / 错题复习都会读写此表。
    """

    __tablename__ = "learning_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_profile_user_kp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # 置信度：参与计算的答题/学习次数，次数越多掌握度越可信
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    knowledge_point = relationship("KnowledgePoint", lazy="joined")
