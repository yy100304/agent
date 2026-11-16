"""主控 Agent 任务 API（/api/agent/tasks）.

职责：
- POST   /api/agent/tasks          提交一句自然语言学习需求，由主控 Agent 规划并调度
- GET    /api/agent/tasks          当前用户的历史任务列表（严格用户隔离）
- GET    /api/agent/tasks/{id}     任务详情：执行计划、步骤、日志与最终结果

说明：
- 复用统一注册表获取主控 Agent，不在接口层硬编码业务逻辑；
- 所有查询都以当前登录用户为过滤条件，不同用户互相不可见；
- 旧的 /api/agent/chat（SSE）保持原样，不删除、不改动。
"""
import json
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.core.base import AgentContext
from app.agents.core.registry import core_registry
from app.agents.core.schemas import AgentTask
from app.agents.registration import register_core_agents
from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import (
    AgentEvaluation,
    AgentExecutionLog,
    AgentTaskRecord,
    User,
    WorkflowRecord,
    WorkflowStepRecord,
)

router = APIRouter()


# ---- 请求模型 ----

class MasterTaskRequest(BaseModel):
    """提交给主控 Agent 的需求.

    message：自然语言需求（必填）；
    options：可选的显式参数（exam_date / daily_minutes / count / question_types /
    difficulty / subject / knowledge_point / agents），优先级高于自然语言解析。
    """

    message: str = Field(..., min_length=1, max_length=4000)
    options: dict[str, Any] = Field(default_factory=dict)


# ---- POST /api/agent/tasks ----

@router.post("")
async def create_master_task(
    payload: MasterTaskRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    """提交自然语言学习需求，返回主控 Agent 的统一执行结果."""
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="需求描述不能为空")

    register_core_agents()
    master = core_registry.get("master")
    if master is None:
        raise HTTPException(status_code=503, detail="主控 Agent 未就绪")

    input_data: dict[str, Any] = {"message": message}
    for key, value in (payload.options or {}).items():
        if value is not None:
            input_data[key] = value

    task = AgentTask(
        task_id=str(uuid.uuid4()),
        user_id=current_user.id,       # 身份由登录态决定，前端不可伪造
        task_type="master",
        input_data=input_data,
    )
    context = AgentContext(
        user_id=current_user.id,
        username=current_user.username,
        db=db,
        request={"message": message},
    )
    logger.info(
        f"[master-api] user={current_user.username} task={task.task_id} "
        f"message={message[:40]}"
    )

    result = await master.run(task, context)
    if not result.success or not isinstance(result.result, dict):
        raise HTTPException(
            status_code=500,
            detail=f"主控 Agent 执行失败：{result.error or '未返回有效结果'}",
        )
    return result.result


# ---- GET /api/agent/tasks ----

