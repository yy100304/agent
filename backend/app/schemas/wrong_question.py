"""错题相关 Schema."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class WrongQuestionOut(BaseModel):
    """错题卡片.

    status 由后端推导：mastered -> 已掌握；
    review_count>0 且未掌握 -> 复习中；否则 未掌握。
    """

    id: int
    question_id: int
    subject: str
    knowledge_point_id: int
    knowledge_point_name: str
    content: str
    question_type: str
    difficulty: str
    my_answer: str
    correct_answer: str
    reason: Optional[str] = None
    suggestion: Optional[str] = None
    mastered: bool
    review_count: int
    status: str  # unmastered / reviewing / mastered
    created_at: datetime


class WrongQuestionStats(BaseModel):
    total: int
    unmastered: int
    reviewing: int
    mastered: int


class WrongQuestionListResponse(BaseModel):
    stats: WrongQuestionStats
    items: List[WrongQuestionOut]


class WrongQuestionDetail(WrongQuestionOut):
    """错题详情：含解析与推荐学习内容."""

    explanation: Optional[str] = None
    options: Optional[List[str]] = None


class MasterResult(BaseModel):
    """标记已掌握的结果."""

    success: bool
    new_mastery: float  # 更新后的掌握度（0~1）
    message: str