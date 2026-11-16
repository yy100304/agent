"""核心 Agent 注册入口.

把各阶段专业 Agent 与主控 Agent 注册进统一注册表（`core_registry`），
主控 Agent / 工作流引擎即可通过名称查找并调度，无需硬编码实例。

约定：
- 幂等：重复调用不会抛“重复注册”，只补注册缺失项；
- 懒加载：函数内部导入各 Agent，避免模块级循环依赖。
"""
from typing import List

from app.agents.core.registry import core_registry


def register_core_agents() -> List[str]:
    """注册所有已实现的专业 Agent 与主控 Agent，返回注册表内的名称列表."""
    from app.agents.knowledge_retrieval_agent import KnowledgeRetrievalAgent
    from app.agents.learning_analysis_agent import LearningAnalysisAgent
    from app.agents.master.master_agent import MasterAgent
    from app.agents.question_generation_agent import QuestionGenerationAgent
    from app.agents.result_validation_agent import ResultValidationAgent
    from app.agents.study_planning_agent import StudyPlanningAgent

    candidates = (
        # 主控 Agent 先注册：调度时需要它已就绪
        MasterAgent(),
        LearningAnalysisAgent(),
        KnowledgeRetrievalAgent(),
        StudyPlanningAgent(),
        QuestionGenerationAgent(),
        ResultValidationAgent(),
    )
    for agent in candidates:
        if core_registry.get(agent.name) is None:
            core_registry.register(agent)
    return core_registry.names()


__all__ = ["register_core_agents"]
