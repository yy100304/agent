"""学习计划 API（第一阶段：列表查询，供 Dashboard 倒计时与计划页使用）."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.database.session import get_db
from app.models import StudyPlan, User

router = APIRouter()


class StudyPlanOut(BaseModel):
    id: int
    title: str
    subject: str
    exam_date: Optional[date] = None
    daily_minutes: int
    status: str

    model_config = ConfigDict(from_attributes=True)


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