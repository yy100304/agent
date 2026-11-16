"""Self-Loop 决策（SelfLoopPolicy）.

输入：失败分类结果 + 当前产物（真实 Agent 输出）
输出：是否修正、修正哪些 Agent、传什么参数、以及停止原因

安全边界（硬编码为策略，不允许绕过）：
- 只补缺口，不重新生成全部题目；
- 只调整本次工作流创建的计划，不改考试日期/每日预算，不删整份计划；
- 已入库题目出现格式问题时**不删不改**，直接停止；
- 学情数据不足、数据库错误不盲目重跑；
- 每个产物最多 MAX_REPAIR_ROUNDS 轮（config 集中配置）。
"""
from dataclasses import dataclass, field
from typing import Optional

from app.agents.master.schemas import MasterIntent
from app.agents.master.task_planner import TaskPlanner
from app.agents.workflow import config
from app.agents.workflow.failure import (
    AGENT_TIMEOUT,
    BUDGET_EXCEEDED,
    COUNT_INSUFFICIENT,
    DATABASE_ERROR,
    DUPLICATE_CONTENT,
    FORMAT_ERROR,
    INSUFFICIENT_DATA,
    RETRIEVAL_EMPTY,
    TYPE_LABELS,
    UNKNOWN_ERROR,
    Failure,
)

# 多个失败同时存在时的处理优先级（越靠前越先处理）
PRIORITY = (
    COUNT_INSUFFICIENT, DUPLICATE_CONTENT, BUDGET_EXCEEDED,
    INSUFFICIENT_DATA, DATABASE_ERROR, FORMAT_ERROR, AGENT_TIMEOUT, UNKNOWN_ERROR,
)


@dataclass
class RepairAction:
    """一个可执行的修正动作."""

    kind: str                       # rerun（重跑 Agent）/ confirm（先确认写入再决定）
    agent: str
    target: str
    reason: str
    input_overrides: dict = field(default_factory=dict)
    task_suffix: str = ""
    merge: str = ""                 # questions_topup：与已有题目合并后再校验

    def public(self) -> dict:
        return {
            "kind": self.kind,
            "agent": self.agent,
            "target": self.target,
            "reason": self.reason,
            "input": {
                key: value for key, value in self.input_overrides.items()
                if key not in ("analysis_result", "retrieval_result")
            },
        }


@dataclass
class Decision:
    """一轮修正决策."""

    target: str
    failure_type: str
    repairable: bool
    stop_reason: str = ""
    note: str = ""
    actions: list[RepairAction] = field(default_factory=list)
    before: dict = field(default_factory=dict)

    def public(self) -> dict:
        return {
            "target": self.target,
            "failure_type": self.failure_type,
            "label": TYPE_LABELS.get(self.failure_type, self.failure_type),
            "repairable": self.repairable,
            "stop_reason": self.stop_reason,
            "note": self.note,
            "actions": [action.public() for action in self.actions],
            "before": self.before,
        }


