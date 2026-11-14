"""Agents - 多智能体核心模块（编排 / 调度 / 执行 / 验证）."""
from app.agents.base import AgentProfile, DispatchResult, RunContext, ValidationResult
from app.agents.registry import ROUTES, agent_registry
from app.agents.dispatcher import LABELS, LABEL_NAMES, dispatcher
from app.agents.validator import output_validator
from app.agents.executor import WorkflowExecutor

__all__ = [
    "AgentProfile",
    "DispatchResult",
    "RunContext",
    "ValidationResult",
    "AgentRegistry",
    "agent_registry",
    "ROUTES",
    "LABELS",
    "LABEL_NAMES",
    "dispatcher",
    "output_validator",
    "WorkflowExecutor",
]