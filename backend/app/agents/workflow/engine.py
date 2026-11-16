"""工作流引擎（WorkflowEngine）.

职责：
1. 按依赖顺序执行 Master Agent 生成的步骤计划（复用 AgentDispatcher）；
2. 把每一步的真实状态/输入/输出落库（复用 MasterTaskRecorder）；
3. 跑完一轮后交给失败分类器 + Self-Loop 策略，必要时**只重跑相关步骤**；
4. 修正后重新校验受影响产物，直到通过 / 达到上限 / 不可修复；
5. 支持取消（步骤间隙检查）与安全恢复（已完成不重跑、未知结果人工确认）；
6. 结束后清理本任务的内存日志（数据库记录保留）。

本模块不含业务规则：修正策略在 self_loop.py，写入确认在 recovery.py。
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.agents.core.base import AgentContext
from app.agents.core.logger import ExecutionLogger
from app.agents.core.registry import CoreAgentRegistry, core_registry
from app.agents.master.agent_dispatcher import AgentDispatcher
from app.agents.master.recorder import MasterTaskRecorder
from app.agents.master.result_aggregator import ResultAggregator
from app.agents.master.schemas import (
    MasterIntent,
    PlanStep,
    StepOutcome,
    StepStatus,
)
from app.agents.master.task_planner import TaskPlanner
from app.agents.workflow import config
from app.agents.workflow.failure import TYPE_LABELS, FailureClassifier
from app.agents.workflow.recovery import SideEffectConfirmer
from app.agents.workflow.self_loop import Decision, RepairAction, SelfLoopPolicy


@dataclass
class RunState:
    """一次工作流执行的可变状态（只在单次调用内使用，避免并发串状态）."""

    task_id: str
    intent: MasterIntent
    steps: list[PlanStep]
    outcomes: list[StepOutcome] = field(default_factory=list)
    by_agent: dict[str, StepOutcome] = field(default_factory=dict)
    validation: dict[str, StepOutcome] = field(default_factory=dict)
    step_started: dict[int, datetime] = field(default_factory=dict)
    rounds: list[dict] = field(default_factory=list)
    artifact_rounds: dict[str, int] = field(default_factory=dict)
    retrieval_rounds: int = 0
    cancelled: bool = False
    stop_reason: str = "passed"

    def target_of(self, order: int) -> Optional[str]:
        for step in self.steps:
            if step.order == order:
                return step.target
        return None


class WorkflowEngine:
    """工作流编排 + Self-Loop 控制器."""

    def __init__(
        self,
        registry: Optional[CoreAgentRegistry] = None,
        logger: Optional[ExecutionLogger] = None,
        policy: Optional[SelfLoopPolicy] = None,
        max_rounds: Optional[int] = None,
    ) -> None:
        self.registry = registry or core_registry
        self.logger = logger or ExecutionLogger()
        self.dispatcher = AgentDispatcher(registry=self.registry, logger=self.logger)
        self.classifier = FailureClassifier()
        self.policy = policy or SelfLoopPolicy(
            int(max_rounds) if max_rounds is not None else config.MAX_REPAIR_ROUNDS
        )
        self.confirmer = SideEffectConfirmer(self.dispatcher)
        self.aggregator = ResultAggregator()

    # ==================== 统一入口 ====================

    async def run(
        self,
        *,
        task_id: str,
        message: str,
        intent: MasterIntent,
        steps: list[PlanStep],
        context: AgentContext,
        recorder: MasterTaskRecorder,
        started_at: float,
        resume_rows: Optional[dict[int, Any]] = None,
        prior: Optional[dict] = None,
    ) -> dict:
        """执行工作流（含 Self-Loop）并返回统一结果.

        resume_rows：恢复工作流时传入历史步骤记录（step_order → WorkflowStepRecord）。
        prior：恢复时已完成的步骤结果与历史修正轮次。
        """
        state = RunState(task_id=task_id, intent=intent, steps=steps)
        prior = prior or {}
        skip_orders: set[int] = set()

        if prior:
            state.outcomes = list(prior.get("outcomes") or [])
            state.by_agent = dict(prior.get("by_agent") or {})
            state.validation = dict(prior.get("validation") or {})
            state.rounds = list(prior.get("rounds") or [])
            state.artifact_rounds = dict(prior.get("artifact_rounds") or {})
            state.retrieval_rounds = int(prior.get("retrieval_rounds") or 0)
            skip_orders = {o.order for o in state.outcomes}

        await self._run_steps(
            state, context, recorder, skip_orders=skip_orders, resume_rows=resume_rows
        )
        if not state.cancelled:
            await self._self_loop(state, context, recorder)

        logs = self.dispatcher.collect_logs(task_id)
        result = self.aggregator.aggregate(
            task_id=task_id,
            original_request=message,
            intent=intent,
            steps=steps,
            outcomes=state.outcomes,
            execution_time=time.time() - started_at,
            logs=logs,
            self_loop=self._self_loop_view(state),
            cancelled=state.cancelled,
        )
        return result

    def collect_logs(self, task_id: str) -> list[dict]:
        return self.dispatcher.collect_logs(task_id)

    # ==================== 步骤执行 ====================

    async def _run_steps(
        self,
        state: RunState,
        context: AgentContext,
        recorder: MasterTaskRecorder,
        skip_orders: Optional[set[int]] = None,
        resume_rows: Optional[dict[int, Any]] = None,
    ) -> None:
        skip_orders = skip_orders or set()

        for step in state.steps:
            if state.cancelled:
                self._record(
                    state, step,
                    self.dispatcher._skipped(
                        step, "任务已取消，未执行", "取消后不再执行后续步骤"
                    ),
                    recorder,
                )
                continue
            if config.CHECK_CANCEL_BEFORE_STEP and recorder.is_cancelled():
                state.cancelled = True
                self._log(state.task_id, "检测到取消请求，停止后续步骤", level="warning")
                self._record(
                    state, step,
                    self.dispatcher._skipped(
                        step, "任务已取消，未执行", "取消后不再执行后续步骤"
                    ),
                    recorder,
                )
                continue
            if step.order in skip_orders:
                continue

            blocked = self.dispatcher.blocking_deps(step, state.by_agent)
            if blocked:
                self._record(
                    state, step,
                    self.dispatcher._skipped(
                        step,
                        f"前置步骤未成功：{'、'.join(blocked)}",
                        "已跳过，未向下游传递任何数据",
                    ),
                    recorder,
                )
                continue

            # 恢复场景：写入型步骤先确认上一次是否已产生副作用
            row = (resume_rows or {}).get(step.order)
            if row is not None and step.agent in config.WRITE_AGENTS:
                adopted, blocked_note = self._resume_write_step(state, step, row, context)
                if adopted is not None:
                    self._record(state, step, adopted, recorder)
                    continue
                if blocked_note:
                    self._record(
                        state, step,
                        StepOutcome(
                            order=step.order, agent=step.agent, action=step.action,
                            status=StepStatus.FAILED.value, success=False,
                            task_id=f"{state.task_id}-{step.order}-unknown",
                            error=blocked_note,
                            input_summary=_loads(row.input_json) or {},
                        ),
                        recorder,
                    )
                    state.stop_reason = "manual_check"
                    self._log(
                        state.task_id, f"{step.agent}：{blocked_note}", level="error"
                    )
                    continue

            state.step_started[step.order] = datetime.utcnow()
            outcome = await self.dispatcher.run_step(
                step, state.intent, context, state.task_id, state.by_agent
            )
            self._record(state, step, outcome, recorder)

    def _resume_write_step(
        self, state: RunState, step: PlanStep, row, context: AgentContext,
    ) -> tuple[Optional[StepOutcome], str]:
        """恢复时处理写入型步骤.

        返回 (可沿用的结果, 阻断原因)：
        - 确认已写入 → 返回结果（不重复执行）；
        - running/retrying 且无法确认 → 返回阻断原因（标记需人工确认，**不重跑**）；
        - pending/skipped/failed 且确认无写入 → (None, "") 允许安全重跑；
        - 从未开始过 → (None, "") 直接重跑。
        """
        status = str(getattr(row, "status", "") or "")
        started = getattr(row, "started_at", None)
        if started is None:
            return None, ""

        input_data = _loads(getattr(row, "input_json", None)) or {}
        confirm = self.confirmer.confirm(
            agent=step.agent, input_data=input_data, context=context, since=started
        )
        if confirm.confirmed and confirm.payload:
            self._log(
                state.task_id,
                f"恢复：{step.agent} 上次已写入（{confirm.note}），不再重复执行",
            )
            return StepOutcome(
                order=step.order,
                agent=step.agent,
                action=step.action,
                status=StepStatus.SUCCESS.value,
                success=True,
                task_id=f"{state.task_id}-{step.order}-recovered",
                note=f"恢复确认：{confirm.note}",
                input_summary=input_data,
                result=confirm.payload,
            ), ""

        if status in ("running", "retrying"):
            return None, f"上次执行结果未知（{confirm.note or '无法确认写入'}），需人工确认"
        return None, ""

    def _record(
        self, state: RunState, step: PlanStep, outcome: StepOutcome,
        recorder: MasterTaskRecorder,
    ) -> None:
        """用最新结果替换同序号步骤结果，并落库."""
        state.outcomes = [o for o in state.outcomes if o.order != step.order]
        state.outcomes.append(outcome)
        state.outcomes.sort(key=lambda item: item.order)
        state.by_agent[step.agent] = outcome
        if outcome.agent == TaskPlanner.AGENT_VALIDATION and step.target:
            state.validation[step.target] = outcome
        recorder.update_step(outcome)

    # ==================== Self-Loop ====================

    async def _self_loop(
        self, state: RunState, context: AgentContext, recorder: MasterTaskRecorder
    ) -> None:
        for _ in range(config.LOOP_HARD_LIMIT):
            failures = self.classifier.classify(state.steps, state.outcomes)
            if not failures:
                state.stop_reason = "passed"
                return

            groups: dict[str, list] = {}
            for failure in failures:
                groups.setdefault(failure.target or failure.agent, []).append(failure)

            decisions: list[Decision] = []
            for target, items in groups.items():
                used = state.artifact_rounds.get(target, 0)
                decision = self.policy.plan(
                    items,
                    by_agent=state.by_agent,
                    intent=state.intent,
                    used_rounds=used,
                    retrieval_rounds=state.retrieval_rounds,
                )
                if not decision.repairable:
                    state.stop_reason = decision.stop_reason or "not_repairable"
                    self._log(
                        state.task_id,
                        f"{TYPE_LABELS.get(decision.failure_type, decision.failure_type)}"
                        f"：停止自动修正（{decision.note or decision.stop_reason}）",
                        level="warning",
                    )
                    continue
                decisions.append(decision)

            if not decisions:
                if state.stop_reason == "passed":
                    state.stop_reason = "not_repairable"
                return

            for decision in decisions:
                if recorder.is_cancelled():
                    state.cancelled = True
                    state.stop_reason = "cancelled"
                    return
                await self._apply_decision(state, decision, context, recorder)
                if state.stop_reason == "manual_check":
                    # 写入结果无法确认：立刻停止后续循环，交人工检查
                    return

        state.stop_reason = "max_rounds"

    async def _apply_decision(
        self, state: RunState, decision: Decision, context: AgentContext,
        recorder: MasterTaskRecorder,
    ) -> None:
        round_no = len(state.rounds) + 1
        started = time.time()
        actions_view: list[dict] = []

        for action in decision.actions:
            if action.kind == "confirm":
                await self._handle_confirm(state, action, context, recorder)
                actions_view.append(action.public())
                continue

            step = self._step_for_action(state, action)
            # 补题合并需要"重跑前"的产物（run_step 会覆盖 by_agent）
            previous = state.by_agent.get(action.agent) if action.merge else None
            state.step_started[step.order] = datetime.utcnow()
            outcome = await self.dispatcher.run_step(
                step, state.intent, context, state.task_id, state.by_agent,
                extra_input=action.input_overrides, task_suffix=action.task_suffix,
            )
            if action.merge == "questions_topup":
                outcome = self._merge_questions(state, step, outcome, recorder, previous)
            self._record(state, step, outcome, recorder)
            actions_view.append(action.public())

        # ---- 重新校验受影响的产物（写入结果未知时不再校验，直接交人工）----
        manual_check = state.stop_reason == "manual_check"
        validation = (
            None if manual_check
            else await self._revalidate(state, decision.target, context, recorder)
        )
        passed = self._is_passed(state, decision.target, validation)

        state.artifact_rounds[decision.target] = (
            state.artifact_rounds.get(decision.target, 0) + 1
        )
        if decision.target == TaskPlanner.AGENT_RETRIEVAL:
            state.retrieval_rounds += 1

        state.rounds.append({
            "round": round_no,
            "target": decision.target,
            "failure_type": decision.failure_type,
            "failure_label": TYPE_LABELS.get(decision.failure_type, decision.failure_type),
            "reason": "；".join(self._failure_messages(decision)),
            "actions": actions_view,
            "before": decision.before,
            "after": self._after_snapshot(state, decision.target),
            "validation": {
                "passed": passed,
                "score": (validation.result or {}).get("score") if validation and isinstance(validation.result, dict) else None,
                "passed_count": (validation.result or {}).get("passed_count") if validation and isinstance(validation.result, dict) else None,
                "check_count": (validation.result or {}).get("check_count") if validation and isinstance(validation.result, dict) else None,
                "issues": (validation.result or {}).get("issues") if validation and isinstance(validation.result, dict) else [],
            },
            "note": decision.note,
            "elapsed": round(time.time() - started, 4),
        })
        if not passed and not manual_check:
            state.stop_reason = "still_failing"
        self._log(
            state.task_id,
            f"第 {round_no} 轮修正完成：{decision.target} "
            f"{'已通过' if passed else '仍未通过'}"
            f"（{TYPE_LABELS.get(decision.failure_type, decision.failure_type)}）",
            level="info" if passed else "warning",
        )

    async def _handle_confirm(
        self, state: RunState, action: RepairAction, context: AgentContext,
        recorder: MasterTaskRecorder,
    ) -> None:
        """写入型失败：先确认是否已写入；确认成功则按成功继续，否则标记人工检查."""
        step = self._step_for_action(state, action)
        since = state.step_started.get(step.order)
        current = state.by_agent.get(action.agent)
        input_data = (current.input_summary if current else {}) or {}

        confirm = self.confirmer.confirm(
            agent=action.agent, input_data=input_data, context=context, since=since
        )
        if confirm.confirmed and confirm.payload:
            outcome = StepOutcome(
                order=step.order,
                agent=step.agent,
                action=step.action,
                status=StepStatus.SUCCESS.value,
                success=True,
                task_id=f"{state.task_id}-{step.order}-confirmed",
                note=confirm.note,
                input_summary=input_data,
                result=confirm.payload,
            )
            self._record(state, step, outcome, recorder)
            self._log(state.task_id, f"写入确认成功：{confirm.note}")
            return

        outcome = StepOutcome(
            order=step.order,
            agent=step.agent,
            action=step.action,
            status=StepStatus.FAILED.value,
            success=False,
            task_id=f"{state.task_id}-{step.order}-unknown",
            error=confirm.note or "执行结果未知，需人工确认",
            input_summary=input_data,
            result=current.result if current else None,
        )
        self._record(state, step, outcome, recorder)
        state.stop_reason = "manual_check"
        self._log(
            state.task_id,
            f"{step.agent} 执行结果无法确认，已标记为需人工检查：{confirm.note}",
            level="error",
        )

    async def _revalidate(
        self, state: RunState, target: str, context: AgentContext,
        recorder: MasterTaskRecorder,
    ) -> Optional[StepOutcome]:
        """重新执行该产物的校验步骤（没有校验步骤则返回 None）."""
        step = self._validation_step(state, target)
        if step is None:
            return None
        state.step_started[step.order] = datetime.utcnow()
        outcome = await self.dispatcher.run_step(
            step, state.intent, context, state.task_id, state.by_agent,
            task_suffix=f"rev{len(state.rounds) + 1}",
        )
        if outcome.status == StepStatus.SKIPPED.value:
            return outcome
        self._record(state, step, outcome, recorder)
        return outcome

    def _validation_step(self, state: RunState, target: str) -> Optional[PlanStep]:
        for step in state.steps:
            if step.agent == TaskPlanner.AGENT_VALIDATION and step.target == target:
                return step
        return None

    def _is_passed(
        self, state: RunState, target: str, validation: Optional[StepOutcome]
    ) -> bool:
        if validation is not None:
            payload = validation.result if isinstance(validation.result, dict) else {}
            return bool(payload.get("passed"))
        # 没有校验步骤（如知识检索）：以产物本身的真实状态判断
        agent = TaskPlanner.TARGET_SOURCE.get(target, target)
        outcome = state.by_agent.get(agent)
        if outcome is None:
            return False
        payload = outcome.result if isinstance(outcome.result, dict) else {}
        if agent == TaskPlanner.AGENT_RETRIEVAL:
            return payload.get("found") is True
        if agent == TaskPlanner.AGENT_QUESTIONS and "count_met" in payload:
            return bool(payload.get("count_met"))
        return outcome.success

    # ==================== 补题合并 ====================

    def _merge_questions(
        self, state: RunState, step: PlanStep, new_outcome: StepOutcome,
        recorder: MasterTaskRecorder, old: Optional[StepOutcome] = None,
    ) -> StepOutcome:
        """把"补充生成的题目"与"上一轮已保存的题目"合并成一个真实产物."""
        old_payload = old.result if (old and isinstance(old.result, dict)) else {}
        new_payload = new_outcome.result if isinstance(new_outcome.result, dict) else {}

        old_items = [q for q in (old_payload.get("questions") or []) if isinstance(q, dict)]
        new_items = [q for q in (new_payload.get("questions") or []) if isinstance(q, dict)]

        merged_items: list[dict] = []
        seen_ids: set = set()
        for item in old_items + new_items:
            key = item.get("id")
            if key in seen_ids:
                continue
            seen_ids.add(key)
            merged_items.append(item)

        old_ids = [int(i) for i in (old_payload.get("question_ids") or [])]
        new_ids = [int(i) for i in (new_payload.get("question_ids") or [])]
        ids = list(dict.fromkeys(old_ids + new_ids))

        requested = int(old_payload.get("requested_count") or new_payload.get("requested_count") or len(ids))
        actual = len(ids)
        merged_payload = {
            **old_payload,
            **{
                key: new_payload.get(key)
                for key in ("knowledge_point", "difficulty", "question_types",
                            "question_type_names", "use_weak_points")
                if new_payload.get(key) is not None
            },
            "agent": TaskPlanner.AGENT_QUESTIONS,
            "status": "success" if actual >= requested else "partial",
            "count_met": actual >= requested,
            "requested_count": requested,
            "actual_count": actual,
            "question_ids": ids,
            "questions": merged_items,
            "excluded_count": new_payload.get("excluded_count", 0),
            "topup_rounds": int(old_payload.get("topup_rounds") or 0) + 1,
            "message": f"补充后共保存 {actual}/{requested} 道题目",
            "reason": "" if actual >= requested else f"仍缺 {requested - actual} 道",
        }

        merged = StepOutcome(
            order=step.order,
            agent=step.agent,
            action=step.action,
            status=(
                StepStatus.SUCCESS.value if actual >= requested
                else StepStatus.PARTIAL.value
            ),
            success=True,
            task_id=new_outcome.task_id,
            execution_time=round(
                float(old.execution_time if old else 0) + new_outcome.execution_time, 4
            ),
            note=f"补充 {len(new_ids)} 道，累计 {actual}/{requested}",
            input_summary=new_outcome.input_summary,
            result=merged_payload,
        )
        self._log(
            state.task_id,
            f"补题合并：新增 {len(new_ids)} 道，累计 {actual}/{requested}",
        )
        return merged

    # ==================== 视图辅助 ====================

    def _self_loop_view(self, state: RunState) -> dict:
        return {
            "enabled": True,
            "max_repair_rounds": self.policy.max_rounds,
            "rounds": state.rounds,
            "repair_count": len(state.rounds),
            "stopped_reason": state.stop_reason,
            "cancelled": state.cancelled,
        }

    def _step_for_action(self, state: RunState, action: RepairAction) -> PlanStep:
        for step in state.steps:
            if step.agent == action.agent and step.agent != TaskPlanner.AGENT_VALIDATION:
                return step
        # 计划外步骤（理论上不会发生）：构造一个不落库的临时步骤
        return PlanStep(
            order=900 + len(state.outcomes),
            agent=action.agent,
            action=f"修正{action.agent}",
            target=action.target,
        )

    @staticmethod
    def _failure_messages(decision: Decision) -> list[str]:
        messages: list[str] = []
        if decision.note:
            messages.append(decision.note)
        for action in decision.actions:
            messages.append(action.reason)
        return messages

    @staticmethod
    def _after_snapshot(state: RunState, target: str) -> dict:
        agent = target if target in (
            TaskPlanner.AGENT_QUESTIONS, TaskPlanner.AGENT_PLAN,
            TaskPlanner.AGENT_ANALYSIS,
        ) else TaskPlanner.TARGET_SOURCE.get(target)
        outcome = state.by_agent.get(agent) if agent else None
        payload = outcome.result if (outcome and isinstance(outcome.result, dict)) else {}
        if not payload:
            return {}
        return {
            "plan_id": payload.get("plan_id"),
            "task_count": payload.get("task_count"),
            "requested_count": payload.get("requested_count"),
            "actual_count": payload.get("actual_count"),
            "found": payload.get("found"),
            "sufficient": payload.get("sufficient"),
            "message": str(payload.get("message") or payload.get("summary") or "")[:160],
        }

    def _log(self, task_id: str, message: str, level: str = "info") -> None:
        self.logger.log(task_id, "workflow", message, level=level)


def _loads(text: Optional[str]) -> Any:
    if not text:
        return None
    import json
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None