class SelfLoopPolicy:
    """把失败分类翻译成修正决策."""

    def __init__(self, max_rounds: int = config.MAX_REPAIR_ROUNDS) -> None:
        self.max_rounds = max_rounds

    # ==================== 入口 ====================

    def plan(
        self,
        failures: list[Failure],
        *,
        by_agent: dict,
        intent: MasterIntent,
        used_rounds: int,
        retrieval_rounds: int = 0,
    ) -> Decision:
        """针对同一产物的失败集合生成一轮决策."""
        primary = self._pick(failures)
        target = primary.target
        artifact = self._artifact_of(primary.agent, by_agent)

        if used_rounds >= self.max_rounds:
            return Decision(
                target=target,
                failure_type=primary.type,
                repairable=False,
                stop_reason="max_rounds",
                note=f"已达到最大修正轮次 {self.max_rounds}，停止自动修正",
                before=self._snapshot(artifact),
            )

        handler = {
            COUNT_INSUFFICIENT: self._repair_questions_gap,
            DUPLICATE_CONTENT: self._repair_questions_gap,
            BUDGET_EXCEEDED: self._repair_plan_budget,
            FORMAT_ERROR: self._repair_format,
            RETRIEVAL_EMPTY: self._repair_retrieval,
            INSUFFICIENT_DATA: self._stop_insufficient_data,
            DATABASE_ERROR: self._confirm_first,
            AGENT_TIMEOUT: self._repair_timeout,
            UNKNOWN_ERROR: self._repair_unknown,
        }.get(primary.type, self._stop_unknown)

        return handler(
            primary, artifact, by_agent, intent, used_rounds, retrieval_rounds
        )

    # ==================== 策略实现 ====================

    def _repair_questions_gap(
        self, failure: Failure, artifact: dict, by_agent: dict,
        intent: MasterIntent, used_rounds: int, retrieval_rounds: int,
    ) -> Decision:
        target = "question_set"
        before = self._snapshot(artifact)

        if failure.type == DUPLICATE_CONTENT and artifact.get("actual_count") == artifact.get("requested_count"):
            # 数量已达标但存在重复：说明重复题已入库，删除会破坏用户数据
            return Decision(
                target, failure.type, False, "not_repairable",
                "检测到重复题目且数量已达标，为避免删除已入库题目，停止自动修正",
                before=before,
            )

        requested = self._as_int(artifact.get("requested_count"))
        actual = self._as_int(artifact.get("actual_count"))
        if requested is None or actual is None:
            return Decision(target, failure.type, False, "not_repairable",
                            "缺少题目数量信息，无法确定缺口", before=before)
        gap = requested - actual
        if gap <= 0:
            return Decision(target, failure.type, False, "not_repairable",
                            "题目数量已达标，无需补充", before=before)

        kp = artifact.get("knowledge_point") or {}
        contents = [
            str(item.get("content") or "")
            for item in (artifact.get("questions") or [])
            if isinstance(item, dict) and item.get("content")
        ]
        overrides = {
            "count": gap,
            "exclude_question_ids": list(artifact.get("question_ids") or []),
            "exclude_contents": contents,
            "knowledge_point": kp.get("name"),
            "difficulty": artifact.get("difficulty"),
            "question_types": artifact.get("question_types"),
        }
        overrides = {k: v for k, v in overrides.items() if v not in (None, [], "")}
        action = RepairAction(
            kind="rerun",
            agent=TaskPlanner.AGENT_QUESTIONS,
            target=target,
            reason=f"数量不足：已保存 {actual}/{requested}，仅补充缺口 {gap} 道并排除已有题目",
            input_overrides=overrides,
            task_suffix=f"topup{used_rounds + 1}",
            merge="questions_topup",
        )
        return Decision(
            target, failure.type, True, "", f"需补充 {gap} 道题目",
            actions=[action], before=before,
        )

    def _repair_plan_budget(
        self, failure: Failure, artifact: dict, by_agent: dict,
        intent: MasterIntent, used_rounds: int, retrieval_rounds: int,
    ) -> Decision:
        target = "study_plan"
        before = self._snapshot(artifact)
        plan_id = artifact.get("plan_id")
        if not plan_id:
            return Decision(
                target, failure.type, False, "not_repairable",
                "未找到本次工作流创建的学习计划（不修改用户已有计划）",
                before=before,
            )
        action = RepairAction(
            kind="rerun",
            agent=TaskPlanner.AGENT_PLAN,
            target=target,
            reason="压缩超预算日期的任务时长（不改考试日期与每日预算，不新建计划）",
            input_overrides={
                "adjust_plan_id": plan_id,
                "adjust_reason": "daily_budget_exceeded",
                "adjust_fix_titles": True,
            },
            task_suffix=f"adjust{used_rounds + 1}",
        )
        return Decision(
            target, failure.type, True, "",
            "仅调整本次计划中超预算的日期", actions=[action], before=before,
        )

    def _repair_format(
        self, failure: Failure, artifact: dict, by_agent: dict,
        intent: MasterIntent, used_rounds: int, retrieval_rounds: int,
    ) -> Decision:
        target = failure.target
        before = self._snapshot(artifact)

        if failure.agent == TaskPlanner.AGENT_PLAN:
            plan_id = artifact.get("plan_id")
            if not plan_id:
                return Decision(target, failure.type, False, "not_repairable",
                                "缺少计划 ID，无法在不动用户数据的前提下修正", before=before)
            action = RepairAction(
                kind="rerun",
                agent=TaskPlanner.AGENT_PLAN,
                target=target,
                reason="就地规范化本次计划（补齐任务标题/重算汇总），不新建计划",
                input_overrides={
                    "adjust_plan_id": plan_id,
                    "adjust_reason": "format_normalize",
                    "adjust_fix_titles": True,
                },
                task_suffix=f"normalize{used_rounds + 1}",
            )
            return Decision(target, failure.type, True, "", "就地规范化计划", actions=[action], before=before)

        if failure.agent == TaskPlanner.AGENT_ANALYSIS:
            action = RepairAction(
                kind="rerun",
                agent=TaskPlanner.AGENT_ANALYSIS,
                target=target,
                reason="学情报告结构不规范，重新生成（只读，不写业务数据）",
                task_suffix=f"rerun{used_rounds + 1}",
            )
            return Decision(target, failure.type, True, "", "重跑学情分析", actions=[action], before=before)

        if failure.agent == TaskPlanner.AGENT_QUESTIONS:
            return Decision(
                target, failure.type, False, "not_repairable",
                "已入库题目存在格式问题：按约定不自动删除/修改用户题库，已停止修正",
                before=before,
            )
        return Decision(target, failure.type, False, "not_repairable",
                        "该产物的格式问题无法自动修正", before=before)

    def _repair_retrieval(
        self, failure: Failure, artifact: dict, by_agent: dict,
        intent: MasterIntent, used_rounds: int, retrieval_rounds: int,
    ) -> Decision:
        target = TaskPlanner.AGENT_RETRIEVAL
        before = self._snapshot(artifact)
        if retrieval_rounds >= config.RETRIEVAL_MAX_REPAIRS:
            return Decision(
                target, failure.type, False, "not_repairable",
                "已调整过检索关键词仍未命中，停止重试并如实报告未检索到内容",
                before=before,
            )
        previous = self._previous_query(by_agent, target)
        next_query = self._next_query(intent, by_agent, previous)
        if not next_query:
            return Decision(target, failure.type, False, "not_repairable",
                            "没有可尝试的其它检索关键词", before=before)
        action = RepairAction(
            kind="rerun",
            agent=TaskPlanner.AGENT_RETRIEVAL,
            target=target,
            reason=f"更换检索关键词为「{next_query}」再试一次",
            input_overrides={"query": next_query, "top_k": 3},
            task_suffix=f"requery{used_rounds + 1}",
        )
        return Decision(target, failure.type, True, "", "调整检索关键词", actions=[action], before=before)

    def _stop_insufficient_data(
        self, failure: Failure, artifact: dict, by_agent: dict,
        intent: MasterIntent, used_rounds: int, retrieval_rounds: int,
    ) -> Decision:
        return Decision(
            failure.target, failure.type, False, "not_repairable",
            "学情数据不足属于事实状态，禁止通过重跑或模型编造修复；请用户补充学习记录",
            before=self._snapshot(artifact),
        )

    def _confirm_first(
        self, failure: Failure, artifact: dict, by_agent: dict,
        intent: MasterIntent, used_rounds: int, retrieval_rounds: int,
    ) -> Decision:
        """数据库错误：不盲目重跑，先确认上一次写入是否已经成功."""
        action = RepairAction(
            kind="confirm",
            agent=failure.agent,
            target=failure.target,
            reason="数据库异常：先查询确认是否已写入，再决定是否继续",
        )
        return Decision(
            failure.target, failure.type, True, "",
            "先确认写入结果，禁止盲目重试", actions=[action],
            before=self._snapshot(artifact),
        )

    def _repair_timeout(
        self, failure: Failure, artifact: dict, by_agent: dict,
        intent: MasterIntent, used_rounds: int, retrieval_rounds: int,
    ) -> Decision:
        if failure.agent in config.READ_ONLY_AGENTS:
            action = RepairAction(
                kind="rerun",
                agent=failure.agent,
                target=failure.target,
                reason="只读 Agent 超时重跑（不会产生重复数据）",
                task_suffix=f"retry{used_rounds + 1}",
            )
            return Decision(failure.target, failure.type, True, "",
                            "只读 Agent 超时可安全重跑一次", actions=[action],
                            before=self._snapshot(artifact))
        action = RepairAction(
            kind="confirm",
            agent=failure.agent,
            target=failure.target,
            reason="写入型 Agent 超时：先确认是否已经写入，确认无写入才允许重跑",
        )
        return Decision(failure.target, failure.type, True, "",
                        "写入型超时需先确认副作用", actions=[action],
                        before=self._snapshot(artifact))

    def _repair_unknown(
        self, failure: Failure, artifact: dict, by_agent: dict,
        intent: MasterIntent, used_rounds: int, retrieval_rounds: int,
    ) -> Decision:
        if failure.agent in config.READ_ONLY_AGENTS:
            action = RepairAction(
                kind="rerun", agent=failure.agent, target=failure.target,
                reason="只读 Agent 异常重跑一次",
                task_suffix=f"retry{used_rounds + 1}",
            )
            return Decision(failure.target, failure.type, True, "",
                            "只读 Agent 可安全重跑", actions=[action],
                            before=self._snapshot(artifact))
        return Decision(failure.target, failure.type, False, "not_repairable",
                        "写入型 Agent 出现未知错误，不自动重跑以避免重复写入",
                        before=self._snapshot(artifact))

    def _stop_unknown(
        self, failure: Failure, artifact: dict, by_agent: dict,
        intent: MasterIntent, used_rounds: int, retrieval_rounds: int,
    ) -> Decision:
        return Decision(failure.target, failure.type, False, "not_repairable",
                        "无法确定修正方式，停止自动修正",
                        before=self._snapshot(artifact))

    # ==================== 辅助 ====================

    @staticmethod
    def _pick(failures: list[Failure]) -> Failure:
        for failure_type in PRIORITY:
            for failure in failures:
                if failure.type == failure_type:
                    return failure
        return failures[0]

    @staticmethod
    def _artifact_of(agent: str, by_agent: dict) -> dict:
        outcome = by_agent.get(agent)
        if outcome is None:
            return {}
        return outcome.result if isinstance(outcome.result, dict) else {}

    @staticmethod
    def _snapshot(artifact: dict) -> dict:
        if not artifact:
            return {}
        return {
            "plan_id": artifact.get("plan_id"),
            "task_count": artifact.get("task_count"),
            "requested_count": artifact.get("requested_count"),
            "actual_count": artifact.get("actual_count"),
            "message": str(artifact.get("message") or "")[:160],
        }

    @staticmethod
    def _previous_query(by_agent: dict, agent: str) -> str:
        outcome = by_agent.get(agent)
        if outcome is None:
            return ""
        summary = outcome.input_summary or {}
        return str(summary.get("query") or "")

    @staticmethod
    def _next_query(intent: MasterIntent, by_agent: dict, previous: str) -> str:
        """按"知识点 → 薄弱点 → 学科 → 原始消息"顺序挑一个没试过的关键词."""
        candidates: list[str] = []
        if intent.knowledge_point:
            candidates.append(intent.knowledge_point)
        analysis = by_agent.get(TaskPlanner.AGENT_ANALYSIS)
        if analysis is not None and isinstance(analysis.result, dict):
            report = analysis.result.get("report") or {}
            weak = [str(w) for w in (report.get("weak_points") or []) if w]
            if weak:
                candidates.append(" ".join(weak[:2]))
        if intent.subject:
            candidates.append(intent.subject)
        if intent.query:
            candidates.append(intent.query)
        candidates.append(intent.message)

        seen: set[str] = set()
        for value in candidates:
            text = str(value or "").strip()
            if not text or text == previous or text in seen:
                continue
            seen.add(text)
            return text
        return ""

    @staticmethod
    def _as_int(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
