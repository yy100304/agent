"""新 Multi-Agent 系统数据模型：任务 / 工作流 / 步骤 / 日志 / 评估.

设计原则（务必遵守）：
1. 全部为**新增表**，不改动任何已有业务表，`create_all` 会自动创建，不重建数据库。
2. 所有表都通过 agent_tasks 关联用户，保证不同用户数据隔离。
3. 对外暴露用业务键 task_id(uuid)，表间外键用自增主键 id，二者职责分离。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class AgentTaskRecord(Base, TimestampMixin):
    """用户提交的一次 Agent 任务（对应 /api/agent/tasks）."""

    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 对外业务键（uuid 字符串），前端用它访问任务详情
    task_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    task_type: Mapped[str] = mapped_column(
        String(32), default="generic", nullable=False
    )
    # 原始输入（用户目标/考试时间/每日时长/知识点等），JSON 文本
    input_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False
    )
    # 最终结果（汇总后的 JSON 文本）
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class WorkflowRecord(Base, TimestampMixin):
    """一次任务对应的工作流实例."""

    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_task_id: Mapped[int] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False
    )
    # 任务拆解计划（含步骤与依赖），JSON 文本
    plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class WorkflowStepRecord(Base, TimestampMixin):
    """工作流中的单个步骤（由某个 Agent 执行）."""

    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 依赖的前置步骤/Agent，JSON 数组文本，如 '["learning_analysis"]'
    depends_on: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AgentExecutionLog(Base, TimestampMixin):
    """Agent 细粒度执行日志（ExecutionLogger.flush 写入）."""

    __tablename__ = "agent_execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_task_id: Mapped[int] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AgentEvaluation(Base, TimestampMixin):
    """Self-Loop 每轮验证记录（Evaluation Agent 写入）."""

    __tablename__ = "agent_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_task_id: Mapped[int] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 各项检查明细，JSON 文本
    checks_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
