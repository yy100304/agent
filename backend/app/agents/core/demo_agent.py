"""示例 Agent（仅用于第二阶段架构冒烟测试，非业务 Agent）.

- EchoAgent：成功路径，回显输入
- FlakyAgent：前 N 次失败后成功，验证"重试 + retrying 状态"
- SlowAgent：执行超时，验证"超时控制 + failed 状态"
"""
import asyncio
from typing import Any

from app.agents.core.base import AgentContext, BaseAgent
from app.agents.core.schemas import AgentTask


class EchoAgent(BaseAgent):
    """回显输入的最小 Agent."""

    name = "echo"
    description = "示例 Agent：回显输入，用于架构冒烟测试"
    task_type = "demo"
    max_retries = 0
    timeout_s = 10.0

    async def execute(self, task: AgentTask, context: AgentContext) -> Any:
        await asyncio.sleep(0.02)  # 模拟少量耗时
        text = task.input_data.get("text", "")
        return {"echo": text, "user": context.username, "task_id": task.task_id}


class FlakyAgent(BaseAgent):
    """前 fail_times 次必定失败，之后成功的 Agent，用于验证重试逻辑."""

    name = "flaky"
    description = "示例 Agent：前 N 次失败后成功，用于验证重试机制"
    task_type = "demo"
    max_retries = 2
    timeout_s = 10.0

    def __init__(self, fail_times: int = 1, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._fail_times = fail_times
        self._calls = 0

    async def execute(self, task: AgentTask, context: AgentContext) -> Any:
        self._calls += 1
        if self._calls <= self._fail_times:
            raise RuntimeError(f"模拟第 {self._calls} 次执行失败")
        return {"ok": True, "calls": self._calls}


class SlowAgent(BaseAgent):
    """执行时间超过 timeout_s 的 Agent，用于验证超时控制."""

    name = "slow"
    description = "示例 Agent：执行超时，用于验证超时控制"
    task_type = "demo"
    max_retries = 0
    timeout_s = 0.1

    async def execute(self, task: AgentTask, context: AgentContext) -> Any:
        await asyncio.sleep(0.5)
        return {"should_not_reach": True}
