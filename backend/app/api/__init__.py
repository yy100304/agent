"""API 路由集合."""
from fastapi import APIRouter

from app.api import (
    auth,
    dashboard,
    knowledge_points,
    questions,
    study_plans,
    tasks,
    user,
    wrong_questions,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(knowledge_points.router, prefix="/knowledge-points", tags=["knowledge-points"])
api_router.include_router(questions.router, prefix="/questions", tags=["questions"])
api_router.include_router(wrong_questions.router, prefix="/wrong-questions", tags=["wrong-questions"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(study_plans.router, prefix="/study-plans", tags=["study-plans"])

__all__ = ["api_router"]