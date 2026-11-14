"""Agent 团队注册表：声明式定义所有可调度子智能体."""
from typing import Optional

from app.agents.base import AgentProfile
from app.agents.prompts import (
    COACH_PROMPT,
    COMMON_STYLE,
    DISPATCHER_PROMPT,
    NOTES_PROMPT,
    ORCHESTRATOR_PROMPT,
    TUTOR_PROMPT,
)


def _with_style(prompt: str, banner: str) -> str:
    """注入通用排版规范并填充横幅占位符."""
    return prompt.replace("{banner}", banner) + "\n" + COMMON_STYLE.replace(
        "{banner}", banner
    )


class AgentRegistry:
    """Agent 团队注册表（平台可调度单元的单一事实来源）."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentProfile] = {}
        self._register_defaults()

    # ---- 注册 ----

    def register(self, profile: AgentProfile) -> None:
        if profile.id in self._agents:
            raise ValueError(f"Agent 重复注册: {profile.id}")
        self._agents[profile.id] = profile

    # ---- 查询 ----

    def get(self, agent_id: str) -> Optional[AgentProfile]:
        return self._agents.get(agent_id)

    def require(self, agent_id: str) -> AgentProfile:
        profile = self._agents.get(agent_id)
        if not profile:
            raise KeyError(f"未注册的 Agent: {agent_id}")
        return profile

    def list_all(self) -> list[AgentProfile]:
        return list(self._agents.values())

    def to_dicts(self) -> list[dict]:
        return [p.to_dict() for p in self._agents.values()]

    # ---- 默认团队（比赛演示场景） ----

    def _register_defaults(self) -> None:
        # 1. 知识点讲解
        self.register(AgentProfile(
            id="tutor",
            name="知识点讲解 Agent",
            banner="> 🧑‍🏫 知识点讲解",
            description="学科知识点由浅入深讲解，四段式结构输出",
            role_prompt=_with_style(TUTOR_PROMPT, "> 🧑‍🏫 知识点讲解"),
            tools=["search_knowledge_base"],
            max_retries=2,
            structure_keywords=["定义", "举例"],
            min_output_chars=60,
        ))
        # 2. 习题答疑
        self.register(AgentProfile(
            id="coach",
            name="习题答疑 Agent",
            banner="> 🎯 习题答疑",
            description="习题分步引导与批改，严禁直接给完整答案",
            role_prompt=_with_style(COACH_PROMPT, "> 🎯 习题答疑"),
            tools=["search_knowledge_base"],
            max_retries=2,
            structure_keywords=["考点"],
            min_output_chars=50,
        ))
        # 3. 笔记整理
        self.register(AgentProfile(
            id="notes",
            name="笔记整理 Agent",
            banner="> 📝 笔记整理",
            description="结构化笔记提炼，支持精简/详细/考点三种风格",
            role_prompt=_with_style(NOTES_PROMPT, "> 📝 笔记整理"),
            tools=[],
            max_retries=2,
            structure_keywords=["-"],
            min_output_chars=30,
        ))
        # 4. 多任务编排
        self.register(AgentProfile(
            id="orchestrator",
            name="多任务编排 Agent",
            banner="> 🗂️ 多任务编排",
            description="拆解组合需求，按学习逻辑排序并逐项调度子 Agent",
            role_prompt=_with_style(ORCHESTRATOR_PROMPT, "> 🗂️ 多任务编排"),
            tools=[],
            max_retries=1,
            structure_keywords=["任务"],
            min_output_chars=50,
        ))

    # ---- 调度器提示词（不属于执行团队，单独暴露） ----

    @property
    def dispatcher_prompt(self) -> str:
        return DISPATCHER_PROMPT


# 模块级单例
agent_registry = AgentRegistry()

# 动态路由表：调度标签 → 工作流首节点
ROUTES: dict[str, str] = {
    "knowledge_explain": "tutor",
    "quiz_coaching": "coach",
    "notes_organizing": "notes",
    "multi_task": "orchestrator",
    "non_learning": "",  # 模板应答，不进入工作流
}
