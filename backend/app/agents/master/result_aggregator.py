"""结果汇总（ResultAggregator）.

职责：
- 根据**真实执行的步骤结果**判定整体状态（success / partial / failed / skipped）；
- 保留各专业 Agent 的原始输出（不做二次改写，便于第九阶段 Self-Loop 复用）；
- 生成对用户可读的确定性摘要：数字一律来自 Agent 的真实返回，不重算、不夸大；
- 汇总告警（数据不足、未检索到、部分成功）与问题（失败、校验不通过）。
"""
from typing import Any, Optional

from app.agents.master.schemas import (
    MasterIntent,
    MasterStatus,
    PlanStep,
    StepOutcome,
    StepStatus,
)
from app.agents.master.task_planner import TaskPlanner


class ResultAggregator:
    """把步骤执行结果汇总成统一的最终响应."""

    def aggregate(
        self,
        *,
        task_id: str,
        original_request: str,
        intent: MasterIntent,
        steps: list[PlanStep],
        outcomes: list[StepOutcome],
        execution_time: float,
        logs: Optional[list[dict]] = None,
        warnings: Optional[list[str]] = None,
        pending_questions: Optional[list[str]] = None,
        self_loop: Optional[dict] = None,
        cancelled: bool = False,
    ) -> dict:
        produced = [
            o for o in outcomes if o.agent != TaskPlanner.AGENT_VALIDATION
        ]
        validations = [
            o for o in outcomes if o.agent == TaskPlanner.AGENT_VALIDATION
        ]
        executed = [o for o in outcomes if o.status != StepStatus.SKIPPED.value]
        usable = [o for o in produced if o.success]

        status = self._overall_status(intent, produced, executed, usable, validations)
        if cancelled:
            # 用户取消：即使部分步骤成功，整体也如实标记为 cancelled
            status = "cancelled"
        artifacts = self._artifacts(produced)
        validation_view = self._validations(steps, validations)
        issues = self._issues(produced, validations)
        warn = self._warnings(produced, intent, warnings)
        summary = self._summary(status, artifacts, validation_view, issues)
        next_actions = self._next_actions(status, artifacts, validation_view, issues)

        return {
            "task_id": task_id,
            "task_status": status,
            "original_request": original_request,
            "parsed_intent": intent.model_dump(mode="json"),
            "execution_plan": [step.public() for step in steps],
            "executed_agents": self._executed_agents(executed),
            "agent_results": [o.public(include_result=True) for o in outcomes],
            "execution_logs": logs or [],
            "execution_time": round(float(execution_time), 4),
            "final_result": {
                "summary": summary,
                "artifacts": artifacts,
                "validations": validation_view,
                "warnings": warn,
                "issues": issues,
                "assumptions": list(intent.assumptions),
                "next_actions": next_actions,
                "pending_questions": pending_questions or [],
                "self_loop": self_loop or {
                    "enabled": False, "rounds": [], "repair_count": 0,
                    "stopped_reason": "", "max_repair_rounds": 0,
                },
                "cancelled": bool(cancelled),
            },
        }

    # ==================== 状态判定 ====================

    # 用户明确要的产物：意图 → 产出它的 Agent
    INTENT_AGENTS = {
        "analysis": TaskPlanner.AGENT_ANALYSIS,
        "retrieval": TaskPlanner.AGENT_RETRIEVAL,
        "plan": TaskPlanner.AGENT_PLAN,
        "questions": TaskPlanner.AGENT_QUESTIONS,
    }

    def _overall_status(
        self,
        intent: MasterIntent,
        produced: list[StepOutcome],
        executed: list[StepOutcome],
        usable: list[StepOutcome],
        validations: list[StepOutcome],
    ) -> str:
        if not executed:
            # 没有任何步骤真正执行（例如只校验但找不到可校验结果）
            return MasterStatus.SKIPPED.value
        if not usable:
            return MasterStatus.FAILED.value

        # 纯校验场景：没有产物，只看校验结论
        if not produced:
            passed = all(o.status == StepStatus.SUCCESS.value for o in validations)
            return MasterStatus.SUCCESS.value if passed else MasterStatus.FAILED.value

        # 用户真正要的产物失败 → 主要任务未完成 → failed
        requested_agents = {
            self.INTENT_AGENTS[i] for i in intent.intents if i in self.INTENT_AGENTS
        }
        primary = [o for o in produced if o.agent in requested_agents] or produced
        delivered = [o for o in primary if o.success]
        if not delivered:
            return MasterStatus.FAILED.value

        degraded = any(
            o.status in (StepStatus.FAILED.value, StepStatus.SKIPPED.value,
                         StepStatus.PARTIAL.value)
            for o in produced
        )
        unverified = any(o.status != StepStatus.SUCCESS.value for o in validations)
        if len(delivered) < len(primary) or degraded or unverified:
            return MasterStatus.PARTIAL.value
        return MasterStatus.SUCCESS.value

    # ==================== 产物与校验视图 ====================

    @staticmethod
    def _artifacts(produced: list[StepOutcome]) -> dict:
        artifacts: dict = {}
        for outcome in produced:
            if outcome.success and isinstance(outcome.result, dict):
                artifacts[outcome.agent] = outcome.result
        return artifacts

    def _validations(
        self, steps: list[PlanStep], validations: list[StepOutcome]
    ) -> list[dict]:
        targets = {step.order: step.target for step in steps}
        view: list[dict] = []
        for outcome in validations:
            payload = outcome.result if isinstance(outcome.result, dict) else {}
            view.append({
                "target": targets.get(outcome.order) or payload.get("target"),
                "status": outcome.status,
                "executed": outcome.status != StepStatus.SKIPPED.value,
                "passed": bool(payload.get("passed")),
                "score": payload.get("score"),
                "check_count": payload.get("check_count"),
                "passed_count": payload.get("passed_count"),
                "issues": list(payload.get("issues") or []),
                "suggestions": list(payload.get("suggestions") or []),
                "message": payload.get("message") or outcome.error or outcome.note,
            })
        return view

    # ==================== 问题与告警 ====================

    @staticmethod
    def _issues(produced: list[StepOutcome], validations: list[StepOutcome]) -> list[str]:
        issues: list[str] = []
        for outcome in produced:
            if outcome.status == StepStatus.FAILED.value:
                detail = outcome.error or outcome.note or "执行失败"
                issues.append(f"{outcome.action}失败：{detail}")
            elif outcome.status == StepStatus.PARTIAL.value:
                detail = outcome.note or "仅部分完成"
                issues.append(f"{outcome.action}部分完成：{detail}")
            elif outcome.status == StepStatus.SKIPPED.value:
                issues.append(f"{outcome.action}未执行：{outcome.error}")
        for outcome in validations:
            payload = outcome.result if isinstance(outcome.result, dict) else {}
            if outcome.status == StepStatus.SUCCESS.value:
                continue
            detail = "；".join(str(i) for i in (payload.get("issues") or []))
            issues.append(
                f"结果校验未通过：{detail}" if detail
                else f"结果校验未完成：{outcome.error or outcome.note}"
            )
        return issues

    @staticmethod
    def _warnings(
        produced: list[StepOutcome], intent: MasterIntent, extra: Optional[list[str]]
    ) -> list[str]:
        warnings: list[str] = list(extra or [])
        for outcome in produced:
            if outcome.status in (StepStatus.SUCCESS.value, StepStatus.PARTIAL.value):
                if outcome.note:
                    warnings.append(f"{outcome.action}：{outcome.note}")
        for assumption in intent.assumptions:
            if assumption not in warnings:
                warnings.append(assumption)
        return warnings

    # ==================== 摘要 ====================

    def _summary(
        self,
        status: str,
        artifacts: dict,
        validations: list[dict],
        issues: list[str],
    ) -> str:
        lines: list[str] = []

        analysis = artifacts.get(TaskPlanner.AGENT_ANALYSIS) or {}
        if analysis:
            if analysis.get("sufficient") is False:
                missing = "、".join(map(str, analysis.get("missing") or []))
                lines.append(f"学情数据不足（{missing or '缺少答题/学习记录'}），已如实说明。")
            else:
                lines.append(f"学情：{analysis.get('summary') or '已生成学情报告。'}")

        retrieval = artifacts.get(TaskPlanner.AGENT_RETRIEVAL) or {}
        if retrieval:
            if retrieval.get("found"):
                lines.append(str(retrieval.get("summary") or "已完成知识检索。"))
            else:
                lines.append(str(retrieval.get("message") or "未检索到相关知识。"))

        plan = artifacts.get(TaskPlanner.AGENT_PLAN) or {}
        if plan:
            lines.append(
                f"已保存学习计划（plan_id={plan.get('plan_id')}）「{plan.get('title')}」："
                f"覆盖 {plan.get('days')} 天、共 {plan.get('task_count')} 个任务，"
                f"每日上限 {plan.get('daily_minutes')} 分钟。"
            )

        questions = artifacts.get(TaskPlanner.AGENT_QUESTIONS) or {}
        if questions:
            types = "/".join(questions.get("question_type_names") or []) or "题目"
            lines.append(
                f"已生成并保存 {questions.get('actual_count')}/"
                f"{questions.get('requested_count')} 道{types}"
                f"（知识点：{(questions.get('knowledge_point') or {}).get('name', '未指定')}，"
                f"难度：{questions.get('difficulty') or '自动'}）。"
            )

        executed_checks = [v for v in validations if v.get("executed")]
        if executed_checks:
            passed = sum(1 for v in executed_checks if v.get("passed"))
            lines.append(f"结果校验：{passed}/{len(executed_checks)} 项通过。")
        elif validations:
            lines.append("结果校验未执行（缺少可校验的产物）。")

        head = {
            MasterStatus.SUCCESS.value: "已完成：",
            MasterStatus.PARTIAL.value: "部分完成：",
            MasterStatus.FAILED.value: "执行失败：",
            MasterStatus.SKIPPED.value: "未执行：",
            "cancelled": "已取消：",
        }.get(status, "")
        body = "\n".join(f"- {line}" for line in lines) or "未产生任何结果。"
        text = f"{head}\n{body}"
        if issues:
            text += "\n待处理问题：\n" + "\n".join(f"- {item}" for item in issues)
        return text

    def _next_actions(
        self,
        status: str,
        artifacts: dict,
        validations: list[dict],
        issues: list[str],
    ) -> list[str]:
        actions: list[str] = []
        if status == MasterStatus.SUCCESS.value:
            return actions
        for item in validations:
            actions.extend(str(s) for s in (item.get("suggestions") or []))
        if not artifacts.get(TaskPlanner.AGENT_PLAN) and issues:
            actions.append("如需生成学习计划，请补充考试日期与每日可用学习时长。")
        if status == MasterStatus.PARTIAL.value:
            actions.append("可针对上述问题重新提交需求，主控会重新调度相关 Agent。")
        deduped: list[str] = []
        for action in actions:
            if action and action not in deduped:
                deduped.append(action)
        return deduped

    @staticmethod
    def _executed_agents(executed: list[StepOutcome]) -> list[str]:
        names: list[str] = []
        for outcome in executed:
            if outcome.agent not in names:
                names.append(outcome.agent)
        return names
