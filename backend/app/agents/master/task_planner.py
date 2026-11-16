"""任务规划（TaskPlanner）.

职责：把"意图 + 参数"翻译成一组**有依赖关系**的执行步骤。

依赖规则（对应需求第七节的调度表）：
- 学情分析        → learning_analysis
- 知识点解释      → knowledge_retrieval
- 制定学习计划    → learning_analysis → knowledge_retrieval → study_planning
- 生成练习题      → question_generation（用户要求"结合薄弱点"时补学情与检索）
- 计划 + 练习     → 学情 → 检索 → 计划 → 出题
- 写入型产物（计划/练习题）默认追加结果校验；显式要求校验时额外校验学情

本阶段只做**顺序调度**（第九阶段才做并行/工作流引擎），因此这里生成的是
拓扑有序的线性计划，depends_on 仅用于失败时阻断下游步骤。
"""
from typing import Optional

from app.agents.master.schemas import (
    INTENT_ANALYSIS,
    INTENT_PLAN,
    INTENT_QUESTIONS,
    INTENT_RETRIEVAL,
    INTENT_VALIDATION,
    TARGET_ANALYSIS,
    TARGET_PLAN,
    TARGET_QUESTION_SET,
    PlanStep,
    MasterIntent,
)


class TaskPlanner:
    """把意图翻译为可执行的步骤计划."""

    AGENT_ANALYSIS = "learning_analysis"
    AGENT_RETRIEVAL = "knowledge_retrieval"
    AGENT_PLAN = "study_planning"
    AGENT_QUESTIONS = "question_generation"
    AGENT_VALIDATION = "result_validation"

    # 校验目标 → 产物来源 Agent
    TARGET_SOURCE = {
        TARGET_ANALYSIS: AGENT_ANALYSIS,
        TARGET_PLAN: AGENT_PLAN,
        TARGET_QUESTION_SET: AGENT_QUESTIONS,
    }

    ACTION_NAMES = {
        AGENT_ANALYSIS: "分析学情",
        AGENT_RETRIEVAL: "检索知识内容",
        AGENT_PLAN: "生成学习计划",
        AGENT_QUESTIONS: "生成练习题",
        AGENT_VALIDATION: "校验结果",
    }

    PURPOSE = {
        AGENT_ANALYSIS: "读取真实学习数据，确定薄弱知识点与掌握度",
        AGENT_RETRIEVAL: "检索知识点定义/重点/难点，为计划与出题提供真实内容",
        AGENT_PLAN: "结合学情与考试时间生成并保存多日学习计划",
        AGENT_QUESTIONS: "针对薄弱知识点生成并保存练习题",
        AGENT_VALIDATION: "校验产物的完整性、数值合理性与落库一致性",
    }

    TARGET_LABELS = {
        TARGET_ANALYSIS: "学情报告",
        TARGET_PLAN: "学习计划",
        TARGET_QUESTION_SET: "练习题",
    }

    def build(self, intent: MasterIntent) -> list[PlanStep]:
        """按意图生成执行计划."""
        intents = set(intent.intents)
        need_analysis = INTENT_ANALYSIS in intents
        need_retrieval = INTENT_RETRIEVAL in intents
        need_plan = INTENT_PLAN in intents
        need_questions = INTENT_QUESTIONS in intents
        need_validation = INTENT_VALIDATION in intents

        # ---- 依赖补齐：计划一定需要学情与知识内容 ----
        if need_plan:
            need_analysis = True
            need_retrieval = True
        # ---- 只有"结合我的薄弱点"出题时才需要学情/检索，避免无谓调用 ----
        if need_questions and (intent.weak_points_driven or need_plan):
            need_analysis = True
            need_retrieval = True

        # ---- 纯校验场景：直接校验已有结果 ----
        if not (need_analysis or need_retrieval or need_plan or need_questions):
            return self._validation_only(intent)

        steps: list[PlanStep] = []

        if need_analysis:
            steps.append(self._step(
                steps, self.AGENT_ANALYSIS, deps=[],
                purpose=self.PURPOSE[self.AGENT_ANALYSIS],
            ))
        if need_retrieval:
            deps = [self.AGENT_ANALYSIS] if need_analysis else []
            steps.append(self._step(
                steps, self.AGENT_RETRIEVAL, deps=deps,
                purpose=self.PURPOSE[self.AGENT_RETRIEVAL],
            ))
        if need_plan:
            deps = [
                name for name in (self.AGENT_ANALYSIS, self.AGENT_RETRIEVAL)
                if any(s.agent == name for s in steps)
            ]
            steps.append(self._step(
                steps, self.AGENT_PLAN, deps=deps,
                purpose=self.PURPOSE[self.AGENT_PLAN],
            ))
        if need_questions:
            deps = [
                name for name in (self.AGENT_ANALYSIS, self.AGENT_RETRIEVAL)
                if any(s.agent == name for s in steps)
            ]
            steps.append(self._step(
                steps, self.AGENT_QUESTIONS, deps=deps,
                purpose=self.PURPOSE[self.AGENT_QUESTIONS],
            ))

        # ---- 结果校验：计划类产物默认校验；显式要求校验时覆盖出题与学情 ----
        targets: dict[str, str] = {}
        if need_plan:
            targets[TARGET_PLAN] = self.AGENT_PLAN
        if need_validation:
            if need_questions:
                targets[TARGET_QUESTION_SET] = self.AGENT_QUESTIONS
            if need_analysis:
                targets[TARGET_ANALYSIS] = self.AGENT_ANALYSIS
            for target in intent.check_targets:
                source = self.TARGET_SOURCE.get(target)
                if source and any(s.agent == source for s in steps):
                    targets.setdefault(target, source)

        for target, source in targets.items():
            steps.append(self._step(
                steps, self.AGENT_VALIDATION, deps=[source], target=target,
                action=f"校验{self.TARGET_LABELS.get(target, target)}",
            ))
        return steps

    def build_explicit(self, agents: list[str], intent: MasterIntent) -> list[PlanStep]:
        """按调用方显式指定的 Agent 顺序生成计划（调试/接口直调）.

        仅接受已注册的专业 Agent 名称；未注册的名称会被忽略，避免拼错导致空跑。
        """
        steps: list[PlanStep] = []
        previous: Optional[str] = None
        for name in agents:
            name = str(name).strip()
            if not name or not self._known_agent(name):
                continue
            if any(s.agent == name for s in steps):
                continue
            steps.append(self._step(steps, name, deps=[previous] if previous else []))
            previous = name
        return steps

    # ==================== 辅助 ====================

    def _validation_only(self, intent: MasterIntent) -> list[PlanStep]:
        """仅校验已有结果：直接对 check_targets 逐个校验."""
        steps: list[PlanStep] = []
        targets = intent.check_targets or [TARGET_PLAN]
        for target in targets:
            steps.append(self._step(
                steps, self.AGENT_VALIDATION, deps=[], target=target,
                action=f"校验{self.TARGET_LABELS.get(target, target)}",
            ))
        return steps

    def _step(
        self,
        steps: list[PlanStep],
        agent: str,
        deps: list[str],
        action: Optional[str] = None,
        purpose: str = "",
        target: Optional[str] = None,
    ) -> PlanStep:
        return PlanStep(
            order=len(steps) + 1,
            agent=agent,
            action=action or self.ACTION_NAMES.get(agent, agent),
            purpose=purpose or self.PURPOSE.get(agent, ""),
            depends_on=[d for d in deps if d],
            optional=agent in (self.AGENT_ANALYSIS, self.AGENT_RETRIEVAL),
            target=target,
        )

    @staticmethod
    def _known_agent(name: str) -> bool:
        return name in (
            TaskPlanner.AGENT_ANALYSIS, TaskPlanner.AGENT_RETRIEVAL,
            TaskPlanner.AGENT_PLAN, TaskPlanner.AGENT_QUESTIONS,
            TaskPlanner.AGENT_VALIDATION,
        )
