"""主控 Agent（Master Agent）数据结构.

本模块只定义"数据契约"，不含执行逻辑：
- MasterStatus：主控任务的整体状态机
- MasterIntent：自然语言解析出的意图与参数
- PlanStep：任务规划中的一个步骤（由某个专业 Agent 执行）
- StepOutcome：步骤的真实执行结果（含原始 Agent 输出）

约定：字段全部可 JSON 序列化，便于落库（agent_tasks / workflows / workflow_steps）
与第九阶段工作流引擎复用。
"""
from datetime import date
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---- 意图标签（与专业 Agent 解耦，由 TaskPlanner 映射到具体 Agent）----
INTENT_ANALYSIS = "analysis"            # 学情分析
INTENT_RETRIEVAL = "retrieval"          # 知识检索 / 知识点解释
INTENT_PLAN = "plan"                    # 制定学习计划
INTENT_QUESTIONS = "questions"          # 生成练习题
INTENT_VALIDATION = "validation"        # 结果校验

ALL_INTENTS = (
    INTENT_ANALYSIS, INTENT_RETRIEVAL, INTENT_PLAN,
    INTENT_QUESTIONS, INTENT_VALIDATION,
)

# ---- 校验目标（复用 ResultValidationAgent 的 SUPPORTED_TARGETS）----
TARGET_ANALYSIS = "learning_analysis"
TARGET_PLAN = "study_plan"
TARGET_QUESTION_SET = "question_set"


class MasterStatus(str, Enum):
    """主控任务整体状态.

    在需求给定的 6 种状态（pending/running/success/partial/failed/skipped）之外，
    额外增加 need_input：缺少必要参数时向用户追问，不执行任何专业 Agent。
    """

    PENDING = "pending"
    RUNNING = "running"
    NEED_INPUT = "need_input"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepStatus(str, Enum):
    """单个步骤状态."""

    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class MasterIntent(BaseModel):
    """一次用户需求的解析结果（意图 + 参数）."""

    message: str = ""
    intents: list[str] = Field(default_factory=list)
    goal: str = ""
    subject: Optional[str] = None
    knowledge_point: Optional[str] = None
    query: str = ""
    exam_date: Optional[date] = None
    days: Optional[int] = None
    daily_minutes: Optional[int] = None
    question_count: Optional[int] = None
    question_types: list[str] = Field(default_factory=list)
    difficulty: Optional[str] = None
    # 是否要求"针对我的薄弱知识点"
    weak_points_driven: bool = False
    # 仅校验场景：待校验的目标类型
    check_targets: list[str] = Field(default_factory=list)
    # 缺少的必要参数（→ 向用户追问）
    missing_params: list[str] = Field(default_factory=list)
    # 采用的合理默认值（如实告知用户，不擅自假装是用户要求）
    assumptions: list[str] = Field(default_factory=list)
    # 解析来源：rule / llm / fallback
    source: str = "rule"

    def has(self, intent: str) -> bool:
        return intent in self.intents


class PlanStep(BaseModel):
    """任务规划中的一个执行步骤."""

    order: int
    agent: str                      # 注册表中的专业 Agent 名称
    action: str                     # 人类可读动作，如"分析学情"
    purpose: str = ""               # 该步骤要解决的问题
    depends_on: list[str] = Field(default_factory=list)   # 依赖的 Agent 名称
    optional: bool = False          # 可选步骤：失败不影响整体可用性
    target: Optional[str] = None    # 校验步骤的校验目标

    def public(self) -> dict:
        """供接口/前端展示的计划视图."""
        return {
            "order": self.order,
            "agent": self.agent,
            "action": self.action,
            "purpose": self.purpose,
            "depends_on": list(self.depends_on),
            "optional": self.optional,
            "target": self.target,
        }


class StepOutcome(BaseModel):
    """一个步骤的真实执行结果（保留原始 Agent 输出）."""

    order: int
    agent: str
    action: str
    status: str = StepStatus.PENDING.value
    success: bool = False
    task_id: str = ""
    execution_time: float = 0.0
    error: str = ""
    note: str = ""
    input_summary: dict = Field(default_factory=dict)
    result: Optional[Any] = None

    def public(self, include_result: bool = True) -> dict:
        data = {
            "order": self.order,
            "agent": self.agent,
            "action": self.action,
            "status": self.status,
            "success": self.success,
            "task_id": self.task_id,
            "execution_time": self.execution_time,
            "note": self.note,
            "error": self.error,
            "input_summary": self.input_summary,
        }
        if include_result:
            data["result"] = self.result
        return data


def compact(data: Any, max_len: int = 120) -> dict:
    """把 Agent 输入压成可落库的摘要（避免把学情全文写进步骤记录）.

    - 简单标量原样保留（长字符串截断）；
    - 字典/列表只保留规模信息（键名、长度），不复制整份内容。
    """
    if not isinstance(data, dict):
        return {"value": _truncate(data, max_len)}

    summary: dict = {}
    for key, value in data.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = _truncate(value, max_len)
        elif isinstance(value, dict):
            summary[key] = {"type": "dict", "keys": sorted(map(str, value.keys()))[:12]}
        elif isinstance(value, (list, tuple, set)):
            summary[key] = {"type": "list", "size": len(value)}
        else:
            summary[key] = {"type": type(value).__name__}
    return summary


def _truncate(value: Any, max_len: int) -> Any:
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "…"
    return value
