"""Dashboard API：学习看板（今日任务 + 状态概览 + 趋势 + Agent 建议）."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import User
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("", response_model=DashboardSummary)
def get_dashboard(
    subject: Optional[str] = Query(default=None, max_length=64, description="按科目过滤计划/今日任务"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    """获取学习看板汇总数据（全部来自真实学习数据）."""
    logger.info(f"获取 Dashboard：user={current_user.username} subject={subject}")
    summary = DashboardService(db).build_summary(current_user, subject=subject)
    return DashboardSummary(**summary)