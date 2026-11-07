"""知识点模型."""
from typing import Optional

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class KnowledgePoint(Base, TimestampMixin):
    """知识点：按学科组织."""

    __tablename__ = "knowledge_points"
    __table_args__ = (UniqueConstraint("subject", "name", name="uq_kp_subject_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(
        String(16), default="medium", nullable=False
    )  # easy / medium / hard

    def __repr__(self) -> str:
        return f"<KnowledgePoint id={self.id} {self.subject}/{self.name}>"