"""主控 Agent（Master Agent）.

一次调用的完整链路：
    用户自然语言 → 意图识别 → 任务规划 → WorkflowEngine 调度专业 Agent
    → 结果校验 → Self-Loop 有限次修正 → 结果汇总 → 统一响应（并落库可追踪）

第九阶段起，编排与自我修正交给 `WorkflowEngine`，本类只负责：
参数校验、意图解析、规划、追问、落库收尾、日志清理与安全恢复入口。
"""
import json
import time
from typing import Any, Optional

from app.agents.core.base import AgentContext, BaseAgent
from app.agents.core.registry import CoreAgentRegistry, core_registry
from app.agents.core.schemas import AgentTask
from app.agents.master.intent_parser import IntentParser
from app.agents.master.recorder import MasterTaskRecorder
from app.agents.master.schemas import (
    MasterIntent,
    MasterStatus,
    PlanStep,
    StepOutcome,
    StepStatus,
)
from app.agents.master.task_planner import TaskPlanner
from app.agents.workflow import config
from app.agents.workflow.engine import WorkflowEngine
from app.core.logging import logger
from app.models import AgentTaskRecord, WorkflowRecord, WorkflowStepRecord


class MasterAgent(BaseAgent):
    """主控智能体：统一调度专业 Agent 完成复杂学习任务."""

    name = "master"
    description = "理解自然语言学习需求，规划并调度专业 Agent 协同完成，汇总统一结果"
    task_type = "master"
    max_retries = 0        # 编排型 Agent：不自动重试，避免重复写计划/题目
    timeout_s = 900.0      # 含出题与 Self-Loop 修正，留足时间

    MESSAGE_KEYS = ("message", "goal", "request", "query", "text")

    def __init__(
        self,
        logger: Optional[Any] = None,
        use_llm_intent: bool = True,
        registry: Optional[CoreAgentRegistry] = None,
        max_repair_rounds: int = config.MAX_REPAIR_ROUNDS,
    ) -> None:
        super().__init__(logger)
        self.registry = registry or core_registry
        self.intent_parser = IntentParser(use_llm=use_llm_intent)
        self.planner = TaskPlanner()
        self.engine = WorkflowEngine(
            registry=self.registry, logger=self.logger, max_rounds=max_repair_rounds
        )
        self.dispatcher = self.engine.dispatcher      # 兼容旧调用（日志归集等）

    # ==================== 统一执行入口 ====================

    async def run(self, task: AgentTask, context: AgentContext):
        """包装 BaseAgent.run：在其收尾日志之后再清理一次内存日志.

        BaseAgent.run 会在 execute 返回后追加一条"执行成功/失败"日志，
        因此需要在最外层再清理一次，确保本任务的内存日志彻底释放。
        """
        result = await super().run(task, context)
        try:
            self._cleanup_logs(task.task_id)
        except Exception as exc:      # 清理失败不影响任务结果
            logger.warning(f"[master] 收尾日志清理失败：{type(exc).__name__}: {exc}")
        return result

    async def execute(self, task: AgentTask, context: AgentContext) -> dict:
        started = time.time()
        if context.db is None:
            raise ValueError("主控 Agent 需要数据库会话（context.db 为空）")
        if task.user_id != context.user_id:
            raise ValueError("任务用户与当前登录用户不一致，已拒绝执行")

        data = task.input_data or {}
        message = self._extract_message(data)
        if not message:
            raise ValueError("缺少用户需求描述（message / goal）")

        task_id = task.task_id
        recorder = MasterTaskRecorder(context.db)
        recorder.start(
            user_id=context.user_id,
            task_id=task_id,
            message=message,
            task_type=self.task_type,
            input_data=data,
        )

        result: Optional[dict] = None
        intent = MasterIntent(message=message, goal=message)
        steps: list[PlanStep] = []
        try:
            # ---- 1. 意图识别（规则优先，LLM 兜底）----
            intent = self.intent_parser.parse(message, context.db, context.user_id)
            intent = self.intent_parser.apply_overrides(intent, data)

            # ---- 2. 任务规划 ----
            steps = self._build_plan(intent, data)

            # ---- 3. 缺少必要参数 → 追问，不执行任何专业 Agent ----
            if intent.missing_params:
                result = self._need_input(task_id, message, intent, steps, started)
                recorder.save_plan(steps)
                recorder.finish(MasterStatus.NEED_INPUT.value, result)
                self.logger.log(
                    task_id, self.name,
                    f"缺少必要参数，向用户追问：{intent.missing_params}",
                    level="warning",
                )
                return result

            if not steps:
                result = self._failed(
                    task_id, message, intent, steps,
                    "未能规划出任何可执行步骤，请补充更明确的需求。", started,
                )
                recorder.finish(MasterStatus.FAILED.value, result, "无可用执行步骤")
                return result

            # ---- 4. 记录执行计划（workflow + steps）----
            recorder.save_plan(steps)
            self.logger.log(
                task_id, self.name,
                "执行计划：" + " → ".join(
                    f"{s.order}.{s.agent}" + (f"({s.target})" if s.target else "")
                    for s in steps
                ),
            )

            # ---- 5. 工作流执行 + Self-Loop ----
            result = await self.engine.run(
                task_id=task_id,
                message=message,
                intent=intent,
                steps=steps,
                context=context,
                recorder=recorder,
                started_at=started,
            )
            self._persist_run(recorder, result)
            return result
        except Exception as exc:      # 编排级异常：如实失败，不吞错
            logger.exception(f"[master] 任务 {task_id} 执行异常: {exc}")
            if result is None:
                result = self._failed(
                    task_id, message, intent, [], f"工作流执行异常：{type(exc).__name__}: {exc}", started
                )
                recorder.finish(MasterStatus.FAILED.value, result, str(exc))
            return result
        finally:
            # ---- 7. 内存日志清理（数据库记录已在 _persist_run 中保留）----
            self._cleanup_logs(task_id)

    # ==================== 安全恢复 ====================

    async def resume(self, task_id: str, context: AgentContext) -> dict:
        """恢复中断/失败的工作流.

        规则：
        - 已完成（success/partial）的步骤不重复执行；
        - 写入型步骤即使 pending/skipped，也必须**确认没有发生过写入**才允许重跑；
        - running 且结果未知的写入步骤直接标记 failed，提示人工确认；
        - 已记录的修正轮次不重置（继续受 max_repair_rounds 约束）。
        """
        if context.db is None:
            raise ValueError("恢复工作流需要数据库会话（context.db 为空）")
        db = context.db

        record = (
            db.query(AgentTaskRecord)
            .filter(
                AgentTaskRecord.task_id == task_id,
                AgentTaskRecord.user_id == context.user_id,
            )
            .first()
        )
        if record is None:
            raise ValueError("任务不存在")
        if str(record.status) == MasterStatus.SUCCESS.value:
            raise ValueError("任务已完成，无需恢复")
        if str(record.status) == MasterStatus.NEED_INPUT.value:
            raise ValueError("任务缺少必要参数，请重新提交需求而不是恢复")

        workflow = (
            db.query(WorkflowRecord)
            .filter(WorkflowRecord.agent_task_id == record.id)
            .order_by(WorkflowRecord.id.desc())
            .first()
        )
        if workflow is None:
            raise ValueError("该任务没有可恢复的执行计划")

        steps = self._load_steps(workflow)
        if not steps:
            raise ValueError("执行计划损坏，无法恢复")

        rows = (
            db.query(WorkflowStepRecord)
            .filter(WorkflowStepRecord.workflow_id == workflow.id)
            .all()
        )
        rows_by_order = {int(row.step_order): row for row in rows}

        previous = _loads(record.result_json) or {}
        intent = self._rebuild_intent(previous, record.title)

        started = time.time()
        recorder = MasterTaskRecorder(db)
        recorder.load(record, workflow)
        recorder.set_status(MasterStatus.RUNNING.value)
        self.logger.log(task_id, self.name, "开始恢复工作流")

        prior = self._build_prior(steps, rows_by_order, previous)
        result = await self.engine.run(
            task_id=task_id,
            message=str(previous.get("original_request") or record.title or ""),
            intent=intent,
            steps=steps,
            context=context,
            recorder=recorder,
            started_at=started,
            resume_rows=rows_by_order,
            prior=prior,
        )
        result["resumed"] = True
        self._persist_run(recorder, result)
        self._cleanup_logs(task_id)
        return result

    # ==================== 内部：计划与结果 ====================

    @classmethod
    def _extract_message(cls, data: dict) -> str:
        for key in cls.MESSAGE_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _build_plan(self, intent: MasterIntent, data: dict) -> list[PlanStep]:
        """显式指定 agents 时按指定顺序执行，否则按意图自动规划."""
        requested = data.get("agents")
        if isinstance(requested, (list, tuple)) and requested:
            steps = self.planner.build_explicit([str(a) for a in requested], intent)
            if steps:
                return steps
        return self.planner.build(intent)

    def _persist_run(self, recorder: MasterTaskRecorder, result: dict) -> None:
        """把日志、Self-Loop 轮次与最终结果写入数据库."""
        recorder.save_logs(result.get("execution_logs") or [])
        self_loop = (result.get("final_result") or {}).get("self_loop") or {}
        recorder.save_evaluations(self_loop.get("rounds") or [])
        recorder.finish(result.get("task_status") or MasterStatus.FAILED.value, result)

    def _cleanup_logs(self, task_id: str) -> None:
        """按 task_id 前缀清理内存日志（不影响其它并发任务）."""
        if not config.LOG_CLEANUP_ENABLED:
            return
        loggers = [self.logger]
        for agent in self.registry.list_all():
            agent_logger = getattr(agent, "logger", None)
            if agent_logger is not None and agent_logger is not self.logger:
                loggers.append(agent_logger)
        removed = 0
        for instance in loggers:
            clear = getattr(instance, "clear_task", None)
            if callable(clear):
                try:
                    removed += int(clear(task_id) or 0)
                except Exception as exc:        # 清理失败不影响任务结果
                    logger.warning(f"[master] 清理内存日志失败：{type(exc).__name__}: {exc}")
        if removed:
            logger.debug(f"[master] 已清理 task={task_id} 的内存日志 {removed} 条")

    # ==================== 内部：恢复辅助 ====================

    @staticmethod
    def _load_steps(workflow: WorkflowRecord) -> list[PlanStep]:
        raw = _loads(workflow.plan_json)
        if not isinstance(raw, list):
            return []
        steps: list[PlanStep] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                steps.append(PlanStep(**item))
            except (TypeError, ValueError):
                continue
        return steps

    @staticmethod
    def _rebuild_intent(previous: dict, title: str) -> MasterIntent:
        raw = previous.get("parsed_intent")
        intent = MasterIntent()
        if isinstance(raw, dict):
            try:
                intent = MasterIntent.model_validate(raw)
            except (TypeError, ValueError):
                intent = MasterIntent()
        if not intent.message:
            intent.message = str(previous.get("original_request") or title or "")
        if not intent.intents:
            intent.intents = ["analysis"]
        return intent

    @staticmethod
    def _build_prior(
        steps: list[PlanStep],
        rows_by_order: dict,
        previous: dict,
    ) -> dict:
        """把已完成的步骤结果还原成引擎可用的 prior 状态（不重跑已完成步骤）."""
        outcomes: list[StepOutcome] = []
        by_agent: dict[str, StepOutcome] = {}
        validation: dict[str, StepOutcome] = {}
        targets = {step.order: step.target for step in steps}

        for step in steps:
            row = rows_by_order.get(step.order)
            if row is None:
                continue
            status = str(row.status or "")
            if status not in (
                StepStatus.SUCCESS.value, StepStatus.PARTIAL.value
            ):
                continue
            payload = _loads(row.output_json)
            if payload is None:
                continue        # 输出被截断/损坏 → 交给写入确认逻辑处理
            elapsed = 0.0
            if row.started_at and row.finished_at:
                elapsed = (row.finished_at - row.started_at).total_seconds()
            outcome = StepOutcome(
                order=step.order,
                agent=step.agent,
                action=step.action,
                status=status,
                success=True,
                task_id=f"{previous.get('task_id') or ''}-{step.order}-resumed",
                execution_time=round(elapsed, 4),
                note="恢复：该步骤此前已完成，不重复执行",
                input_summary=_loads(row.input_json) or {},
                result=payload,
            )
            outcomes.append(outcome)
            by_agent[step.agent] = outcome
            if step.target:
                validation[step.target] = outcome

        self_loop = (previous.get("final_result") or {}).get("self_loop") or {}
        rounds = list(self_loop.get("rounds") or [])
        artifact_rounds: dict[str, int] = {}
        retrieval_rounds = 0
        for item in rounds:
            target = str(item.get("target") or "")
            if not target:
                continue
            artifact_rounds[target] = artifact_rounds.get(target, 0) + 1
            if target == TaskPlanner.AGENT_RETRIEVAL:
                retrieval_rounds += 1

        return {
            "outcomes": outcomes,
            "by_agent": by_agent,
            "validation": validation,
            "rounds": rounds,
            "artifact_rounds": artifact_rounds,
            "retrieval_rounds": retrieval_rounds,
        }

    # ==================== 内部：非执行分支 ====================

    def _need_input(
        self,
        task_id: str,
        message: str,
        intent: MasterIntent,
        steps: list[PlanStep],
        started: float,
    ) -> dict:
        questions = {
            "exam_date": "考试日期是哪一天？（也可以直接说“还有几天考试”）",
            "daily_minutes": "每天大概能安排多少分钟学习？（例如“每天2小时”）",
        }
        pending = [
            questions.get(name, f"请补充参数：{name}") for name in intent.missing_params
        ]
        summary = (
            "需要补充信息后才能继续：\n"
            + "\n".join(f"- {item}" for item in pending)
            + "\n已识别到的需求：" + "、".join(intent.intents or ["未识别"])
        )
        return {
            "task_id": task_id,
            "task_status": MasterStatus.NEED_INPUT.value,
            "original_request": message,
            "parsed_intent": intent.model_dump(mode="json"),
            "execution_plan": [step.public() for step in steps],
            "executed_agents": [],
            "agent_results": [],
            "execution_logs": [],
            "execution_time": round(time.time() - started, 4),
            "final_result": {
                "summary": summary,
                "artifacts": {},
                "validations": [],
                "warnings": list(intent.assumptions),
                "issues": [],
                "assumptions": list(intent.assumptions),
                "next_actions": pending,
                "pending_questions": pending,
                "self_loop": {
                    "enabled": False, "rounds": [], "repair_count": 0,
                    "stopped_reason": "", "max_repair_rounds": config.MAX_REPAIR_ROUNDS,
                },
                "cancelled": False,
            },
        }

    def _failed(
        self,
        task_id: str,
        message: str,
        intent: MasterIntent,
        steps: list[PlanStep],
        reason: str,
        started: float,
    ) -> dict:
        return {
            "task_id": task_id,
            "task_status": MasterStatus.FAILED.value,
            "original_request": message,
            "parsed_intent": intent.model_dump(mode="json"),
            "execution_plan": [step.public() for step in steps],
            "executed_agents": [],
            "agent_results": [],
            "execution_logs": [],
            "execution_time": round(time.time() - started, 4),
            "final_result": {
                "summary": f"执行失败：{reason}",
                "artifacts": {},
                "validations": [],
                "warnings": list(intent.assumptions),
                "issues": [reason],
                "assumptions": list(intent.assumptions),
                "next_actions": [reason],
                "pending_questions": [],
                "self_loop": {
                    "enabled": False, "rounds": [], "repair_count": 0,
                    "stopped_reason": "failed", "max_repair_rounds": config.MAX_REPAIR_ROUNDS,
                },
                "cancelled": False,
            },
        }


def _loads(text: Optional[str]) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None
