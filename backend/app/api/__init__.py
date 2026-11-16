"""API 路由集合."""
from fastapi import APIRouter

from app.api import (
    agent,
    agent_tasks,
    auth,
    dashboard,
    knowledge_docs,
    knowledge_points,
    questions,
    study_plans,
    subjects,
    tasks,
    user,
    wrong_questions,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(knowledge_points.router, prefix="/knowledge-points", tags=["knowledge-points"])
# 知识库资料（上传 / 列表 / 检索）
api_router.include_router(knowledge_docs.router, prefix="/knowledge-docs", tags=["knowledge-docs"])
# 科目（各模块共享的科目名称）
api_router.include_router(subjects.router, prefix="/subjects", tags=["subjects"])
api_router.include_router(questions.router, prefix="/questions", tags=["questions"])
api_router.include_router(wrong_questions.router, prefix="/wrong-questions", tags=["wrong-questions"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(study_plans.router, prefix="/study-plans", tags=["study-plans"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
# 主控 Agent 任务接口（新增，不影响旧 /api/agent/chat）
api_router.include_router(agent_tasks.router, prefix="/agent/tasks", tags=["agent-tasks"])

__all__ = ["api_router"]