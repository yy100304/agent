"""新 Multi-Agent 系统基础层（与旧 agents/ 体系完全独立并行）.

对外暴露：
- 数据结构：AgentStatus / AgentTask / AgentResult / AgentLogEntry
- 执行基类：BaseAgent / AgentContext
- 日志：ExecutionLogger
- 注册：CoreAgentRegistry / core_registry
- 示例 Agent：EchoAgent / FlakyAgent / SlowAgent（仅冒烟测试用）
"""
from app.agents.core.base import AgentContext, BaseAgent
from app.agents.core.demo_agent import EchoAgent, FlakyAgent, SlowAgent
from app.agents.core.logger import ExecutionLogger
from app.agents.core.registry import CoreAgentRegistry, core_registry
from app.agents.core.schemas import AgentLogEntry, AgentResult, AgentStatus, AgentTask

__all__ = [
    # 数据结构
    "AgentStatus",
    "AgentTask",
    "AgentResult",
    "AgentLogEntry",
    # 执行基类
    "BaseAgent",
    "AgentContext",
    # 日志
    "ExecutionLogger",
    # 注册
    "CoreAgentRegistry",
    "core_registry",
    # 示例 Agent
    "EchoAgent",
    "FlakyAgent",
    "SlowAgent",
]
