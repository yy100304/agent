"""学习计划 Agent（Study Planning Agent）.

职责：综合学情分析、知识检索、考试日期与每日可用学习时长，生成可执行的多日
学习计划，并原子写入现有 StudyPlan / StudyTask 模型。

关键约束（对应需求）：
- 复用第三阶段 LearningAnalysisAgent 的学情结果（薄弱点）；
- 复用第四阶段 KnowledgeRetrievalAgent 的知识内容（用于任务描述）；
- 每日学习总时长由 **Python 代码**计算校验：按天汇总该用户当天所有 StudyTask
  （含既有任务），新增任务总量不得超过 daily_minutes - 当天已有分钟数；
- StudyPlan 与 StudyTask 在**同一事务**写入，任何失败均 rollback，不产生半截数据；
- 不修改、不删除任何既有计划/任务；写入型 Agent 不做自动重试（max_retries=0）。
"""
import json
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.core.base import AgentContext, BaseAgent
from app.agents.core.schemas import AgentTask
from app.agents.knowledge_retrieval_agent import KnowledgeRetrievalAgent
from app.agents.learning_analysis_agent import LearningAnalysisAgent
from app.models import KnowledgePoint, StudyPlan, StudyTask


class StudyPlanningAgent(BaseAgent):
    """学习计划专业 Agent."""

    name = "study_planning"
    description = "结合学情、知识检索、考试日期与每日时长，生成并保存学习计划"
    task_type = "study_planning"
    max_retries = 0        # 写入型 Agent：不自动重试，避免重复写计划
    timeout_s = 120.0

    # ---- 计划生成参数（可按需调整）----
    MIN_TASK_MINUTES = 15       # 单个任务最小粒度
    MAX_DAILY_MINUTES = 1440    # 每日时长合法上限
    MAX_FOCUS_POINTS = 8        # 最多关注的知点数量

    # 任务块模板：25 / 20 / 15 三档，单日三块合计 60
    TASK_BLOCKS = (
        {"minutes": 25, "title": "复习「{kp}」核心概念", "prefix": "概念梳理与重点回顾"},
        {"minutes": 20, "title": "完成「{kp}」专项练习", "prefix": "针对性专项练习"},
        {"minutes": 15, "title": "复习「{kp}」错题", "prefix": "错题复盘与巩固"},
    )

    # ==================== 统一执行入口 ====================

    async def execute(self, task: AgentTask, context: AgentContext) -> dict:
        if context.db is None:
            raise ValueError("学习计划生成需要数据库会话（context.db 为空）")
        if task.user_id != context.user_id:
            raise ValueError("任务用户与当前登录用户不一致，已拒绝执行")

        db: Session = context.db
        data = task.input_data or {}
        today = date.today()

        # ---- 0. 修正模式（Self-Loop）：原地调整本次工作流创建的计划 ----
        if data.get("adjust_plan_id") is not None:
            return self._adjust_plan(task, context, data)

        # ---- 1. 必要参数校验 ----
        exam_date = self._parse_exam_date(data.get("exam_date"))
        daily_minutes = self._parse_daily_minutes(data.get("daily_minutes"))

        missing: list[str] = []
        if exam_date is None:
            missing.append("exam_date")
        if daily_minutes is None:
            missing.append("daily_minutes")
        if missing:
            self.logger.log(
                task.task_id, self.name,
                f"缺少必要参数：{missing}", level="warning",
            )
            return {
                "agent": self.name,
                "created": False,
                "missing_params": missing,
                "message": (
                    "缺少必要参数："
                    + "、".join(
                        {"exam_date": "考试日期(exam_date)",
                         "daily_minutes": "每日可用学习时长(daily_minutes)"}[m]
                        for m in missing
                    )
                    + "，请补充后再生成计划。"
                ),
            }

        if exam_date <= today:
            return {
                "agent": self.name,
                "created": False,
                "missing_params": [],
                "message": "考试日期必须晚于今天，请检查后重试。",
            }

        days = (exam_date - today).days
        if daily_minutes < self.MIN_TASK_MINUTES:
            return {
                "agent": self.name,
                "created": False,
                "missing_params": [],
                "message": f"每日可用学习时长过短（至少需要 {self.MIN_TASK_MINUTES} 分钟）。",
            }

        # ---- 2. 复用学情分析 Agent（薄弱点 / 数据是否充分）----
        analysis, data_sufficient, weak_points = await self._collect_analysis(
            task, context
        )

        # ---- 3. 复用知识检索 Agent（补充内容）----
        retrieval = await self._collect_retrieval(
            task, context, data.get("goal"), weak_points,
            data.get("subject"),
        )
        retrieval_used = bool(retrieval.get("found"))
        retrieval_points = retrieval.get("knowledge_points", []) or []

        # ---- 4. 解析学科 / 学习重点 / 知识点映射 ----
        subject = self._resolve_subject(db, data.get("subject"), weak_points)
        focus = self._build_focus(db, subject, weak_points, retrieval_points)
        kp_map = {k.name: k.id for k in db.query(KnowledgePoint).all()}
        content_map = self._build_content_map(focus, retrieval)

        # ---- 5. 计算当天既有任务占用（用于每日预算）----
        dates = [today + timedelta(days=i) for i in range(days)]
        existing = self._existing_minutes_by_date(db, task.user_id, dates)

        # ---- 6. 纯 Python 生成任务并校验每日预算 ----
        tasks = self._build_tasks(
            today, days, daily_minutes, focus, kp_map, content_map, existing
        )
        if not tasks:
            return {
                "agent": self.name,
                "created": False,
                "missing_params": [],
                "message": "每日可用时长不足或当日已有任务占满，未能生成任何任务。",
            }
        self._validate_budget(tasks, daily_minutes, existing)  # 硬校验，超限即失败

        # ---- 7. 同一事务写入 StudyPlan + StudyTask ----
        title = str(data.get("title") or f"{subject}·{days}天学习计划")
        plan = StudyPlan(
            user_id=task.user_id,
            title=title,
            subject=subject,
            exam_date=exam_date,
            daily_minutes=daily_minutes,
            status="active",
            adjustment_log=json.dumps({
                "source": self.name,
                "data_sufficient": data_sufficient,
                "weak_points": weak_points,
                "focus_points": focus,
                "daily_minutes": daily_minutes,
                "days": days,
                "retrieval_used": retrieval_used,
            }, ensure_ascii=False),
        )
        try:
            self._persist(db, plan, tasks)
        except Exception:
            db.rollback()          # 任意失败都回滚，杜绝半截数据
            raise
        self.logger.log(
            task.task_id, self.name,
            f"计划已保存 plan_id={plan.id}，共 {len(tasks)} 个任务",
        )

        # ---- 8. 组装结果 ----
        daily_summary = {}
        for i in range(days):
            d = today + timedelta(days=i)
            new_sum = sum(
                t["estimated_minutes"] for t in tasks if t["scheduled_date"] == d
            )
            ex = existing.get(d, 0)
            daily_summary[d.isoformat()] = {
                "new": new_sum,
                "existing": ex,
                "total": ex + new_sum,
                "limit": daily_minutes,
            }

        message = (
            f"学习数据不足，已生成基础计划（未做个性化薄弱点调整）。"
            if not data_sufficient
            else f"已生成 {days} 天学习计划，共 {len(tasks)} 个任务。"
        )

        return {
            "agent": self.name,
            "created": True,
            "plan_id": plan.id,
            "title": title,
            "subject": subject,
            "exam_date": exam_date.isoformat(),
            "daily_minutes": daily_minutes,
            "days": days,
            "task_count": len(tasks),
            "daily_summary": daily_summary,
            "data_warning": not data_sufficient,
            "weak_points": weak_points,
            "focus_points": focus,
            "retrieval_used": retrieval_used,
            "retrieval_points": retrieval_points,
            "message": message,
        }

    # ==================== 修正模式：原地调整已有计划 ====================

    def _adjust_plan(self, task: AgentTask, context: AgentContext, data: dict) -> dict:
        """Self-Loop 修正：**只**调整本次工作流创建的计划，绝不新建计划.

        允许的操作（与需求确认的范围一致）：
        - 压缩超预算日期的任务时长（单个任务不低于 MIN_TASK_MINUTES）；
        - 补齐空任务标题；
        - 重新计算并返回每日汇总。

        禁止：修改考试日期 / 每日预算 / 计划标题，删除整份计划，改动其它计划。
        幂等：重复调用不会改变已符合预算的数据（只做必要的压缩与补齐）。
        """
        db: Session = context.db
        try:
            plan_id = int(data.get("adjust_plan_id"))
        except (TypeError, ValueError):
            return self._adjust_fail("计划 ID 非法", None, task)

        plan = (
            db.query(StudyPlan)
            .filter(StudyPlan.id == plan_id, StudyPlan.user_id == task.user_id)
            .first()
        )
        if plan is None:
            return self._adjust_fail(
                "计划不存在或不属于当前用户，拒绝修改", plan_id, task
            )

        budget = int(plan.daily_minutes or 0)
        if budget < self.MIN_TASK_MINUTES:
            return self._adjust_fail("计划每日预算非法，无法调整", plan_id, task)

        reason = str(data.get("adjust_reason") or "self_loop")
        fix_titles = bool(data.get("adjust_fix_titles", True))
        tasks = (
            db.query(StudyTask)
            .filter(StudyTask.plan_id == plan.id)
            .order_by(StudyTask.scheduled_date.asc(), StudyTask.id.asc())
            .all()
        )
        if not tasks:
            return self._adjust_fail("该计划没有任何任务，无法调整", plan_id, task)

        adjustments: list[dict] = []
        try:
            # ---- 1) 补齐空标题（不改变时长，避免触发格式校验失败）----
            if fix_titles:
                for row in tasks:
                    if not str(row.title or "").strip():
                        row.title = f"复习「{plan.subject or '本学科'}」"
                        adjustments.append({
                            "type": "title", "task_id": row.id, "after": row.title,
                        })

            # ---- 2) 按天压缩超预算时长（不删除任何任务）----
            by_day: dict[date, list[StudyTask]] = {}
            for row in tasks:
                by_day.setdefault(self._as_date(row.scheduled_date), []).append(row)

            for day, group in sorted(by_day.items()):
                total = sum(int(row.estimated_minutes or 0) for row in group)
                over = total - budget
                if over <= 0:
                    continue
                trimmed = self._trim_group(group, over)
                if trimmed is None:
                    db.rollback()
                    return self._adjust_fail(
                        f"{day.isoformat()} 超出预算 {over} 分钟，"
                        f"且无法在不低于 {self.MIN_TASK_MINUTES} 分钟/任务的前提下压缩，"
                        "为避免删除用户任务已停止调整",
                        plan_id, task,
                    )
                adjustments.append({
                    "type": "trim", "date": day.isoformat(),
                    "before": total, "after": total - trimmed, "trimmed": trimmed,
                })

            # ---- 3) 追加调整记录（保留历史，不覆盖原始内容）----
            self._append_adjust_log(plan, {
                "source": "self_loop", "reason": reason, "adjustments": adjustments,
            })
            db.commit()
        except Exception:
            db.rollback()
            raise

        payload = self._plan_payload(db, plan)
        payload.update({
            "adjusted": True,
            "adjustments": adjustments,
            "created": True,
            "message": (
                f"已调整学习计划（{len(adjustments)} 处改动），"
                f"考试日期 {payload.get('exam_date')}、每日预算 {budget} 分钟保持不变。"
                if adjustments
                else "计划已符合约束，无需调整。"
            ),
        })
        self.logger.log(
            task.task_id, self.name,
            f"修正完成 plan_id={plan.id}：{len(adjustments)} 处调整",
        )
        return payload

    def _trim_group(self, group: list[StudyTask], over: int) -> Optional[int]:
        """从最长任务开始压缩，保证每个任务不低于 MIN_TASK_MINUTES."""
        capacity = sum(
            max(0, int(row.estimated_minutes or 0) - self.MIN_TASK_MINUTES)
            for row in group
        )
        if over > capacity:
            return None

        remaining = over
        for row in sorted(group, key=lambda item: -int(item.estimated_minutes or 0)):
            if remaining <= 0:
                break
            current = int(row.estimated_minutes or 0)
            cut = min(remaining, max(0, current - self.MIN_TASK_MINUTES))
            if cut > 0:
                row.estimated_minutes = current - cut
                remaining -= cut
        return over - remaining

    @staticmethod
    def _append_adjust_log(plan: StudyPlan, entry: dict) -> None:
        """把调整记录追加到 adjustment_log（保留原有内容与历史）."""
        try:
            log = json.loads(plan.adjustment_log) if plan.adjustment_log else {}
            if not isinstance(log, dict):
                log = {"original": log}
        except (TypeError, ValueError):
            log = {}
        history = log.get("self_loop")
        if not isinstance(history, list):
            history = []
        history.append(entry)
        log["self_loop"] = history[-20:]      # 只保留最近 20 次，避免无限增长
        plan.adjustment_log = json.dumps(log, ensure_ascii=False)

    def _plan_payload(self, db: Session, plan: StudyPlan) -> dict:
        """按 ResultValidationAgent 的 study_plan 结构重建计划结果（读真实库）."""
        tasks = db.query(StudyTask).filter(StudyTask.plan_id == plan.id).all()
        per_day: dict[str, int] = {}
        for row in tasks:
            key = self._as_date(row.scheduled_date).isoformat()
            per_day[key] = per_day.get(key, 0) + int(row.estimated_minutes or 0)

        created = self._as_date(plan.created_at) if plan.created_at else date.today()
        exam = self._as_date(plan.exam_date) if plan.exam_date else None
        days = max(1, (exam - created).days) if exam else max(1, len(per_day))
        budget = int(plan.daily_minutes or 0)

        return {
            "agent": self.name,
            "plan_id": plan.id,
            "title": plan.title,
            "subject": plan.subject,
            "exam_date": exam.isoformat() if exam else None,
            "daily_minutes": budget,
            "days": days,
            "task_count": len(tasks),
            "daily_summary": {
                day: {"new": total, "existing": 0, "total": total, "limit": budget}
                for day, total in per_day.items()
            },
        }

    def _adjust_fail(self, message: str, plan_id: Optional[int], task: AgentTask) -> dict:
        self.logger.log(task.task_id, self.name, message, level="warning")
        return {
            "agent": self.name,
            "created": False,
            "adjusted": False,
            "plan_id": plan_id,
            "message": message,
            "adjustments": [],
        }

    # ==================== 复用前序 Agent ====================

    async def _collect_analysis(
        self, task: AgentTask, context: AgentContext
    ) -> tuple[dict, bool, list[str]]:
        """调用学情分析 Agent；失败则降级为空结果（不编造学情）.

        主控 Agent 已在同一任务中产出真实学情时，直接复用该结果
        （input_data.analysis_result），避免重复调用与重复读取数据库。
        """
        preset = (task.input_data or {}).get("analysis_result")
        if isinstance(preset, dict) and "sufficient" in preset:
            report = preset.get("report") or {}
            return preset, bool(preset.get("sufficient")), list(report.get("weak_points") or [])
        try:
            sub = AgentTask(
                task_id=f"{task.task_id}-analysis",
                user_id=task.user_id,
                task_type="learning_analysis",
                input_data={},
            )
            res = await LearningAnalysisAgent(use_llm=False).run(sub, context)
            if res.success and isinstance(res.result, dict):
                report = res.result.get("report") or {}
                return (
                    res.result,
                    bool(res.result.get("sufficient")),
                    list(report.get("weak_points") or []),
                )
        except Exception:
            pass
        return {}, False, []

    async def _collect_retrieval(
        self, task: AgentTask, context: AgentContext,
        goal: Optional[str], weak_points: list[str],
        subject: Optional[str],
    ) -> dict:
        """调用知识检索 Agent；失败则降级为空（任务描述退化为通用说明）.

        主控 Agent 已提供真实检索结果时直接复用（input_data.retrieval_result）。
        """
        preset = (task.input_data or {}).get("retrieval_result")
        if isinstance(preset, dict) and "found" in preset:
            return preset
        query = (goal or "").strip() or " ".join(weak_points) or (subject or "")
        if not query:
            return {}
        try:
            sub = AgentTask(
                task_id=f"{task.task_id}-retrieval",
                user_id=task.user_id,
                task_type="knowledge_retrieval",
                input_data={"query": query, "top_k": 5},
            )
            res = await KnowledgeRetrievalAgent().run(sub, context)
            if res.success and isinstance(res.result, dict):
                return res.result
        except Exception:
            pass
        return {}

    # ==================== 学科 / 重点 / 内容 ====================

    @staticmethod
    def _resolve_subject(
        db: Session, input_subject: Optional[str], weak_points: list[str]
    ) -> str:
        if input_subject and str(input_subject).strip():
            return str(input_subject).strip()
        if weak_points:
            row = (
                db.query(KnowledgePoint)
                .filter(KnowledgePoint.name.in_(weak_points))
                .first()
            )
            if row:
                return row.subject
        row = db.query(KnowledgePoint).first()
        return row.subject if row else "综合复习"

    def _build_focus(
        self, db: Session, subject: str,
        weak_points: list[str], retrieval_points: list[str],
    ) -> list[str]:
        """确定学习重点：薄弱点优先 → 检索命中 → 该学科全部知识点 → 兜底."""
        names: list[str] = list(weak_points or [])

        subject_kps = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.subject == subject)
            .all()
        )
        kp_names = [k.name for k in subject_kps]

        # 检索标题里出现的知识点名（如 "图论·割点与割边" 命中 "图论"）
        for title in retrieval_points:
            for name in kp_names:
                if name in str(title) and name not in names:
                    names.append(name)

        # 该学科其余知识点补齐
        for name in kp_names:
            if name not in names:
                names.append(name)

        names = self._dedup(names)[: self.MAX_FOCUS_POINTS]
        if not names:
            names = [subject] if subject else ["基础知识点"]
        return names

    @staticmethod
    def _build_content_map(focus: list[str], retrieval: dict) -> dict:
        """把检索结果映射到知识点名，供任务描述使用（真实内容）."""
        content_map: dict[str, str] = {}
        for item in retrieval.get("results", []) or []:
            parts = (item.get("key_points") or []) + (item.get("difficulties") or [])
            if not parts:
                continue
            text = "；".join(parts[:3])
            title = str(item.get("title", ""))
            context_text = str(item.get("context", ""))
            for kp in focus:
                if kp in title or kp in context_text:
                    content_map.setdefault(kp, text)
        return content_map

    @staticmethod
    def _detail_for(kp_name: str, content_map: dict) -> str:
        detail = (content_map.get(kp_name) or "").strip()
        return detail[:120]

    # ==================== 每日预算（纯 Python） ====================

    @staticmethod
    def _as_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    def _existing_minutes_by_date(
        self, db: Session, user_id: int, dates: list[date]
    ) -> dict[date, int]:
        """按天统计该用户当天所有 StudyTask（含其他计划）的既有分钟数."""
        if not dates:
            return {}
        rows = (
            db.query(
                StudyTask.scheduled_date,
                func.sum(StudyTask.estimated_minutes),
            )
            .join(StudyPlan, StudyTask.plan_id == StudyPlan.id)
            .filter(
                StudyPlan.user_id == user_id,
                StudyTask.scheduled_date.in_(dates),
            )
            .group_by(StudyTask.scheduled_date)
            .all()
        )
        return {self._as_date(d): int(m or 0) for d, m in rows}

    def _build_tasks(
        self, today: date, days: int, daily_minutes: int,
        focus: list[str], kp_map: dict, content_map: dict,
        existing: dict[date, int],
    ) -> list[dict]:
        """按天分配任务，size=min(块时长, 当日剩余)，从结构上保证不超上限."""
        tasks: list[dict] = []
        cursor = 0
        for i in range(days):
            d = today + timedelta(days=i)
            available = max(0, daily_minutes - existing.get(d, 0))
            remaining = available
            block_index = 0
            while remaining >= self.MIN_TASK_MINUTES:
                block = self.TASK_BLOCKS[block_index % len(self.TASK_BLOCKS)]
                block_index += 1
                kp_name = focus[cursor % len(focus)]
                cursor += 1
                size = min(block["minutes"], remaining)
                if size < self.MIN_TASK_MINUTES:
                    break
                detail = self._detail_for(kp_name, content_map)
                description = (
                    f"{block['prefix']}：{detail}"
                    if detail
                    else f"{block['prefix']}（重点巩固该知识点）"
                )
                tasks.append({
                    "title": block["title"].format(kp=kp_name),
                    "description": description,
                    "estimated_minutes": size,
                    "scheduled_date": d,
                    "knowledge_point_id": kp_map.get(kp_name),
                })
                remaining -= size
        return tasks

    def _validate_budget(
        self, tasks: list[dict], daily_minutes: int, existing: dict[date, int]
    ) -> None:
        """二次硬校验：按天汇总当天全部任务（既有 + 新增），超限直接失败."""
        per_day: dict[date, int] = {}
        for t in tasks:
            d = t["scheduled_date"]
            per_day[d] = per_day.get(d, 0) + int(t["estimated_minutes"])

        for d, new_total in per_day.items():
            ex = existing.get(d, 0)
            available = max(0, daily_minutes - ex)
            if new_total > available:
                raise ValueError(
                    f"{d.isoformat()} 新增任务 {new_total} 分钟，"
                    f"超过当日可用上限 {available} 分钟（上限 {daily_minutes}）"
                )
            if ex + new_total > daily_minutes:
                raise ValueError(
                    f"{d.isoformat()} 当天总时长 {ex + new_total} 分钟，"
                    f"超过每日上限 {daily_minutes} 分钟"
                )

    # ==================== 持久化（单一事务） ====================

    @staticmethod
    def _persist(db: Session, plan: StudyPlan, tasks: list[dict]) -> None:
        """StudyPlan 与 StudyTask 在同一事务写入，由调用方负责 rollback."""
        db.add(plan)
        db.flush()                       # 取得 plan.id（尚未提交）
        for t in tasks:
            db.add(StudyTask(
                plan_id=plan.id,
                knowledge_point_id=t.get("knowledge_point_id"),
                title=t["title"],
                description=t["description"],
                estimated_minutes=t["estimated_minutes"],
                completed=False,
                scheduled_date=t["scheduled_date"],
            ))
        db.commit()                      # 唯一一次提交（最后一步）

    # ==================== 参数解析 ====================

    @staticmethod
    def _parse_exam_date(raw: Any) -> Optional[date]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return None
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        try:
            return date.fromisoformat(str(raw).strip()[:10])
        except ValueError:
            return None

    def _parse_daily_minutes(self, raw: Any) -> Optional[int]:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        if value <= 0 or value > self.MAX_DAILY_MINUTES:
            return None
        return value

    @staticmethod
    def _dedup(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = str(item).strip()
            if key and key not in seen:
                seen.add(key)
                result.append(key)
        return result