@router.get("")
def list_master_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    """当前用户最近的 Agent 任务（任务记录严格按用户隔离）."""
    rows = (
        db.query(AgentTaskRecord)
        .filter(AgentTaskRecord.user_id == current_user.id)
        .order_by(AgentTaskRecord.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_task_brief(row) for row in rows]


# ---- GET /api/agent/tasks/{task_id} ----

@router.get("/{task_id}")
def get_master_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    """任务详情：执行计划、各步骤状态与原始输出、执行日志、最终结果."""
    record = (
        db.query(AgentTaskRecord)
        .filter(
            AgentTaskRecord.task_id == task_id,
            AgentTaskRecord.user_id == current_user.id,
        )
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    workflow = (
        db.query(WorkflowRecord)
        .filter(WorkflowRecord.agent_task_id == record.id)
        .order_by(WorkflowRecord.id.desc())
        .first()
    )
    steps: list[dict] = []
    if workflow is not None:
        rows = (
            db.query(WorkflowStepRecord)
            .filter(WorkflowStepRecord.workflow_id == workflow.id)
            .order_by(WorkflowStepRecord.step_order.asc())
            .all()
        )
        steps = [_step_view(row) for row in rows]

    logs = (
        db.query(AgentExecutionLog)
        .filter(AgentExecutionLog.agent_task_id == record.id)
        .order_by(AgentExecutionLog.id.asc())
        .limit(300)
        .all()
    )

    evaluations = (
        db.query(AgentEvaluation)
        .filter(AgentEvaluation.agent_task_id == record.id)
        .order_by(AgentEvaluation.attempt.asc(), AgentEvaluation.id.asc())
        .limit(50)
        .all()
    )

    return {
        **_task_brief(record),
        "input": _loads(record.input_json),
        "plan": _loads(workflow.plan_json) if workflow is not None else None,
        "steps": steps,
        "evaluations": [
            {
                "round": item.attempt,
                "target": item.agent_name,
                "passed": item.passed,
                "score": item.score,
                "feedback": item.feedback,
                "detail": _loads(item.checks_json),
            }
            for item in evaluations
        ],
        "logs": [
            {
                "agent": log.agent_name,
                "level": log.level,
                "message": log.message,
                "latency_ms": log.latency_ms,
                "created_at": log.created_at.isoformat(timespec="seconds")
                if log.created_at else "",
            }
            for log in logs
        ],
        "result": _loads(record.result_json),
    }


# ---- POST /api/agent/tasks/{task_id}/cancel ----

@router.post("/{task_id}/cancel")
def cancel_master_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    """请求取消任务.

    只置状态位，不强制终止正在执行的数据库事务：
    工作流会在**当前步骤安全提交/回滚之后**停止后续步骤，已写入的数据保持完整。
    """
    record = (
        db.query(AgentTaskRecord)
        .filter(
            AgentTaskRecord.task_id == task_id,
            AgentTaskRecord.user_id == current_user.id,
        )
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    status = str(record.status)
    if status == "cancelled":
        return {"task_id": task_id, "status": status, "detail": "任务已处于取消状态"}
    if status not in ("pending", "running"):
        raise HTTPException(
            status_code=409, detail=f"任务当前状态为 {status}，无法取消"
        )

    record.status = "cancelled"
    workflow = (
        db.query(WorkflowRecord)
        .filter(WorkflowRecord.agent_task_id == record.id)
        .order_by(WorkflowRecord.id.desc())
        .first()
    )
    if workflow is not None:
        workflow.status = "cancelled"
    db.commit()
    logger.info(f"[master-api] user={current_user.username} cancel task={task_id}")
    return {"task_id": task_id, "status": "cancelled", "detail": "已提交取消请求"}


# ---- POST /api/agent/tasks/{task_id}/resume ----

@router.post("/{task_id}/resume")
async def resume_master_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    """安全恢复中断/失败的任务.

    - 已完成步骤不重复执行；
    - 写入型步骤必须先确认没有发生过写入才允许重跑；
    - 结果未知的写入步骤会被标记为 failed，需人工确认。
    """
    register_core_agents()
    master = core_registry.get("master")
    if master is None:
        raise HTTPException(status_code=503, detail="主控 Agent 未就绪")

    context = AgentContext(
        user_id=current_user.id,
        username=current_user.username,
        db=db,
        request={"resume_task_id": task_id},
    )
    try:
        result = await master.resume(task_id, context)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    logger.info(f"[master-api] user={current_user.username} resume task={task_id}")
    return result


# ---- 视图辅助 ----

def _task_brief(record: AgentTaskRecord) -> dict:
    return {
        "task_id": record.task_id,
        "title": record.title,
        "task_type": record.task_type,
        "status": record.status,
        "error": record.error,
        "created_at": record.created_at.isoformat(timespec="seconds")
        if record.created_at else "",
        "completed_at": record.completed_at.isoformat(timespec="seconds")
        if record.completed_at else None,
    }


def _step_view(row: WorkflowStepRecord) -> dict:
    return {
        "agent": row.agent_name,
        "order": row.step_order,
        "depends_on": _loads(row.depends_on) or [],
        "status": row.status,
        "error": row.error,
        "input": _loads(row.input_json),
        "output": _loads(row.output_json),
        "started_at": row.started_at.isoformat(timespec="seconds")
        if row.started_at else None,
        "finished_at": row.finished_at.isoformat(timespec="seconds")
        if row.finished_at else None,
    }


def _loads(text: Optional[str]) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text
