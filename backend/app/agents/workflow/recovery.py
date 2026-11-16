"""写入确认（Recovery）.

用途：写入型 Agent 超时/数据库异常时，**先查询确认上一次是否已经写入**，
再决定是"按成功继续"还是"标记失败等人工确认"，避免盲目重跑导致重复插入。

约束：
- 只读数据库，不修改任何业务数据；
- 只按"本次任务时间窗口 + 当前用户"确认，绝不跨用户读取；
- 无法确认（例如原地调整计划）时一律返回未确认，交人工处理。
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.agents.master.task_planner import TaskPlanner
from app.models import KnowledgePoint, Question


@dataclass
class ConfirmResult:
    """写入确认结果."""

    confirmed: bool
    payload: Optional[dict] = None
    note: str = ""
    details: dict = field(default_factory=dict)


class SideEffectConfirmer:
    """确认写入型步骤是否已经产生副作用（只读）."""

    def __init__(self, dispatcher) -> None:
        self.dispatcher = dispatcher

    def confirm(
        self,
        *,
        agent: str,
        input_data: dict,
        context,
        since: Optional[datetime],
    ) -> ConfirmResult:
        if context.db is None:
            return ConfirmResult(False, note="缺少数据库会话，无法确认写入结果")
        if since is None:
            return ConfirmResult(False, note="缺少步骤开始时间，无法确认写入结果")

        if agent == TaskPlanner.AGENT_QUESTIONS:
            return self._confirm_questions(input_data, context, since)
        if agent == TaskPlanner.AGENT_PLAN:
            return self._confirm_plan(input_data, context, since)
        return ConfirmResult(False, note=f"{agent} 不支持写入确认")

    # ==================== 题目 ====================

    def _confirm_questions(
        self, input_data: dict, context, since: datetime
    ) -> ConfirmResult:
        db: Session = context.db
        kp = self._resolve_kp(db, input_data)
        if kp is None:
            return ConfirmResult(False, note="无法确定知识点，无法确认题目是否已写入")

        window_start = since - timedelta(seconds=5)   # 容忍时钟粒度误差
        rows = (
            db.query(Question)
            .filter(
                Question.knowledge_point_id == kp.id,
                Question.created_at >= window_start,
            )
            .order_by(Question.id.asc())
            .all()
        )
        if not rows:
            return ConfirmResult(
                False, note="未在本任务时间窗口内发现新增题目，可安全重跑",
                details={"knowledge_point": kp.name},
            )

        requested = self._as_int(input_data.get("count")) or 0
        payload = {
            "agent": TaskPlanner.AGENT_QUESTIONS,
            "status": "success" if len(rows) >= requested else "partial",
            "count_met": len(rows) >= requested if requested else True,
            "requested_count": requested or len(rows),
            "actual_count": len(rows),
            "question_ids": [row.id for row in rows],
            "questions": [],
            "knowledge_point": {"id": kp.id, "name": kp.name, "subject": kp.subject},
            "recovered": True,
            "message": f"已确认上一次执行已写入 {len(rows)} 道题目",
        }
        return ConfirmResult(
            True, payload=payload,
            note=f"已确认写入 {len(rows)} 道题目，不再重复执行",
            details={"question_ids": [row.id for row in rows]},
        )

    # ==================== 计划 ====================

    def _confirm_plan(
        self, input_data: dict, context, since: datetime
    ) -> ConfirmResult:
        if input_data.get("adjust_plan_id"):
            # 原地调整无法通过"新增记录"确认，按安全优先原则交人工检查
            return ConfirmResult(
                False,
                note="计划的原地调整结果未知，需人工确认后再继续",
                details={"adjust_plan_id": input_data.get("adjust_plan_id")},
            )

        from app.models import StudyPlan

        db: Session = context.db
        window_start = since - timedelta(seconds=5)
        plan = (
            db.query(StudyPlan)
            .filter(
                StudyPlan.user_id == context.user_id,
                StudyPlan.created_at >= window_start,
            )
            .order_by(StudyPlan.id.desc())
            .first()
        )
        if plan is None:
            return ConfirmResult(False, note="未发现本任务新增的计划，可安全重跑")

        payload = self.dispatcher.plan_payload(db, plan.id, context.user_id)
        if payload is None:
            return ConfirmResult(False, note="计划存在但读取失败，需人工确认")
        return ConfirmResult(
            True, payload=payload,
            note=f"已确认计划已写入 plan_id={plan.id}，不再重复创建",
            details={"plan_id": plan.id},
        )

    # ==================== 辅助 ====================

    @staticmethod
    def _resolve_kp(db: Session, input_data: dict) -> Optional[KnowledgePoint]:
        name = input_data.get("knowledge_point")
        if name:
            row = db.query(KnowledgePoint).filter(
                KnowledgePoint.name == str(name)
            ).first()
            if row:
                return row
        kp_id = input_data.get("knowledge_point_id")
        if kp_id:
            try:
                return db.get(KnowledgePoint, int(kp_id))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _as_int(value) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
