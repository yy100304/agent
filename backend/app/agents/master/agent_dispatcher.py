"""专业 Agent 调度（AgentDispatcher）.

职责：
- 从统一注册表（core_registry）按名取 Agent，不在主控里硬编码实例；
- 按计划顺序执行，把前序 Agent 的**真实输出**注入后序 Agent 的输入；
- 前置步骤失败时阻断下游（skipped），不允许把失败结果当成功数据继续传；
- 把每个步骤的真实状态/耗时/错误/原始输出记录下来。

本阶段为顺序调度，不含 Self-Loop（第九阶段）。
"""
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.core.base import AgentContext
from app.agents.core.logger import ExecutionLogger
from app.agents.core.registry import CoreAgentRegistry, core_registry
from app.agents.core.schemas import AgentResult, AgentTask
from app.agents.master.schemas import (
    TARGET_PLAN,
    MasterIntent,
    PlanStep,
    StepOutcome,
    StepStatus,
    compact,
)
from app.agents.master.task_planner import TaskPlanner
from app.models import StudyPlan, StudyTask

# 允许继续向后传递的步骤状态（partial 表示结果部分可用，但会在告警中标注）
_USABLE = (StepStatus.SUCCESS.value, StepStatus.PARTIAL.value)
# 题量默认值（与 IntentParser.DEFAULT_QUESTION_COUNT 保持一致）
DEFAULT_QUESTION_COUNT = 5


