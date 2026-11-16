"""第九阶段测试：Self-Loop 自我修正机制.

覆盖：
1. 题目数量不足 → 只补缺口（不重新生成全部）+ 排除已有题目 + 合并后重新校验
2. 连续不足 → 达到最大修正轮次（2 轮）后停止，如实报告最终数量
3. 学习计划每日预算超限 → 只压缩超预算日期的任务，不新建计划、不改考试日期/预算
4. 不可修复：学情数据不足（不重跑、不编造）
5. 不可修复：知识检索为空（只换一次关键词，仍空则如实报告）
6. 数据库错误：不盲目重跑，标记需人工确认
7. 超时分类与策略（只读可重跑 / 写入先确认）
8. 幂等：不重复插入题目、不重复创建计划
9. 修正记录落库（agent_evaluations）与每轮真实数据
10. 内存日志清理 + 其他任务日志不受影响 + 用户隔离

测试不消耗 DeepSeek 额度：llm_service.chat 被临时替换为返回 None（全部走题库降级）。
用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_self_loop.py
"""
import asyncio
import sys
import uuid
from datetime import date
from unittest.mock import patch

import app.main  # noqa: F401
from app.agents.core import AgentContext, AgentTask
from app.agents.core.registry import CoreAgentRegistry, core_registry
from app.agents.master.master_agent import MasterAgent
from app.agents.master.schemas import MasterIntent, StepOutcome
from app.agents.question_generation_agent import QuestionGenerationAgent
from app.agents.registration import register_core_agents
from app.agents.study_planning_agent import StudyPlanningAgent
from app.agents.workflow.config import MAX_REPAIR_ROUNDS
from app.agents.workflow.failure import (
    AGENT_TIMEOUT,
    DATABASE_ERROR,
    FailureClassifier,
)
from app.agents.workflow.self_loop import SelfLoopPolicy
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import (
    AgentEvaluation,
    AgentTaskRecord,
    Answer,
    KnowledgePoint,
    LearningProfile,
    LearningRecord,
    Question,
    StudyPlan,
    StudyTask,
    User,
    WrongQuestion,
)
from app.services.llm_service import llm_service

KP_NAME = "关系与闭包"
Q_PREFIX = "【测试】SL"


# ==================== 测试替身（模拟真实异常场景）====================

class ScriptedQuestionAgent(QuestionGenerationAgent):
    """按脚本"只能生成 N 道"，用于模拟 LLM/题库数量不足."""

    def __init__(self, limits: list[int]) -> None:
        super().__init__()
        self.limits = list(limits)
        self.calls: list[dict] = []

    async def execute(self, task: AgentTask, context: AgentContext) -> dict:
        data = dict(task.input_data or {})
        self.calls.append(data)
        requested = int(data.get("count") or 0)
        index = min(len(self.calls) - 1, len(self.limits) - 1)
        limit = min(self.limits[index], requested) if requested else self.limits[index]

        original = task.input_data
        task.input_data = {**data, "count": max(1, limit)}
        try:
            result = await super().execute(task, context)
        finally:
            task.input_data = original

        if requested > limit:
            result["requested_count"] = requested
            result["count_met"] = False
            result["status"] = "partial" if result.get("actual_count") else "failed"
            result["reason"] = f"仅生成 {result.get('actual_count')}/{requested} 道"
        return result


class OverBudgetPlanAgent(StudyPlanningAgent):
    """首次生成后注入一个超预算任务，模拟"每日时长超限"异常数据."""

    async def execute(self, task: AgentTask, context: AgentContext) -> dict:
        data = task.input_data or {}
        if data.get("adjust_plan_id"):
            return await super().execute(task, context)

        result = await super().execute(task, context)
        if not result.get("created"):
            return result
        db = context.db
        db.add(StudyTask(
            plan_id=result["plan_id"],
            title=f"{Q_PREFIX}超预算任务",
            description="测试注入的超预算任务",
            estimated_minutes=30,
            completed=False,
            scheduled_date=date.today(),
        ))
        db.commit()
        payload = self._plan_payload(db, db.get(StudyPlan, result["plan_id"]))
        payload.update({"created": True, "message": "已生成计划（测试注入超预算任务）"})
        return payload


