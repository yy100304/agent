"""题目模型."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

# 题目类型
QUESTION_TYPES = ("single_choice", "multiple_choice", "true_false", "short_answer")
# 难度
DIFFICULTIES = ("easy", "medium", "hard")


class Question(Base):
    """题目：AI 生成或内置题库."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(
        String(16), default="single_choice", nullable=False
    )
    # 单选题选项，JSON 数组字符串，如 '["选项A","选项B"]'
    options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 单选/判断存 "A"/"B"... 或 "true"/"false"；简答存参考答案关键词
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(
        String(16), default="medium", nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(16), default="bank", nullable=False
    )  # bank（内置题库）/ ai（LLM 生成）
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    knowledge_point = relationship("KnowledgePoint", lazy="joined")

    def __repr__(self) -> str:
        return f"<Question id={self.id} type={self.question_type}>"