"""答题记录与错题模型."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Answer(Base):
    """用户答题记录."""

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 0~1 得分（简答题可能是部分得分）
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )

    question = relationship("Question", lazy="joined")

    def __repr__(self) -> str:
        return f"<Answer id={self.id} q={self.question_id} correct={self.is_correct}>"


class WrongQuestion(Base):
    """错题：答题错误后自动记录，支持复习与掌握标记."""

    __tablename__ = "wrong_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # AI 分析的错误原因（无 LLM 时为规则生成）
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 学习建议（AI 分析输出的一部分）
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 重新练习次数，用于推导"复习中"状态
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    question = relationship("Question", lazy="joined")

    def __repr__(self) -> str:
        return f"<WrongQuestion id={self.id} q={self.question_id} mastered={self.mastered}>"