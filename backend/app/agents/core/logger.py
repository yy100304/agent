"""Agent 执行日志：内存收集 + 可选落库.

设计目标：
1. 执行过程中随时记录结构化日志（不依赖数据库，保证 Agent 可单测）；
2. 需要时调用 flush(db, agent_task_row_id) 一次性写入 agent_execution_logs 表；
3. 同时把日志转发给项目统一的 loguru logger，便于控制台/文件排查。

注意：日志中绝不写入 API Key、完整提示词等敏感内容。
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.agents.core.schemas import AgentLogEntry
from app.core.logging import logger


# loguru 的日志级别名称与自定义 level 的映射
_LEVEL_MAP = {
    "debug": "debug",
    "info": "info",
    "warning": "warning",
    "warn": "warning",
    "error": "error",
}


class ExecutionLogger:
    """收集 Agent 执行日志，并支持批量落库."""

    def __init__(self) -> None:
        self.entries: List[AgentLogEntry] = []

    def log(
        self,
        task_id: str,
        agent_name: str,
        message: str,
        level: str = "info",
        latency_ms: int = 0,
    ) -> AgentLogEntry:
        """记录一条日志：存入内存 + 转发 loguru."""
        entry = AgentLogEntry(
            task_id=task_id,
            agent_name=agent_name,
            level=level,
            message=message,
            latency_ms=latency_ms,
        )
        self.entries.append(entry)

        # 转发到项目统一日志（控制台/文件），级别做安全映射
        log_fn = getattr(logger, _LEVEL_MAP.get(level, "info"))
        log_fn(f"[agent-core] {agent_name}: {message}")
        return entry

    def flush(self, db: Session, agent_task_id: int) -> int:
        """把内存中的日志批量写入 agent_execution_logs 表.

        参数 agent_task_id 为 agent_tasks 表的自增主键。
        返回写入条数。调用方负责 commit 之前/之后的一致性由本方法内部 commit。
        """
        from app.models.workflow import AgentExecutionLog  # 延迟导入，避免循环依赖

        if not self.entries:
            return 0

        rows = [
            AgentExecutionLog(
                agent_task_id=agent_task_id,
                step_id=None,
                agent_name=e.agent_name,
                level=e.level,
                message=e.message,
                latency_ms=e.latency_ms,
                created_at=e.created_at,
            )
            for e in self.entries
        ]
        db.add_all(rows)
        db.commit()
        return len(rows)

    def clear(self) -> None:
        """清空内存日志（复用 logger 实例时使用）."""
        self.entries.clear()

    def count(self, level: Optional[str] = None) -> int:
        if level is None:
            return len(self.entries)
        return sum(1 for e in self.entries if e.level == level)