class BrokenPlanAgent(StudyPlanningAgent):
    """模拟数据库写入异常."""

    async def execute(self, task: AgentTask, context: AgentContext) -> dict:
        raise RuntimeError("OperationalError: database is locked")


# ==================== 数据准备 ====================

def get_or_create_user(db, username: str, email: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, email=email, password_hash=hash_password("test1234"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def ensure_kp(db, name: str, subject: str = "离散数学") -> tuple[KnowledgePoint, bool]:
    kp = db.query(KnowledgePoint).filter(
        KnowledgePoint.name == name, KnowledgePoint.subject == subject
    ).first()
    if kp:
        return kp, False
    kp = KnowledgePoint(subject=subject, name=name, description="测试用", difficulty="hard")
    db.add(kp)
    db.commit()
    db.refresh(kp)
    return kp, True


def clear_user(db, user: User) -> None:
    db.query(WrongQuestion).filter(WrongQuestion.user_id == user.id).delete(synchronize_session=False)
    db.query(Answer).filter(Answer.user_id == user.id).delete(synchronize_session=False)
    db.query(LearningRecord).filter(LearningRecord.user_id == user.id).delete(synchronize_session=False)
    db.query(LearningProfile).filter(LearningProfile.user_id == user.id).delete(synchronize_session=False)
    plan_ids = [p.id for p in db.query(StudyPlan).filter(StudyPlan.user_id == user.id).all()]
    if plan_ids:
        db.query(StudyTask).filter(StudyTask.plan_id.in_(plan_ids)).delete(synchronize_session=False)
        db.query(StudyPlan).filter(StudyPlan.id.in_(plan_ids)).delete(synchronize_session=False)
    db.commit()


def purge_master_records(db, users: list[User]) -> None:
    """删除测试用户的 Agent 任务相关记录（评估/日志/步骤/工作流/任务）."""
    from app.models import AgentExecutionLog, WorkflowRecord, WorkflowStepRecord

    rows = db.query(AgentTaskRecord).filter(
        AgentTaskRecord.user_id.in_([u.id for u in users])
    ).all()
    ids = [row.id for row in rows]
    if not ids:
        return
    workflow_ids = [
        w.id for w in db.query(WorkflowRecord).filter(
            WorkflowRecord.agent_task_id.in_(ids)
        ).all()
    ]
    if workflow_ids:
        db.query(WorkflowStepRecord).filter(
            WorkflowStepRecord.workflow_id.in_(workflow_ids)
        ).delete(synchronize_session=False)
        db.query(WorkflowRecord).filter(
            WorkflowRecord.id.in_(workflow_ids)
        ).delete(synchronize_session=False)
    db.query(AgentEvaluation).filter(
        AgentEvaluation.agent_task_id.in_(ids)
    ).delete(synchronize_session=False)
    db.query(AgentExecutionLog).filter(
        AgentExecutionLog.agent_task_id.in_(ids)
    ).delete(synchronize_session=False)
    db.query(AgentTaskRecord).filter(
        AgentTaskRecord.id.in_(ids)
    ).delete(synchronize_session=False)
    db.commit()


def seed_weak_point(db, user: User, kp: KnowledgePoint) -> None:
    """造一份"薄弱的真实学情"：答题记录 + 学习记录 + 掌握度画像."""
    question = Question(
        knowledge_point_id=kp.id,
        content=f"{Q_PREFIX}历史练习：关系闭包的性质判断",
        question_type="true_false",
        answer="正确",
        explanation="测试用历史练习题干，仅用于生成真实答题记录",
        difficulty="easy",
        source="bank",
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    db.add(Answer(
        user_id=user.id, question_id=question.id, user_answer="错误",
        is_correct=False, score=0.0,
    ))
    db.add(LearningProfile(
        user_id=user.id, knowledge_point_id=kp.id, mastery_score=0.35, confidence=5,
    ))
    db.add(LearningRecord(
        user_id=user.id, knowledge_point_id=kp.id, study_minutes=60,
        mastery_score=0.35, source="practice",
    ))
    db.commit()


def reset_user(db, user: User, kp: KnowledgePoint) -> None:
    """清空用户数据与测试知识点下的题目，再重新造一份薄弱的真实学情."""
    clear_user(db, user)
    db.query(Question).filter(Question.knowledge_point_id == kp.id).delete(
        synchronize_session=False
    )
    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(
        synchronize_session=False
    )
    db.commit()
    seed_weak_point(db, user, kp)


def build_master(overrides: dict) -> MasterAgent:
    register_core_agents()
    registry = CoreAgentRegistry()
    for agent in core_registry.list_all():
        registry.register(overrides.get(agent.name, agent))
    return MasterAgent(registry=registry, use_llm_intent=False)


async def run_master(master: MasterAgent, user: User, db, message: str) -> dict:
    task = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user.id, task_type="master",
        input_data={"message": message},
    )
    context = AgentContext(
        user_id=user.id, username=user.username, db=db, request={"message": message},
    )
    result = await master.run(task, context)
    assert result.success, result.error
    return result.result


# ==================== 测试主体 ====================

async def main() -> None:
    ok = 0
    fail = 0

    def check(name: str, cond: bool, extra: str = "") -> None:
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"[PASS] {name} {extra}")
        else:
            fail += 1
            print(f"[FAIL] {name} {extra}")

    init_db()
    register_core_agents()
    db = SessionLocal()

    user = get_or_create_user(db, "sl_test_a", "sl_a@test.com")
    empty_user = get_or_create_user(db, "sl_test_empty", "sl_empty@test.com")

    kp, kp_created = ensure_kp(db, KP_NAME)
    # 清理历史遗留：用户数据、测试知识点下的题目、上次运行残留的任务/评估/日志
    clear_user(db, empty_user)
    reset_user(db, user, kp)
    purge_master_records(db, [user, empty_user])

    task_ids: list[str] = []
    plan_ids: list[int] = []
    question_ids: list[int] = []

    def remember(result: dict) -> dict:
        task_ids.append(result["task_id"])
        artifacts = (result.get("final_result") or {}).get("artifacts") or {}
        plan = artifacts.get("study_planning") or {}
        if plan.get("plan_id"):
            plan_ids.append(int(plan["plan_id"]))
        questions = artifacts.get("question_generation") or {}
        question_ids.extend(int(i) for i in (questions.get("question_ids") or []))
        return result

    with patch.object(llm_service, "chat", return_value=None):
        # ---------- 1. 补题：10 道 → 首次 6 道 → 只补 4 道 ----------
        scripted = ScriptedQuestionAgent(limits=[6, 10])
        master = build_master({"question_generation": scripted})
        out = remember(await run_master(
            master, user, db, f"帮我生成10道{KP_NAME}的练习题。"
        ))
        questions = (out["final_result"]["artifacts"] or {}).get("question_generation") or {}
        loop = out["final_result"]["self_loop"]
        check("补题-整体成功", out["task_status"] == "success", f"({out['task_status']})")
        check("补题-最终数量达标", questions.get("actual_count") == 10,
              f"(actual={questions.get('actual_count')})")
        check("补题-只执行 1 轮修正", loop["repair_count"] == 1, f"({loop['repair_count']})")
        check("补题-第二轮只请求缺口 4 道",
              len(scripted.calls) == 2 and int(scripted.calls[1].get("count") or 0) == 4,
              f"({[c.get('count') for c in scripted.calls]})")
        second_call = scripted.calls[1] if len(scripted.calls) > 1 else {}
        check("补题-第二轮排除已保存题目",
              bool(second_call.get("exclude_question_ids"))
              and len(second_call.get("exclude_contents") or []) == 6,
              f"(ids={len(second_call.get('exclude_question_ids') or [])})")
        check("补题-未重新生成全部题目",
              len(scripted.calls) == 2 and out["final_result"]["self_loop"]["rounds"][0]["before"].get("actual_count") == 6,
              f"(before={(out['final_result']['self_loop']['rounds'][0]['before'])})")
        check("补题-修正后校验通过",
              out["final_result"]["self_loop"]["rounds"][0]["validation"]["passed"] is True,
              f"({out['final_result']['self_loop']['rounds'][0]['validation']})")

        db_questions = (
            db.query(Question)
            .filter(Question.knowledge_point_id == kp.id,
                    Question.id.in_(questions.get("question_ids") or [0]))
            .all()
        )
        contents = {q.content.strip() for q in db_questions}
        check("幂等-数据库题目数与报告一致且不重复",
              len(db_questions) == 10 and len(contents) == 10,
              f"(rows={len(db_questions)}, unique={len(contents)})")

        evaluations = (
            db.query(AgentEvaluation)
            .filter(AgentEvaluation.agent_task_id ==
                    db.query(AgentTaskRecord.id)
                    .filter(AgentTaskRecord.task_id == out["task_id"]).scalar())
            .order_by(AgentEvaluation.attempt.asc()).all()
        )
        check("记录-修正轮次已落库",
              len(evaluations) == 1 and evaluations[0].attempt == 1,
              f"({[(e.attempt, e.passed) for e in evaluations]})")

        # ---------- 2. 连续不足 → 达到最大轮次停止 ----------
        reset_user(db, user, kp)

        scripted = ScriptedQuestionAgent(limits=[6, 1, 1, 1, 1])
        master = build_master({"question_generation": scripted})
        out = remember(await run_master(
            master, user, db, f"帮我生成10道{KP_NAME}的练习题。"
        ))
        questions = (out["final_result"]["artifacts"] or {}).get("question_generation") or {}
        loop = out["final_result"]["self_loop"]
        actual = questions.get("actual_count")
        check("上限-修正轮次不超过 2", loop["repair_count"] == MAX_REPAIR_ROUNDS,
              f"({loop['repair_count']})")
        check("上限-停止原因为 max_rounds", loop["stopped_reason"] == "max_rounds",
              f"({loop['stopped_reason']})")
        check("上限-不谎报成功", out["task_status"] in ("partial", "failed"),
              f"({out['task_status']})")
        check("上限-如实报告最终数量", isinstance(actual, int) and actual < 10
              and f"{actual}/10" in out["final_result"]["summary"],
              f"(actual={actual})")
        check("上限-每轮失败原因都有记录",
              len(loop["rounds"]) == 2
              and all(item.get("failure_type") == "count_insufficient" for item in loop["rounds"]),
              f"({[i.get('failure_type') for i in loop['rounds']]})")

        # ---------- 3. 学习计划：每日预算超限 → 原地压缩 ----------
        reset_user(db, user, kp)
        master = build_master({"study_planning": OverBudgetPlanAgent()})
        out = remember(await run_master(
            master, user, db,
            "我还有7天就要考离散数学了，每天能学习2小时，帮我制定复习计划。",
        ))
        plan = (out["final_result"]["artifacts"] or {}).get("study_planning") or {}
        loop = out["final_result"]["self_loop"]
        plan_count = db.query(StudyPlan).filter(StudyPlan.user_id == user.id).count()
        rows = (
            db.query(StudyTask.scheduled_date, StudyTask.estimated_minutes)
            .filter(StudyTask.plan_id == plan.get("plan_id")).all()
        )
        per_day: dict[str, int] = {}
        for day, minutes in rows:
            key = day.isoformat()
            per_day[key] = per_day.get(key, 0) + int(minutes or 0)

        check("预算-识别并修正 1 轮", loop["repair_count"] == 1, f"({loop['repair_count']})")
        check("预算-修正后每日不超限",
              bool(per_day) and all(total <= 120 for total in per_day.values()),
              f"(max={max(per_day.values()) if per_day else None})")
        check("预算-不新建计划（幂等）", plan_count == 1, f"({plan_count})")
        check("预算-考试日期与每日预算未被修改",
              plan.get("exam_date") is not None and plan.get("daily_minutes") == 120,
              f"({plan.get('exam_date')}, {plan.get('daily_minutes')})")
        check("预算-单个任务不低于 15 分钟",
              all(int(minutes or 0) >= 15 for _, minutes in rows))
        check("预算-修正后校验通过",
              loop["rounds"][0]["validation"]["passed"] is True,
              f"({loop['rounds'][0]['validation']})")
        check("预算-整体成功", out["task_status"] == "success", f"({out['task_status']})")

        # ---------- 4. 不可修复：学情数据不足 ----------
        master = build_master({})
        out = remember(await run_master(master, empty_user, db, "帮我分析一下最近的学习情况。"))
        analysis = (out["final_result"]["artifacts"] or {}).get("learning_analysis") or {}
        loop = out["final_result"]["self_loop"]
        check("数据不足-不进行任何修正", loop["repair_count"] == 0
              and loop["stopped_reason"] == "not_repairable",
              f"({loop['repair_count']}, {loop['stopped_reason']})")
        check("数据不足-如实标注且不编造", analysis.get("sufficient") is False,
              f"({analysis.get('sufficient')})")
        check("数据不足-摘要提示补充记录", "数据不足" in out["final_result"]["summary"],
              f"({out['final_result']['summary'][:50]})")

        # ---------- 5. 不可修复：知识检索为空（只换一次关键词）----------
        out = remember(await run_master(
            master, user, db, "帮我解释一下量子纠缠的定义。"
        ))
        retrieval = (out["final_result"]["artifacts"] or {}).get("knowledge_retrieval") or {}
        loop = out["final_result"]["self_loop"]
        check("检索为空-只尝试一次关键词调整", loop["repair_count"] == 1,
              f"({loop['repair_count']})")
        check("检索为空-仍为空且不编造",
              retrieval.get("found") is False and not retrieval.get("results"),
              f"({retrieval.get('found')})")
        check("检索为空-如实报告", "未检索到" in out["final_result"]["summary"],
              f"({out['final_result']['summary'][:60]})")
        check("检索为空-停止原因为不可修复",
              loop["stopped_reason"] in ("not_repairable", "still_failing"),
              f"({loop['stopped_reason']})")

        # ---------- 6. 数据库错误：不盲目重跑，标记人工确认 ----------
        reset_user(db, user, kp)
        master = build_master({"study_planning": BrokenPlanAgent()})
        out = remember(await run_master(
            master, user, db,
            "我还有7天就要考离散数学了，每天能学习2小时，帮我制定复习计划。",
        ))
        loop = out["final_result"]["self_loop"]
        statuses = {item["agent"]: item["status"] for item in out["agent_results"]}
        check("数据库错误-计划步骤标记失败", statuses.get("study_planning") == "failed",
              f"({statuses})")
        check("数据库错误-未重复创建计划",
              db.query(StudyPlan).filter(StudyPlan.user_id == user.id).count() == 0)
        check("数据库错误-停止原因为人工确认", loop["stopped_reason"] == "manual_check",
              f"({loop['stopped_reason']})")
        check("数据库错误-仅 1 轮且不盲目重试", loop["repair_count"] == 1,
              f"({loop['repair_count']})")
        check("数据库错误-整体失败", out["task_status"] == "failed", f"({out['task_status']})")

        # ---------- 7. 超时/异常的分类与策略（单元级）----------
        classifier = FailureClassifier()
        policy = SelfLoopPolicy(MAX_REPAIR_ROUNDS)
        intent = MasterIntent(message="测试", intents=["analysis"])

        readonly_failure = classifier.from_step(StepOutcome(
            order=1, agent="learning_analysis", action="分析",
            status="failed", error="TimeoutError: 执行超时",
        ))
        decision = policy.plan([readonly_failure], by_agent={}, intent=intent, used_rounds=0)
        check("超时-只读 Agent 可重跑",
              readonly_failure.type == AGENT_TIMEOUT and decision.repairable
              and decision.actions[0].kind == "rerun",
              f"({readonly_failure.type}, {decision.actions[0].kind if decision.actions else None})")

        write_failure = classifier.from_step(StepOutcome(
            order=2, agent="study_planning", action="计划",
            status="failed", error="TimeoutError: 执行超时",
        ))
        decision = policy.plan([write_failure], by_agent={}, intent=intent, used_rounds=0)
        check("超时-写入型先确认副作用",
              decision.repairable and decision.actions[0].kind == "confirm",
              f"({decision.actions[0].kind if decision.actions else None})")

        db_failure = classifier.from_step(StepOutcome(
            order=3, agent="question_generation", action="出题",
            status="failed", error="OperationalError: database is locked",
        ))
        check("异常-数据库错误分类正确", db_failure.type == DATABASE_ERROR,
              f"({db_failure.type})")

        question_format = classifier.from_validation("question_set", {
            "checks": [{"name": "题干完整性", "passed": False, "critical": True, "detail": "缺题干"}],
        })
        decision = policy.plan([question_format], by_agent={}, intent=intent, used_rounds=0)
        check("格式-已入库题目不自动删改",
              question_format.type == "format_error" and decision.repairable is False,
              f"({decision.note})")

        # ---------- 8. 日志清理与隔离 ----------
        master = build_master({})
        master.logger.log("other-task-sentinel", "master", "其它任务日志")
        out = remember(await run_master(master, user, db, "帮我分析一下最近的学习情况。"))
        prefix_left = [e for e in master.logger.entries if e.task_id.startswith(out["task_id"])]
        sentinel_left = [e for e in master.logger.entries if e.task_id == "other-task-sentinel"]
        agent_log_left = []
        for agent in master.registry.list_all():
            logger_obj = getattr(agent, "logger", None)
            entries = getattr(logger_obj, "entries", []) or []
            agent_log_left.extend([e for e in entries if e.task_id.startswith(out["task_id"])])

        record = db.query(AgentTaskRecord).filter(
            AgentTaskRecord.task_id == out["task_id"]
        ).first()
        db_logs = db.query(AgentEvaluation).filter(
            AgentEvaluation.agent_task_id == record.id
        ).count() if record else 0
        from app.models import AgentExecutionLog
        db_log_count = db.query(AgentExecutionLog).filter(
            AgentExecutionLog.agent_task_id == record.id
        ).count() if record else 0

        check("日志-内存中本任务日志已清理",
              not prefix_left and not agent_log_left,
              f"(master={len(prefix_left)}, agents={len(agent_log_left)})")
        check("日志-其它任务的日志未被误删", len(sentinel_left) == 1)
        check("日志-数据库正式记录保留", db_log_count > 0, f"({db_log_count} 条)")
        master.logger.clear_task("other-task-sentinel")

        # ---------- 9. 用户隔离 ----------
        other_tasks = db.query(AgentTaskRecord).filter(
            AgentTaskRecord.user_id == user.id,
            AgentTaskRecord.task_id == out["task_id"],
        ).count()
        empty_tasks = db.query(AgentTaskRecord).filter(
            AgentTaskRecord.user_id == empty_user.id,
            AgentTaskRecord.task_id == out["task_id"],
        ).count()
        check("隔离-任务归属正确", other_tasks == 1 and empty_tasks == 0,
              f"({other_tasks}, {empty_tasks})")

    # ---------- 清理 ----------
    for item in (user, empty_user):
        clear_user(db, item)
    db.query(Question).filter(Question.knowledge_point_id == kp.id).delete(
        synchronize_session=False
    )
    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(
        synchronize_session=False
    )
    db.commit()
    purge_master_records(db, [user, empty_user])
    # 测试专用知识点（description=测试用）一并删除，避免题库判重影响下次运行
    if kp_created or (kp.description or "") == "测试用":
        db.delete(kp)
        db.commit()

    leftover = db.query(AgentTaskRecord).filter(
        AgentTaskRecord.user_id.in_([user.id, empty_user.id])
    ).count()
    leftover_plans = db.query(StudyPlan).filter(
        StudyPlan.user_id.in_([user.id, empty_user.id])
    ).count()
    check("清理-测试数据已清除", leftover == 0 and leftover_plans == 0,
          f"({leftover}, {leftover_plans})")

    db.close()
    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
