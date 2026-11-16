"""知识库资料模型：用户上传的课程资料（供 RAG 检索）."""
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class KnowledgeDocument(Base, TimestampMixin):
    """上传的学习资料：正文入库，用于关键词检索与讲解引用."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), default="通用", nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 原始文件落盘路径（用于原格式预览；早期记录为空，只能看解析文本）
    stored_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 解析后的纯文本（检索与引用来源）
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<KnowledgeDocument id={self.id} title={self.title}>"
