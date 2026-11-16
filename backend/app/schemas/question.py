"""题目 / 答题 / 练习相关 Schema."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgePointOut(BaseModel):
    id: int
    subject: str
    name: str
    description: Optional[str] = None
    difficulty: str

    model_config = ConfigDict(from_attributes=True)


class QuestionOut(BaseModel):
    """对外输出的题目（不含答案，避免泄题）."""

    id: int
    knowledge_point_id: int
    knowledge_point_name: Optional[str] = None
    subject: Optional[str] = None
    content: str
    question_type: str
    options: Optional[List[str]] = None
    difficulty: str
    source: str = "bank"

    model_config = ConfigDict(from_attributes=True)


class QuestionDetail(QuestionOut):
    """含答案与解析（批改后返回）."""

    answer: str
    explanation: Optional[str] = None


class GenerateQuestionsRequest(BaseModel):
    knowledge_point_id: Optional[int] = None
    subject: Optional[str] = None
    knowledge_point: Optional[str] = None       # 兼容按名称指定知识点
    count: int = Field(default=5, ge=1, le=20)
    difficulty: Optional[str] = None            # 不传则根据掌握度动态决定
    question_types: Optional[List[str]] = None  # 不传则四种题型混合
    use_weak_points: Optional[bool] = None      # 不传则默认结合薄弱知识点


class AnswerRequest(BaseModel):
    user_answer: str = Field(..., min_length=1, max_length=2000)


class AnswerResult(BaseModel):
    """批改结果."""

    is_correct: bool
    score: float
    correct_answer: str
    explanation: Optional[str] = None
    # 是否因此题产生了新的错题记录
    wrong_question_id: Optional[int] = None


class TaskOut(BaseModel):
    id: int
    plan_id: int
    knowledge_point_id: Optional[int] = None
    knowledge_point_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    estimated_minutes: int
    completed: bool
    scheduled_date: datetime

    model_config = ConfigDict(from_attributes=True)