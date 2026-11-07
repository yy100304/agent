"""学习任务 API（Dashboard 今日任务 / 学习计划页共用）."""
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import KnowledgePoint, StudyPlan, StudyTask, User
from app.schemas.question import TaskOut
from app.services.learning_service import LearningService

router = APIRouter()


@router.get("", response_model=List[TaskOut])
def list_tasks(
    date_str: Optional[str] = Query(default=None, alias="date"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[TaskOut]:
    """任务列表：默认今天，可指定日期，范围今天起 7 天."""
    try:
        target = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    rows = (
        db.query(StudyTask, KnowledgePoint)
        .outerjoin(KnowledgePoint, StudyTask.knowledge_point_id == KnowledgePoint.id)
        .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
        .filter(
            StudyPlan.user_id == current_user.id,
            StudyTask.scheduled_date == target,
        )
        .order_by(StudyTask.completed.asc(), StudyTask.id.asc())
        .all()
    )
    return [
        TaskOut(
            id=t.id,
            plan_id=t.plan_id,
            knowledge_point_id=t.knowledge_point_id,
            knowledge_point_name=kp.name if kp else None,
            title=t.title,
            description=t.description,
            estimated_minutes=t.estimated_minutes,
            completed=t.completed,
            scheduled_date=datetime.combine(t.scheduled_date, datetime.min.time()),
        )
        for t, kp in rows
    ]


@router.put("/{task_id}/complete", response_model=TaskOut)
def complete_task(
    task_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    """完成任务：标记完成并记入学习记录（学习时长 = 预估时长）."""
    task = (
        db.query(StudyTask)
        .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
        .filter(StudyTask.id == task_id, StudyPlan.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if not task.completed:
        task.completed = True
        task.completed_at = datetime.utcnow()
        # 记录学习行为
        learning = LearningService(db)
        learning.add_record(
            current_user.id,
            task.knowledge_point_id,
            task.estimated_minutes,
            source="task",
        )
        db.commit()
        logger.info(f"任务完成 user={current_user.id} task={task_id}")

    db.refresh(task)
    kp = db.get(KnowledgePoint, task.knowledge_point_id) if task.knowledge_point_id else None
    return TaskOut(
        id=task.id,
        plan_id=task.plan_id,
        knowledge_point_id=task.knowledge_point_id,
        knowledge_point_name=kp.name if kp else None,
        title=task.title,
        description=task.description,
        estimated_minutes=task.estimated_minutes,
        completed=task.completed,
        scheduled_date=datetime.combine(task.scheduled_date, datetime.min.time()),
    )