class AgentDispatcher:
    """按计划调度专业 Agent，并记录真实执行结果."""

    def __init__(
        self,
        registry: Optional[CoreAgentRegistry] = None,
        logger: Optional[ExecutionLogger] = None,
    ) -> None:
        self.registry = registry or core_registry
        self.logger = logger or ExecutionLogger()

    # ==================== 入口 ====================

    async def dispatch(
        self,
        steps: list[PlanStep],
        intent: MasterIntent,
        context: AgentContext,
        master_task_id: str,
        by_agent: Optional[dict[str, StepOutcome]] = None,
    ) -> list[StepOutcome]:
        """按计划顺序执行（第九阶段由 WorkflowEngine 编排，本方法保留兼容）."""
        outcomes: list[StepOutcome] = []
        by_agent = by_agent if by_agent is not None else {}

        for step in steps:
            blocked = self.blocking_deps(step, by_agent)
            if blocked:
                outcome = self._skipped(
                    step,
                    f"前置步骤未成功：{'、'.join(blocked)}",
                    "已跳过，未向下游传递任何数据",
                )
            elif self.registry.get(step.agent) is None:
                outcome = self._failed(step, f"未注册的 Agent：{step.agent}")
            else:
                outcome = await self.run_step(
                    step, intent, context, master_task_id, by_agent
                )
            outcomes.append(outcome)
            by_agent[step.agent] = outcome
        return outcomes

    async def run_step(
        self,
        step: PlanStep,
        intent: MasterIntent,
        context: AgentContext,
        master_task_id: str,
        by_agent: dict[str, StepOutcome],
        extra_input: Optional[dict] = None,
        task_suffix: str = "",
    ) -> StepOutcome:
        """执行单个步骤（工作流引擎在 Self-Loop 修正轮次中复用它重跑指定步骤）.

        extra_input：在标准输入之上覆盖的参数（如补题缺口、计划调整 ID、新检索词）。
        """
        agent = self.registry.get(step.agent)
        if agent is None:
            return self._failed(step, f"未注册的 Agent：{step.agent}")

        input_data = self._build_input(step, intent, context, by_agent)
        if input_data is None:
            return self._skipped(
                step, "缺少可校验的产物，未执行",
                "可在完成计划/出题后再校验，或先提供待校验结果",
            )
        if extra_input:
            input_data = {**input_data, **extra_input}

        suffix = f"-{task_suffix}" if task_suffix else ""
        sub_task = AgentTask(
            task_id=f"{master_task_id}-{step.order}{suffix}",
            user_id=context.user_id,
            task_type=agent.task_type,
            input_data=input_data,
        )
        self.logger.log(
            master_task_id, "master",
            f"调度第 {step.order} 步 {step.agent}（{step.action}）"
            + (f"［{task_suffix}］" if task_suffix else ""),
        )
        result: AgentResult = await agent.run(sub_task, context)

        status, note = self._status_of(step.agent, result)
        outcome = StepOutcome(
            order=step.order,
            agent=step.agent,
            action=step.action,
            status=status,
            success=status in _USABLE,
            task_id=sub_task.task_id,
            execution_time=round(float(result.execution_time), 4),
            error="" if result.success else (result.error or "执行失败"),
            note=note,
            input_summary=compact(input_data),
            result=result.result,
        )
        if outcome.success:
            # 真实数据传递：把结果放进共享上下文，供后续 Agent 读取
            context.shared[step.agent] = result.result
            by_agent[step.agent] = outcome

        self.logger.log(
            master_task_id, "master",
            f"第 {step.order} 步 {step.agent} 完成：status={status}"
            + (f"，{note}" if note else ""),
            level="info" if status == StepStatus.SUCCESS.value else "warning",
        )
        return outcome

    # ==================== 依赖与状态 ====================

    @staticmethod
    def blocking_deps(step: PlanStep, by_agent: dict[str, StepOutcome]) -> list[str]:
        blocked: list[str] = []
        for dep in step.depends_on:
            outcome = by_agent.get(dep)
            if outcome is None or outcome.status not in _USABLE:
                blocked.append(f"{dep}({outcome.status if outcome else 'missing'})")
        return blocked

    @staticmethod
    def _blocking_deps(step: PlanStep, by_agent: dict[str, StepOutcome]) -> list[str]:
        """兼容旧调用名."""
        return AgentDispatcher.blocking_deps(step, by_agent)

    @staticmethod
    def _skipped(step: PlanStep, error: str, note: str = "") -> StepOutcome:
        return StepOutcome(
            order=step.order,
            agent=step.agent,
            action=step.action,
            status=StepStatus.SKIPPED.value,
            error=error,
            note=note,
        )

    @staticmethod
    def _failed(step: PlanStep, error: str) -> StepOutcome:
        return StepOutcome(
            order=step.order,
            agent=step.agent,
            action=step.action,
            status=StepStatus.FAILED.value,
            error=error,
        )

    @staticmethod
    def _status_of(agent_name: str, result: AgentResult) -> tuple[str, str]:
        """把 AgentResult 映射成步骤状态（不把失败/缩水包装成成功）."""
        if not result.success:
            return StepStatus.FAILED.value, ""

        payload = result.result if isinstance(result.result, dict) else {}

        if agent_name == TaskPlanner.AGENT_QUESTIONS:
            internal = str(payload.get("status") or "")
            if internal == "partial":
                return StepStatus.PARTIAL.value, str(payload.get("reason") or "仅部分题目生成成功")
            if internal == "failed":
                return StepStatus.FAILED.value, str(payload.get("reason") or "题目生成失败")
            return StepStatus.SUCCESS.value, ""

        if agent_name == TaskPlanner.AGENT_PLAN:
            if not payload.get("created"):
                return StepStatus.FAILED.value, str(payload.get("message") or "学习计划未保存")
            return StepStatus.SUCCESS.value, ""

        if agent_name == TaskPlanner.AGENT_ANALYSIS:
            if payload.get("sufficient") is False:
                missing = "、".join(map(str, payload.get("missing") or []))
                return StepStatus.SUCCESS.value, f"学情数据不足（{missing}），已如实上报"
            return StepStatus.SUCCESS.value, ""

        if agent_name == TaskPlanner.AGENT_RETRIEVAL:
            if payload.get("found") is False:
                return StepStatus.SUCCESS.value, str(payload.get("message") or "未检索到相关知识")
            return StepStatus.SUCCESS.value, ""

        if agent_name == TaskPlanner.AGENT_VALIDATION:
            if payload.get("passed"):
                return StepStatus.SUCCESS.value, ""
            issues = "；".join(str(i) for i in (payload.get("issues") or []))[:200]
            return StepStatus.PARTIAL.value, f"校验未通过：{issues or '存在异常项'}"
        return StepStatus.SUCCESS.value, ""

    # ==================== 输入组装（真实数据传递）====================

    def _build_input(
        self,
        step: PlanStep,
        intent: MasterIntent,
        context: AgentContext,
        by_agent: dict[str, StepOutcome],
    ) -> Optional[dict]:
        analysis = self._result_of(TaskPlanner.AGENT_ANALYSIS, by_agent)
        retrieval = self._result_of(TaskPlanner.AGENT_RETRIEVAL, by_agent)

        if step.agent == TaskPlanner.AGENT_ANALYSIS:
            # 学情分析直接读数据库中的真实数据
            return {}

        if step.agent == TaskPlanner.AGENT_RETRIEVAL:
            query = self._retrieval_query(intent, analysis)
            return {"query": query, "top_k": 3}

        if step.agent == TaskPlanner.AGENT_PLAN:
            data: dict[str, Any] = {
                "goal": intent.goal or intent.message,
            }
            if intent.exam_date is not None:
                data["exam_date"] = intent.exam_date.isoformat()
            if intent.daily_minutes is not None:
                data["daily_minutes"] = intent.daily_minutes
            if intent.subject:
                data["subject"] = intent.subject
            if analysis:
                data["analysis_result"] = analysis       # 复用真实学情，不重复调用
            if retrieval:
                data["retrieval_result"] = retrieval     # 复用真实检索内容
            return data

        if step.agent == TaskPlanner.AGENT_QUESTIONS:
            data = {
                "count": intent.question_count or DEFAULT_QUESTION_COUNT,
                "question_types": intent.question_types or None,
                "difficulty": intent.difficulty,
                "subject": intent.subject,
                "knowledge_point": intent.knowledge_point,
                "goal": intent.goal or intent.message,
                "use_weak_points": bool(
                    intent.weak_points_driven or intent.has("plan")
                ),
            }
            if analysis:
                data["analysis_result"] = analysis
            if retrieval:
                data["retrieval_result"] = retrieval
            return data

        if step.agent == TaskPlanner.AGENT_VALIDATION:
            target = step.target or TARGET_PLAN
            source = TaskPlanner.TARGET_SOURCE.get(target)
            payload = self._result_of(source, by_agent) if source else None
            if payload is None and target == TARGET_PLAN:
                payload = self._latest_plan_payload(context.db, context.user_id)
            if payload is None:
                return None
            return {"target": target, "payload": payload}

        # 其他显式指定的 Agent：把已有产物原样传入，交由 Agent 自行解析
        data = {"goal": intent.goal or intent.message}
        for name in (TaskPlanner.AGENT_ANALYSIS, TaskPlanner.AGENT_RETRIEVAL):
            value = self._result_of(name, by_agent)
            if value:
                data[f"{name}_result"] = value
        return data

    @staticmethod
    def _result_of(agent_name: Optional[str], by_agent: dict[str, StepOutcome]) -> Optional[dict]:
        if not agent_name:
            return None
        outcome = by_agent.get(agent_name)
        if outcome is None or outcome.status not in _USABLE:
            return None
        return outcome.result if isinstance(outcome.result, dict) else None

    @staticmethod
    def _retrieval_query(intent: MasterIntent, analysis: Optional[dict]) -> str:
        """检索词优先级：知识点 → 学情薄弱点 → 用户主题 → 原始消息.

        学科名（如"离散数学"）过宽，容易检索不到具体内容，因此不作为首选。
        """
        candidates: list[str] = []
        if intent.knowledge_point:
            candidates.append(intent.knowledge_point)
        if analysis:
            report = analysis.get("report") or {}
            weak = [str(w) for w in (report.get("weak_points") or []) if w]
            if weak:
                candidates.append(" ".join(weak[:3]))
        if intent.query:
            candidates.append(intent.query)
        candidates.append(intent.message)
        for value in candidates:
            if value and str(value).strip():
                return str(value).strip()
        return ""

    # ==================== 已有结果（仅校验场景）====================

    @staticmethod
    def plan_payload(
        db: Optional[Session], plan_id: int, user_id: Optional[int] = None
    ) -> Optional[dict]:
        """按 ResultValidationAgent 的 study_plan 结构读取指定计划（只读）.

        user_id 非空时做归属校验，防止跨用户读取。
        """
        if db is None:
            return None
        try:
            plan = db.get(StudyPlan, int(plan_id))
        except (TypeError, ValueError):
            return None
        if plan is None:
            return None
        if user_id is not None and plan.user_id != user_id:
            return None

        tasks = db.query(StudyTask).filter(StudyTask.plan_id == plan.id).all()
        per_day: dict[str, int] = {}
        for task in tasks:
            key = task.scheduled_date.isoformat()
            per_day[key] = per_day.get(key, 0) + int(task.estimated_minutes or 0)

        created = _as_date(plan.created_at) if plan.created_at else None
        exam = _as_date(plan.exam_date) if plan.exam_date else None
        if created and exam:
            days = max(1, (exam - created).days)
        else:
            days = max(1, len(per_day))

        return {
            "agent": TaskPlanner.AGENT_PLAN,
            "plan_id": plan.id,
            "created": True,
            "title": plan.title,
            "subject": plan.subject,
            "exam_date": exam.isoformat() if exam else None,
            "daily_minutes": int(plan.daily_minutes or 0),
            "days": days,
            "task_count": len(tasks),
            "daily_summary": {
                day: {"new": total, "existing": 0, "total": total,
                      "limit": int(plan.daily_minutes or 0)}
                for day, total in per_day.items()
            },
        }

    @classmethod
    def _latest_plan_payload(cls, db: Optional[Session], user_id: int) -> Optional[dict]:
        """读取用户最近一份计划（仅校验场景，只读）."""
        if db is None:
            return None
        plan = (
            db.query(StudyPlan)
            .filter(StudyPlan.user_id == user_id)
            .order_by(StudyPlan.id.desc())
            .first()
        )
        if plan is None:
            return None
        return cls.plan_payload(db, plan.id, user_id)

    # ==================== 日志归集 ====================

    def collect_logs(self, master_task_id: str, limit: int = 200) -> list[dict]:
        """归集主控与各专业 Agent 的本次执行日志（按任务 ID 前缀过滤）."""
        entries: list[dict] = []
        sources: list[ExecutionLogger] = [self.logger]
        for agent in self.registry.list_all():
            logger_obj = getattr(agent, "logger", None)
            if isinstance(logger_obj, ExecutionLogger) and logger_obj is not self.logger:
                sources.append(logger_obj)

        seen: set[tuple] = set()
        for logger_obj in sources:
            for entry in logger_obj.entries:
                if not str(entry.task_id).startswith(master_task_id):
                    continue
                key = (entry.task_id, entry.agent_name, entry.message, entry.created_at)
                if key in seen:
                    continue
                seen.add(key)
                entries.append({
                    "task_id": entry.task_id,
                    "agent": entry.agent_name,
                    "level": entry.level,
                    "message": entry.message,
                    "latency_ms": entry.latency_ms,
                    "created_at": entry.created_at.isoformat(timespec="seconds"),
                })
        entries.sort(key=lambda item: item["created_at"])
        return entries[-limit:]


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None



