"""主控任务落库（Recorder）.

只复用第四阶段已建好的新体系表，不新增任何数据库表：
- agent_tasks          一次用户任务（原始输入 / 最终结果 / 状态）
- workflows            该任务的执行计划（步骤与依赖）
- workflow_steps       每个步骤：执行 Agent、输入输出、状态、耗时
- agent_execution_logs 细粒度执行日志

所有写入都带异常兜底：落库失败不会让业务结果丢失，只记录告警。
用户隔离：所有记录通过 agent_tasks.user_id 关联到当前登录用户。
"""
import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.master.schemas import PlanStep, StepOutcome
from app.core.logging import logger
from app.models import (
    AgentEvaluation,
    AgentExecutionLog,
    AgentTaskRecord,
    WorkflowRecord,
    WorkflowStepRecord,
)


class MasterTaskRecorder:
    """把主控任务的执行过程写入数据库（可追踪、可回放）."""

    OUTPUT_LIMIT = 50000      # 单步输出落库上限（字符）
    LOG_LIMIT = 200           # 单次任务写入日志条数上限

    def __init__(self, db: Optional[Session]) -> None:
        self.db = db
        self.record: Optional[AgentTaskRecord] = None
        self.workflow: Optional[WorkflowRecord] = None
        self.step_rows: dict[int, WorkflowStepRecord] = {}

    # ==================== 任务主记录 ====================

    def start(
        self,
        *,
        user_id: int,
        task_id: str,
        message: str,
        task_type: str = "master",
        input_data: Optional[dict] = None,
    ) -> Optional[AgentTaskRecord]:
        if self.db is None:
            return None
        try:
            record = AgentTaskRecord(
                task_id=task_id,
                user_id=user_id,
                title=message[:200],
                task_type=task_type,
                input_json=_dump(input_data or {}),
                status="running",
            )
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            self.record = record
            return record
        except Exception as exc:
            self._rollback("任务记录创建失败", exc)
            return None

    def save_plan(self, steps: list[PlanStep]) -> Optional[WorkflowRecord]:
        if self.db is None or self.record is None:
            return None
        try:
            workflow = WorkflowRecord(
                agent_task_id=self.record.id,
                status="running",
                plan_json=_dump([step.model_dump(mode="json") for step in steps]),
                started_at=datetime.utcnow(),
            )
            self.db.add(workflow)
            self.db.flush()

            for step in steps:
                row = WorkflowStepRecord(
                    workflow_id=workflow.id,
                    agent_name=step.agent,
                    step_order=step.order,
                    depends_on=_dump(step.depends_on),
                    status="pending",
                )
                self.db.add(row)
                self.db.flush()
                self.step_rows[step.order] = row
            self.db.commit()
            self.workflow = workflow
            return workflow
        except Exception as exc:
            self._rollback("执行计划落库失败", exc)
            return None

    # ==================== 步骤与日志 ====================

    def update_step(self, outcome: StepOutcome) -> None:
        row = self.step_rows.get(outcome.order)
        if self.db is None or row is None:
            return
        try:
            row.status = outcome.status
            row.error = (outcome.error or outcome.note or "")[:2000] or None
            row.input_json = _dump(outcome.input_summary)
            row.output_json = _dump(outcome.result, limit=self.OUTPUT_LIMIT)
            row.started_at = row.started_at or datetime.utcnow()
            row.finished_at = datetime.utcnow()
            self.db.commit()
        except Exception as exc:
            self._rollback(f"步骤 {outcome.agent} 落库失败", exc)

    def save_logs(self, logs: list[dict]) -> int:
        if self.db is None or self.record is None or not logs:
            return 0
        try:
            rows = [
                AgentExecutionLog(
                    agent_task_id=self.record.id,
                    step_id=None,
                    agent_name=str(item.get("agent") or "master")[:64],
                    level=str(item.get("level") or "info")[:16],
                    message=str(item.get("message") or "")[:4000],
                    latency_ms=int(item.get("latency_ms") or 0),
                )
                for item in logs[-self.LOG_LIMIT:]
            ]
            self.db.add_all(rows)
            self.db.commit()
            return len(rows)
        except Exception as exc:
            self._rollback("执行日志落库失败", exc)
            return 0

    # ==================== 状态与 Self-Loop 记录 ====================

    def is_cancelled(self) -> bool:
        """轻量读取任务状态：用户是否已请求取消（不依赖对象缓存）."""
        if self.db is None or self.record is None:
            return False
        try:
            status = (
                self.db.query(AgentTaskRecord.status)
                .filter(AgentTaskRecord.id == self.record.id)
                .scalar()
            )
        except Exception:      # 查询失败不应影响工作流
            return False
        return str(status) == "cancelled"

    def set_status(self, status: str, error: str = "") -> None:
        """只更新状态（取消/恢复接口用，避免覆盖已有结果）."""
        if self.db is None or self.record is None:
            return
        try:
            self.record.status = status
            if error:
                self.record.error = error[:2000]
            if self.workflow is not None:
                self.workflow.status = status
            self.db.commit()
        except Exception as exc:
            self._rollback("任务状态更新失败", exc)

    def step_row(self, order: int) -> Optional[WorkflowStepRecord]:
        return self.step_rows.get(order)

    def save_evaluations(self, rounds: list[dict]) -> int:
        """把 Self-Loop 每一轮修正写入 agent_evaluations（复用已有表）."""
        if self.db is None or self.record is None or not rounds:
            return 0
        try:
            rows = []
            for item in rounds:
                validation = item.get("validation") or {}
                rows.append(AgentEvaluation(
                    agent_task_id=self.record.id,
                    step_id=None,
                    agent_name=str(item.get("target") or "self_loop")[:64],
                    attempt=int(item.get("round") or 1),
                    passed=bool(validation.get("passed")),
                    score=validation.get("score"),
                    feedback=str(item.get("note") or item.get("failure_label") or "")[:2000],
                    checks_json=_dump(item, limit=self.OUTPUT_LIMIT),
                ))
            self.db.add_all(rows)
            self.db.commit()
            return len(rows)
        except Exception as exc:
            self._rollback("Self-Loop 记录落库失败", exc)
            return 0

    def load(self, record: AgentTaskRecord, workflow: Optional[WorkflowRecord]) -> None:
        """恢复工作流时，把已有记录挂到 recorder 上（不新建）."""
        if self.db is None:
            return
        self.record = record
        self.workflow = workflow
        self.step_rows = {}
        if workflow is None:
            return
        try:
            rows = (
                self.db.query(WorkflowStepRecord)
                .filter(WorkflowStepRecord.workflow_id == workflow.id)
                .all()
            )
            self.step_rows = {int(row.step_order): row for row in rows}
        except Exception as exc:
            self._rollback("读取历史步骤失败", exc)

    # ==================== 收尾 ====================

    def finish(
        self,
        status: str,
        result: Optional[dict] = None,
        error: str = "",
    ) -> None:
        if self.db is None or self.record is None:
            return
        try:
            self.record.status = status
            self.record.result_json = _dump(result, limit=self.OUTPUT_LIMIT)
            self.record.error = error[:2000] or None
            self.record.completed_at = datetime.utcnow()
            if self.workflow is not None:
                self.workflow.status = status
                self.workflow.finished_at = datetime.utcnow()
            self.db.commit()
        except Exception as exc:
            self._rollback("任务结果落库失败", exc)

    # ==================== 内部 ====================

    def _rollback(self, title: str, exc: Exception) -> None:
        """落库失败：回滚当前事务并告警，不影响已产生的业务结果."""
        logger.warning(f"[master] {title}：{type(exc).__name__}: {exc}")
        try:
            if self.db is not None:
                self.db.rollback()
        except Exception:  # 会话不可用时忽略
            pass


def _dump(payload: Any, limit: int = 20000) -> str:
    """安全序列化：日期/模型等不可序列化对象转字符串，超长截断."""
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(payload)
    return text[:limit]
