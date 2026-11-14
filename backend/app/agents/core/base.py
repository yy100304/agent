"""统一 Agent 基类与执行上下文.

核心思想：
- 子类只需要实现 `execute(task, context)` 这一件事；
- 状态流转、计时、异常捕获、超时控制、重试、日志记录全部由 `run()` 统一处理。

这样保证所有 Agent 的对外行为一致，主控 Agent / 工作流引擎无需关心细节。
"""
import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.core.logger import ExecutionLogger
from app.agents.core.schemas import AgentResult, AgentStatus, AgentTask


@dataclass
class AgentContext:
    """Agent 执行时共享的上下文.

    - db：数据库会话（可选，纯计算型 Agent 可不需要）
    - shared：前序 Agent 的结果，key 为 Agent 名称，供后续 Agent 读取
    - request：本次用户任务的原始输入
    - extra：任意附加信息（预留）
    """

    user_id: int
    username: str
    db: Optional[Session] = None
    shared: dict[str, Any] = field(default_factory=dict)
    request: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def get_shared(self, agent_name: str, default: Any = None) -> Any:
        """读取某个前序 Agent 的结果."""
        return self.shared.get(agent_name, default)


class BaseAgent(ABC):
    """所有新体系 Agent 的基类.

    子类必须声明：
    - name        唯一名称（注册表键）
    - description 一句话职责
    - task_type   处理的任务类型
    并实现 execute()。
    """

    # ---- 子类通过类属性声明身份 ----
    name: str = "base_agent"
    description: str = "基础 Agent"
    task_type: str = "generic"

    # ---- 执行策略（子类可覆盖）----
    max_retries: int = 0        # 失败后额外重试次数（总执行 = 1 + max_retries）
    timeout_s: float = 60.0     # 单次执行超时（秒）

    def __init__(self, logger: Optional[ExecutionLogger] = None) -> None:
        self.logger = logger or ExecutionLogger()

    # ==================== 子类实现 ====================

    @abstractmethod
    async def execute(self, task: AgentTask, context: AgentContext) -> Any:
        """执行真正的业务逻辑，返回可序列化结果（dict/list/str/number）.

        约定：
        - 不要在这里做 try/except 兜底（交给 run 统一处理）；
        - 需要的数据从 task.input_data / context 读取；
        - 结果请尽量返回 dict，便于后续 Agent 与前端消费。
        """
        raise NotImplementedError

    # ==================== 统一执行接口 ====================

    async def run(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """统一执行入口：状态管理 + 计时 + 超时 + 重试 + 日志 + 异常兜底.

        永远不向外抛异常：失败也返回 AgentResult(success=False)，
        避免单个 Agent 崩溃拖垮整个工作流。
        """
        start = time.time()
        task.status = AgentStatus.RUNNING
        self.logger.log(
            task.task_id, self.name,
            f"开始执行（task_type={task.task_type}）",
        )

        attempts = 0
        last_error = ""

        while attempts <= self.max_retries:
            attempts += 1
            try:
                result = await asyncio.wait_for(
                    self.execute(task, context), timeout=self.timeout_s
                )
                cost = round(time.time() - start, 4)
                task.status = AgentStatus.SUCCESS
                task.result = result
                task.completed_at = datetime.utcnow()
                self.logger.log(
                    task.task_id, self.name,
                    f"执行成功（第 {attempts} 次尝试，耗时 {cost}s）",
                    latency_ms=int(cost * 1000),
                )
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    result=result,
                    execution_time=cost,
                    metadata={"attempts": attempts},
                )
            except asyncio.TimeoutError:
                last_error = f"执行超时（超过 {self.timeout_s}s）"
                self.logger.log(
                    task.task_id, self.name, last_error, level="warning"
                )
            except Exception as e:  # noqa: BLE001 - 统一兜底，不让异常外泄
                last_error = f"{type(e).__name__}: {e}"
                self.logger.log(
                    task.task_id, self.name,
                    f"执行异常：{last_error}", level="error",
                )

            # 还有重试机会则标记 retrying，否则跳出
            if attempts <= self.max_retries:
                task.status = AgentStatus.RETRYING
                self.logger.log(
                    task.task_id, self.name,
                    f"准备第 {attempts + 1} 次重试", level="warning",
                )
            else:
                break

        # 所有尝试均失败
        cost = round(time.time() - start, 4)
        task.status = AgentStatus.FAILED
        task.error = last_error
        task.completed_at = datetime.utcnow()
        self.logger.log(
            task.task_id, self.name,
            f"执行失败（共 {attempts} 次尝试）：{last_error}", level="error",
        )
        return AgentResult(
            agent_name=self.name,
            success=False,
            error=last_error,
            execution_time=cost,
            metadata={"attempts": attempts},
        )

    # ==================== 供注册表/接口展示 ====================

    def describe(self) -> dict:
        """Agent 元信息（不含提示词，供 /api/agent/agents 与前端展示）."""
        return {
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type,
            "max_retries": self.max_retries,
            "timeout_s": self.timeout_s,
        }
