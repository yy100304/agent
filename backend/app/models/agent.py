"""多智能体运行数据模型：执行轨迹与对话历史."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class AgentRun(Base, TimestampMixin):
    """一次完整的 Agent 工作流执行记录（可回放、可统计）."""

    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_user_session", "user_id", "session_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        String(64), index=True, nullable=False
    )  # 冗余存 username，避免跨表 join
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # 调度标签：knowledge_explain / quiz_coaching / notes_organizing / multi_task / non_learning
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    # 本次执行涉及的子 Agent，JSON 数组字符串，如 '["tutor","validator"]'
    agent_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Self-Loop 实际执行轮数
    attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # 最终验证是否通过
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 完整执行轨迹（SSE 事件流 JSON），供回放
    trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AgentMessage(Base):
    """Agent 对话历史（用于上下文注入）."""

    __tablename__ = "agent_messages"
    __table_args__ = (Index("ix_agent_messages_session", "session_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )