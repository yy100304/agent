"""学习计划 API：列表 / 详情 / 手动新建与维护（计划 + 每日任务）."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import KnowledgePoint, StudyPlan, StudyTask, User

router = APIRouter()


class StudyPlanOut(BaseModel):
    id: int
    title: str
    subject: str
    exam_date: Optional[date] = None
    daily_minutes: int
    status: str
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PlanTaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    estimated_minutes: int
    completed: bool
    scheduled_date: date
    knowledge_point_id: Optional[int] = None
    knowledge_point_name: Optional[str] = None


class StudyPlanDetail(StudyPlanOut):
    tasks: List[PlanTaskOut]
    total_tasks: int
    completed_tasks: int
    progress: float
    days_left: Optional[int] = None
    examination: bool = False
    adjustment_log: Optional[str] = None


class StudyPlanCreate(BaseModel):
    """手动新建计划：只填用户自己关心的几项，其余用默认值."""

    title: str = Field(min_length=1, max_length=128)
    subject: Optional[str] = Field(default=None, max_length=64)
    exam_date: Optional[date] = None
    daily_minutes: int = Field(default=60, ge=10, le=720)
    description: Optional[str] = Field(default=None, max_length=5000)


class StudyPlanUpdate(BaseModel):
    """修改计划基本信息（只更新传了的字段）."""

    title: Optional[str] = Field(default=None, max_length=128)
    subject: Optional[str] = Field(default=None, max_length=64)
    exam_date: Optional[date] = None
    daily_minutes: Optional[int] = Field(default=None, ge=10, le=720)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[str] = Field(default=None, pattern="^(active|completed|archived)$")


class PlanTaskCreate(BaseModel):
    """手动添加任务：日期不填就排到今天."""

    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    scheduled_date: Optional[date] = None
    estimated_minutes: int = Field(default=30, ge=5, le=600)


class PlanTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    scheduled_date: Optional[date] = None
    estimated_minutes: Optional[int] = Field(default=None, ge=5, le=600)
    completed: Optional[bool] = None


def _own_plan(db: Session, user_id: int, plan_id: int) -> StudyPlan:
    plan = (
        db.query(StudyPlan)
        .filter(StudyPlan.id == plan_id, StudyPlan.user_id == user_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="学习计划不存在")
    return plan


def _own_task(db: Session, user_id: int, task_id: int) -> StudyTask:
    task = (
        db.query(StudyTask)
        .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
        .filter(StudyTask.id == task_id, StudyPlan.user_id == user_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


def _task_out(task: StudyTask, kp: Optional[KnowledgePoint] = None) -> PlanTaskOut:
    return PlanTaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        estimated_minutes=task.estimated_minutes,
        completed=task.completed,
        scheduled_date=task.scheduled_date,
        knowledge_point_id=task.knowledge_point_id,
        knowledge_point_name=kp.name if kp else None,
    )


@router.get("", response_model=List[StudyPlanOut])
def list_study_plans(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[StudyPlanOut]:
    """当前用户的学习计划列表."""
    query = db.query(StudyPlan).filter(StudyPlan.user_id == current_user.id)
    if status_filter:
        query = query.filter(StudyPlan.status == status_filter)
    plans = query.order_by(StudyPlan.created_at.desc()).all()
    return [StudyPlanOut.model_validate(p) for p in plans]


@router.get("/{plan_id}", response_model=StudyPlanDetail)
def get_study_plan(
    plan_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StudyPlanDetail:
    """计划详情：按日期分组的任务、完成进度、考试倒计时."""
    plan = (
        db.query(StudyPlan)
        .filter(StudyPlan.id == plan_id, StudyPlan.user_id == current_user.id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="学习计划不存在")

    rows = (
        db.query(StudyTask, KnowledgePoint)
        .outerjoin(KnowledgePoint, StudyTask.knowledge_point_id == KnowledgePoint.id)
        .filter(StudyTask.plan_id == plan.id)
        .order_by(StudyTask.scheduled_date.asc(), StudyTask.id.asc())
        .all()
    )
    tasks = [
        PlanTaskOut(
            id=task.id,
            title=task.title,
            description=task.description,
            estimated_minutes=task.estimated_minutes,
            completed=task.completed,
            scheduled_date=task.scheduled_date,
            knowledge_point_id=task.knowledge_point_id,
            knowledge_point_name=kp.name if kp else None,
        )
        for task, kp in rows
    ]
    total = len(tasks)
    done = sum(1 for t in tasks if t.completed)
    return StudyPlanDetail(
        id=plan.id,
        title=plan.title,
        subject=plan.subject,
        exam_date=plan.exam_date,
        daily_minutes=plan.daily_minutes,
        status=plan.status,
        description=plan.description,
        tasks=tasks,
        total_tasks=total,
        completed_tasks=done,
        progress=round(done / total, 3) if total else 0.0,
        days_left=(plan.exam_date - date.today()).days if plan.exam_date else None,
        examination=bool(plan.exam_date),
        adjustment_log=plan.adjustment_log,
    )


# ===== 手动维护：计划与任务都由用户自己写，Agent 生成只是可选入口 =====


@router.post("", response_model=StudyPlanOut, status_code=status.HTTP_201_CREATED)
def create_study_plan(
    payload: StudyPlanCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StudyPlanOut:
    """新建一份空白计划，任务由用户自己往里面填."""
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="计划名称不能为空")
    subject = (payload.subject or "").strip() or "通用"
    plan = StudyPlan(
        user_id=current_user.id,
        title=title[:128],
        subject=subject[:64],
        exam_date=payload.exam_date,
        daily_minutes=payload.daily_minutes,
        description=(payload.description or "").strip() or None,
        status="active",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    logger.info(f"学习计划已创建 user={current_user.id} plan={plan.id}")
    return StudyPlanOut.model_validate(plan)


@router.patch("/{plan_id}", response_model=StudyPlanOut)
def update_study_plan(
    plan_id: int,
    payload: StudyPlanUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StudyPlanOut:
    """修改计划基本信息（标题 / 科目 / 考试日期 / 每日时长 / 状态）."""
    plan = _own_plan(db, current_user.id, plan_id)

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="计划名称不能为空")
        plan.title = title[:128]
    if payload.subject is not None and payload.subject.strip():
        plan.subject = payload.subject.strip()[:64]
    if payload.exam_date is not None:
        plan.exam_date = payload.exam_date
    if payload.daily_minutes is not None:
        plan.daily_minutes = payload.daily_minutes
    if payload.description is not None:
        plan.description = payload.description.strip() or None
    if payload.status is not None:
        plan.status = payload.status

    db.commit()
    db.refresh(plan)
    return StudyPlanOut.model_validate(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_study_plan(
    plan_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """删除计划（连同其下所有任务）."""
    plan = _own_plan(db, current_user.id, plan_id)
    db.delete(plan)
    db.commit()
    logger.info(f"学习计划已删除 user={current_user.id} plan={plan_id}")


@router.post(
    "/{plan_id}/tasks", response_model=PlanTaskOut, status_code=status.HTTP_201_CREATED
)
def create_plan_task(
    plan_id: int,
    payload: PlanTaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> PlanTaskOut:
    """给计划手动加一条任务（哪天做、做什么、大概多久）."""
    plan = _own_plan(db, current_user.id, plan_id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="任务内容不能为空")

    task = StudyTask(
        plan_id=plan.id,
        title=title[:255],
        description=(payload.description or "").strip() or None,
        estimated_minutes=payload.estimated_minutes,
        scheduled_date=payload.scheduled_date or date.today(),
        completed=False,
    )
    db.add(task)
    # 有任务动过了，计划重新激活
    if plan.status != "active":
        plan.status = "active"
    db.commit()
    db.refresh(task)
    return _task_out(task)


@router.patch("/tasks/{task_id}", response_model=PlanTaskOut)
def update_plan_task(
    task_id: int,
    payload: PlanTaskUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> PlanTaskOut:
    """改任务内容 / 挪日期 / 调整时长，也可用于取消完成状态."""
    task = _own_task(db, current_user.id, task_id)

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="任务内容不能为空")
        task.title = title[:255]
    if payload.description is not None:
        task.description = payload.description.strip() or None
    if payload.scheduled_date is not None:
        task.scheduled_date = payload.scheduled_date
    if payload.estimated_minutes is not None:
        task.estimated_minutes = payload.estimated_minutes
    if payload.completed is not None:
        task.completed = payload.completed
        task.completed_at = None if not payload.completed else task.completed_at

    db.commit()
    db.refresh(task)
    kp = db.get(KnowledgePoint, task.knowledge_point_id) if task.knowledge_point_id else None
    return _task_out(task, kp)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """删除一条任务."""
    task = _own_task(db, current_user.id, task_id)
    db.delete(task)
    db.commit()
