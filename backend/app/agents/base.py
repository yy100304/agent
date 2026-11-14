"""多智能体基础类型：AgentProfile（团队定义）与运行上下文."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentProfile:
    """Agent 团队成员的声明式定义.

    注册进 AgentRegistry 即成为平台可调度的执行单元，
    包含：身份、角色提示词、可用工具、Self-Loop 重试策略。
    """

    id: str                          # 唯一标识，如 "tutor"
    name: str                        # 展示名，如 "知识点讲解 Agent"
    banner: str                      # 输出横幅，如 "🧑‍🏫 知识点讲解"
    description: str                 # 一句话职责（前端团队面板展示）
    role_prompt: str                 # 完整角色系统提示词
    tools: list[str] = field(default_factory=list)   # 可用工具名列表
    max_retries: int = 2             # Self-Loop 最大重试次数（总执行 = 1 + max_retries）
    temperature: float = 0.5
    # 输出结构校验关键词（Validator 规则层使用）：必须全部出现才算结构完整
    structure_keywords: list[str] = field(default_factory=list)
    min_output_chars: int = 40       # 最短输出长度（规则校验）

    def to_dict(self) -> dict:
        """团队定义对外展示（不含完整提示词，避免泄露）."""
        return {
            "id": self.id,
            "name": self.name,
            "banner": self.banner,
            "description": self.description,
            "tools": self.tools,
            "max_retries": self.max_retries,
        }


@dataclass
class RunContext:
    """一次执行中传递给 Agent / 工具的上下文."""

    user_id: int
    username: str
    session_id: str
    message: str
    history: list[dict] = field(default_factory=list)  # [{"role","content"}]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DispatchResult:
    """主调度结果."""

    label: str            # knowledge_explain / quiz_coaching / notes_organizing / multi_task / non_learning
    label_name: str       # 中文名
    reason: str
    channel: str          # llm / rule（演示轨迹中展示双通道来源）


@dataclass
class ValidationResult:
    """验证结果."""

    passed: bool
    score: Optional[float] = None    # LLM 评分 0~1（规则模式下为 None）
    feedback: str = ""               # 不通过时的修正反馈（驱动 Self-Loop）
    checks: list[dict] = field(default_factory=list)  # 各项规则明细
