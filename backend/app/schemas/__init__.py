"""Pydantic Schemas."""
from app.schemas.auth import LoginRequest, RegisterRequest, Token
from app.schemas.user import UserOut, UserUpdate
from app.schemas.question import (
    AnswerRequest,
    AnswerResult,
    GenerateQuestionsRequest,
    KnowledgePointOut,
    QuestionDetail,
    QuestionOut,
    TaskOut,
)
from app.schemas.wrong_question import (
    MasterResult,
    WrongQuestionDetail,
    WrongQuestionListResponse,
    WrongQuestionOut,
    WrongQuestionStats,
)
from app.schemas.dashboard import DashboardSummary

__all__ = [
    "LoginRequest",
    "RegisterRequest",
    "Token",
    "UserOut",
    "UserUpdate",
    "AnswerRequest",
    "AnswerResult",
    "GenerateQuestionsRequest",
    "KnowledgePointOut",
    "QuestionDetail",
    "QuestionOut",
    "TaskOut",
    "MasterResult",
    "WrongQuestionDetail",
    "WrongQuestionListResponse",
    "WrongQuestionOut",
    "WrongQuestionStats",
    "DashboardSummary",
]