"""新体系 Agent 注册表（独立于旧 agents/registry.py）.

单一事实来源：主控 Agent 与工作流引擎通过名称查找已注册的专业 Agent。
"""
from typing import Dict, List, Optional

from app.agents.core.base import BaseAgent


class CoreAgentRegistry:
    """核心 Agent 注册表：register / get / require / list_all / to_dicts."""

    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """注册一个 Agent，名称重复则报错（避免静默覆盖）."""
        if not getattr(agent, "name", ""):
            raise ValueError("Agent 必须声明 name")
        if agent.name in self._agents:
            raise ValueError(f"Agent 重复注册: {agent.name}")
        self._agents[agent.name] = agent

    def unregister(self, name: str) -> None:
        self._agents.pop(name, None)

    def get(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    def require(self, name: str) -> BaseAgent:
        agent = self._agents.get(name)
        if agent is None:
            raise KeyError(f"未注册的 Agent: {name}")
        return agent

    def list_all(self) -> List[BaseAgent]:
        return list(self._agents.values())

    def names(self) -> List[str]:
        return list(self._agents.keys())

    def to_dicts(self) -> List[dict]:
        return [a.describe() for a in self._agents.values()]


# 模块级单例（供全局注册/调度使用）
core_registry = CoreAgentRegistry()
