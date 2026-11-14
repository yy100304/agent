"""新 Multi-Agent 系统统一数据结构（与旧 agents/base.py 完全独立）.

本模块只定义"数据契约"，不含任何执行逻辑：
- AgentStatus：子任务/Agent 的执行状态机
- AgentTask：交给某个 Agent 的统一输入
- AgentResult：Agent 的统一输出
- AgentLogEntry：一条结构化执行日志

约定：所有新 Agent 的输入输出都走这里，保证主控 Agent 与工作流引擎
可以一致地调度、序列化和落库，而不关心具体 Agent 的内部实现。
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent 执行状态（字符串枚举，便于直接落库/序列化）."""

    PENDING = "pending"     # 已创建，等待执行
    RUNNING = "running"     # 执行中
    SUCCESS = "success"     # 执行成功
    FAILED = "failed"       # 执行失败（含超过重试次数）
    RETRYING = "retrying"   # 某次失败后、下一次重试之前


class AgentTask(BaseModel):
    """一次交给 Agent 的子任务（统一输入）.

    字段与需求文档一致：task_id / user_id / task_type / input_data /
    status / result / error / created_at / completed_at。
    """

    task_id: str
    user_id: int
    task_type: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    status: AgentStatus = AgentStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class AgentResult(BaseModel):
    """Agent 的统一输出.

    - success：是否成功
    - result：成功时的业务结果（可序列化为 dict/list）
    - error：失败原因（不直接暴露给终端用户，由上层做脱敏）
    - execution_time：本次执行总耗时（秒，含重试）
    - metadata：附加信息（如尝试次数、命中数据条数等）
    """

    agent_name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentLogEntry(BaseModel):
    """一条结构化的 Agent 执行日志（可落库到 agent_execution_logs）."""

    task_id: str
    agent_name: str
    level: str = "info"          # info / warning / error / debug
    message: str
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
