"""Dashboard 相关 Schema（重构版：今日任务 + 状态概览 + 趋势 + Agent 建议）."""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class ExamCountdown(BaseModel):
    """考试倒计时."""

    plan_id: int
    subject: str
    title: str
    exam_date: date
    days_left: int


class TodayTask(BaseModel):
    """今日学习任务."""

    id: int
    title: str
    knowledge_point_id: Optional[int] = None
    knowledge_point_name: Optional[str] = None
    estimated_minutes: int
    completed: bool


class DashboardStats(BaseModel):
    """学习数据概览."""

    today_minutes: int
    today_task_total: int
    today_task_completed: int
    today_completion_rate: float  # 0~1
    recent_accuracy: Optional[float]  # 0~1，最近20题
    weak_points: List[str]


class TrendPoint(BaseModel):
    date: date
    # 当日无数据时为 null（前端已兼容）
    value: Optional[float] = None


class AgentSuggestion(BaseModel):
    """Agent 学习建议：基于真实学习数据（画像/记录/错题）生成."""

    text: str
    weak_knowledge_point_id: Optional[int] = None
    weak_knowledge_point_name: Optional[str] = None


class DashboardSummary(BaseModel):
    """学习看板汇总."""

    greeting: str
    username: str
    study_day_count: int  # 学习第 N 天
    exam: Optional[ExamCountdown] = None
    today_tasks: List[TodayTask]
    stats: DashboardStats
    study_time_trend: List[TrendPoint]
    accuracy_trend: List[TrendPoint]
    agent_suggestion: AgentSuggestion