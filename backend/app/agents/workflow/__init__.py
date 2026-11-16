"""第九阶段：工作流引擎与 Self-Loop 自我修正机制.

对外暴露：
- WorkflowEngine：依赖执行 + 校验 + 有限次修正
- SelfLoopPolicy / RepairAction / Decision：修正策略与动作
- FailureClassifier / Failure：失败分类
- SideEffectConfirmer：写入确认（幂等保障）
- config：集中配置（修正次数等）
"""
from app.agents.workflow.engine import RunState, WorkflowEngine
from app.agents.workflow.failure import Failure, FailureClassifier
from app.agents.workflow.recovery import ConfirmResult, SideEffectConfirmer
from app.agents.workflow.self_loop import Decision, RepairAction, SelfLoopPolicy

__all__ = [
    "WorkflowEngine",
    "RunState",
    "FailureClassifier",
    "Failure",
    "SelfLoopPolicy",
    "RepairAction",
    "Decision",
    "SideEffectConfirmer",
    "ConfirmResult",
]
