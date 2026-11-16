"""第五阶段测试：学习计划 Agent.

覆盖：
- 正常生成多日学习计划
- 每日学习总时长不超过上限（按天汇总该用户全部 StudyTask）
- 结合学情调整学习重点（薄弱点）
- 结合知识检索结果丰富任务内容
- 缺少必要参数时明确提示
- 写入成功后可被现有服务层读取（前端数据来源）
- 写入失败时事务回滚，不产生半截数据
- 不同用户数据隔离

测试数据标识：所有测试计划标题以「【测试】」开头，清理仅针对本次生成的 plan_id。

用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_study_planning_agent.py
"""
import asyncio
import sys
import uuid
from datetime import date, timedelta

from sqlalchemy import func

from app.agents.core import AgentContext, AgentStatus, AgentTask
from app.agents.study_planning_agent import StudyPlanningAgent
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import (
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
from app.services.dashboard_service import DashboardService

MARK = "【测试】"
TEST_USERS = ("sp_test_data", "sp_test_empty", "sp_test_other")


# ==================== 测试数据工具 ====================

def get_or_create_user(db, username: str, email: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, email=email, password_hash=hash_password("test1234"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def test_plan_ids_of(db, user: User) -> list[int]:
    return [
        p.id for p in db.query(StudyPlan)
        .filter(StudyPlan.user_id == user.id, StudyPlan.title.like(f"{MARK}%"))
        .all()
    ]


def delete_plans(db, plan_ids: list[int]) -> tuple[int, int]:
    if not plan_ids:
        return 0, 0
    t = db.query(StudyTask).filter(StudyTask.plan_id.in_(plan_ids)).delete(
        synchronize_session=False
    )
    p = db.query(StudyPlan).filter(StudyPlan.id.in_(plan_ids)).delete(
        synchronize_session=False
    )
    db.commit()
    return t, p


def clear_user_learning(db, user: User) -> None:
    db.query(WrongQuestion).filter(WrongQuestion.user_id == user.id).delete(synchronize_session=False)
    db.query(Answer).filter(Answer.user_id == user.id).delete(synchronize_session=False)
    db.query(LearningRecord).filter(LearningRecord.user_id == user.id).delete(synchronize_session=False)
    db.query(LearningProfile).filter(LearningProfile.user_id == user.id).delete(synchronize_session=False)
    db.commit()


def ensure_kp(db, name: str) -> tuple[KnowledgePoint, bool]:
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.name == name).first()
    if kp:
        return kp, False
    kp = KnowledgePoint(subject="离散数学", name=name, description="测试用", difficulty="hard")
    db.add(kp)
    db.commit()
    db.refresh(kp)
    return kp, True


def seed_learning_data(db, user: User, kp: KnowledgePoint) -> None:
    """为测试用户造确定性学情：3 题(2 对 1 错)、薄弱点=该知识点."""
    db.query(Question).filter(Question.content.like("【测试】计划题%")).delete(
        synchronize_session=False
    )
    db.commit()

    questions = [
        Question(
            knowledge_point_id=kp.id,
            content=f"【测试】计划题{i}",
            question_type="single_choice",
            options='["A","B"]',
            answer="A",
            explanation="测试解析",
            difficulty="medium",
            source="bank",
        )
        for i in range(2)
    ]
    db.add_all(questions)
    db.commit()
    for q in questions:
        db.refresh(q)

    flags = [True, True, False]
    answers = [
        Answer(
            user_id=user.id,
            question_id=questions[i % 2].id,
            user_answer="A" if c else "B",
            is_correct=c,
            score=1.0 if c else 0.0,
        )
        for i, c in enumerate(flags)
    ]
    db.add_all(answers)
    db.commit()
    for a in answers:
        db.refresh(a)

    db.add(WrongQuestion(
        user_id=user.id, question_id=answers[2].question_id,
        reason="测试错误原因", suggestion="测试建议", mastered=False, review_count=0,
    ))
    # 薄弱画像：掌握度 0.35 < 0.65
    db.add(LearningProfile(
        user_id=user.id, knowledge_point_id=kp.id, mastery_score=0.35, confidence=5,
    ))
    db.add(LearningRecord(
        user_id=user.id, knowledge_point_id=kp.id, study_minutes=60,
        mastery_score=0.35, source="practice",
    ))
    db.commit()


class BrokenPersistAgent(StudyPlanningAgent):
    """故障注入：flush 后抛异常，用于验证事务回滚."""

    def _persist(self, db, plan, tasks):
        db.add(plan)
        db.flush()                     # 已分配 id，但未提交
        raise RuntimeError("模拟写入失败")


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
    db = SessionLocal()

    data_user = get_or_create_user(db, "sp_test_data", "sp_data@test.com")
    empty_user = get_or_create_user(db, "sp_test_empty", "sp_empty@test.com")
    other_user = get_or_create_user(db, "sp_test_other", "sp_other@test.com")

    # 预清理：仅清理这些测试用户且带【测试】标识的历史计划（保证可重复运行）
    for u in (data_user, empty_user, other_user):
        delete_plans(db, test_plan_ids_of(db, u))

    clear_user_learning(db, data_user)
    clear_user_learning(db, empty_user)

    kp, kp_created = ensure_kp(db, "图论")
    seed_learning_data(db, data_user, kp)

    created_plan_ids: list[int] = []
    agent = StudyPlanningAgent()
    ctx = AgentContext(user_id=data_user.id, username=data_user.username, db=db)
    today = date.today()

    # ---------- 1. 正常生成多日计划 ----------
    task = AgentTask(
        task_id=str(uuid.uuid4()), user_id=data_user.id,
        task_type="study_planning",
        input_data={
            "exam_date": (today + timedelta(days=4)).isoformat(),
            "daily_minutes": 60,
            "subject": "离散数学",
            "title": f"{MARK}正常计划",
            "goal": "图论 割点",
        },
    )
    res = await agent.run(task, ctx)
    out = res.result or {}
    if out.get("plan_id"):
        created_plan_ids.append(out["plan_id"])

    check("多日-执行成功", res.success and task.status == AgentStatus.SUCCESS)
    check("多日-已创建", out.get("created") is True and out.get("plan_id", 0) > 0,
          f"(plan_id={out.get('plan_id')})")
    check("多日-天数=4", out.get("days") == 4, f"({out.get('days')})")
    check("多日-任务数>0", out.get("task_count", 0) > 0, f"(tasks={out.get('task_count')})")

    # ---------- 2. 每日总时长不超过上限（汇总该用户当天全部 StudyTask）----------
    summary = out.get("daily_summary") or {}
    limit = out.get("daily_minutes", 60)
    check("时长-汇总覆盖 4 天", len(summary) == 4, f"({len(summary)})")
    check("时长-每日不超上限",
          all(v["total"] <= limit for v in summary.values()),
          f"({ {k: v['total'] for k, v in summary.items()} })")

    db_rows = (
        db.query(StudyTask.scheduled_date, func.sum(StudyTask.estimated_minutes))
        .filter(StudyTask.plan_id == out["plan_id"])
        .group_by(StudyTask.scheduled_date)
        .all()
    )
    check("时长-数据库逐日复核",
          all(int(m) <= limit for _, m in db_rows),
          f"({[(str(d), int(m)) for d, m in db_rows]})")

    # ---------- 3. 结合学情调整重点 ----------
    check("学情-薄弱点识别", "图论" in (out.get("weak_points") or []),
          f"({out.get('weak_points')})")
    check("学情-重点纳入图论", "图论" in (out.get("focus_points") or []),
          f"({out.get('focus_points')})")
    check("学情-数据充分无警告", out.get("data_warning") is False)

    # ---------- 4. 结合知识检索结果 ----------
    check("检索-已使用", out.get("retrieval_used") is True)
    check("检索-命中知识点", bool(out.get("retrieval_points")),
          f"({out.get('retrieval_points')})")
    descs = [
        t.description for t in
        db.query(StudyTask).filter(StudyTask.plan_id == out["plan_id"]).all()
    ]
    enriched = any("：" in d and d.split("：", 1)[1].strip() for d in descs)
    check("检索-任务描述含真实内容", enriched)

    # ---------- 5. 缺少必要参数 ----------
    t_missing = AgentTask(
        task_id=str(uuid.uuid4()), user_id=data_user.id,
        task_type="study_planning", input_data={},
    )
    r_missing = await agent.run(t_missing, ctx)
    o_missing = r_missing.result or {}
    check("缺参-未创建", o_missing.get("created") is False)
    check("缺参-列出全部缺失",
          set(o_missing.get("missing_params") or []) == {"exam_date", "daily_minutes"},
          f"({o_missing.get('missing_params')})")
    check("缺参-提示明确", "缺少必要参数" in (o_missing.get("message") or ""))

    t_only_date = AgentTask(
        task_id=str(uuid.uuid4()), user_id=data_user.id, task_type="study_planning",
        input_data={"exam_date": (today + timedelta(days=3)).isoformat()},
    )
    r_only_date = await agent.run(t_only_date, ctx)
    check("缺参-仅缺时长",
          (r_only_date.result or {}).get("missing_params") == ["daily_minutes"])

    t_past = AgentTask(
        task_id=str(uuid.uuid4()), user_id=data_user.id, task_type="study_planning",
        input_data={"exam_date": (today - timedelta(days=1)).isoformat(), "daily_minutes": 60},
    )
    r_past = await agent.run(t_past, ctx)
    check("缺参-过期日期被拒",
          (r_past.result or {}).get("created") is False
          and "考试日期" in ((r_past.result or {}).get("message") or ""))

    # ---------- 6. 写入后可被现有服务层读取（前端数据来源）----------
    plan = db.get(StudyPlan, out["plan_id"])
    check("读取-计划存在", plan is not None and plan.user_id == data_user.id)
    check("读取-计划字段正确",
          plan.exam_date == today + timedelta(days=4)
          and plan.daily_minutes == 60 and plan.status == "active")
    task_cnt = db.query(StudyTask).filter(StudyTask.plan_id == plan.id).count()
    check("读取-任务数量一致", task_cnt == out["task_count"],
          f"(db={task_cnt}, result={out['task_count']})")
    dash = DashboardService(db).build_summary(data_user)
    check("读取-看板可读取今日任务", len(dash["today_tasks"]) >= 1,
          f"(今日任务 {len(dash['today_tasks'])} 条)")

    # ---------- 6.1 既有任务占用预算：同期再生成应被拒绝 ----------
    t_overlap = AgentTask(
        task_id=str(uuid.uuid4()), user_id=data_user.id, task_type="study_planning",
        input_data={
            "exam_date": (today + timedelta(days=2)).isoformat(),
            "daily_minutes": 60,
            "subject": "离散数学",
            "title": f"{MARK}重叠用例",
        },
    )
    r_overlap = await agent.run(t_overlap, ctx)
    o_overlap = r_overlap.result or {}
    check("预算-既有任务占满被识别",
          o_overlap.get("created") is False
          and "占满" in (o_overlap.get("message") or ""),
          f"({o_overlap.get('message')})")

    # ---------- 7. 写入失败 → 事务回滚 ----------
    # 用无历史计划/任务的空用户，避免受当天预算占用影响，确保真正执行到落库
    broken = BrokenPersistAgent()
    rollback_ctx = AgentContext(
        user_id=empty_user.id, username=empty_user.username, db=db
    )
    t_rollback = AgentTask(
        task_id=str(uuid.uuid4()), user_id=empty_user.id, task_type="study_planning",
        input_data={
            "exam_date": (today + timedelta(days=3)).isoformat(),
            "daily_minutes": 60,
            "subject": "离散数学",
            "title": f"{MARK}回滚用例",
        },
    )
    r_rollback = await broken.run(t_rollback, rollback_ctx)
    check("回滚-执行失败",
          (not r_rollback.success) and t_rollback.status == AgentStatus.FAILED)
    check("回滚-错误已记录", "模拟写入失败" in (r_rollback.error or ""),
          f"({r_rollback.error})")
    leftover = (
        db.query(StudyPlan)
        .filter(StudyPlan.user_id == empty_user.id, StudyPlan.title == f"{MARK}回滚用例")
        .count()
    )
    check("回滚-无半截计划残留", leftover == 0, f"(残留 {leftover})")

    # ---------- 8. 用户数据隔离 ----------
    t_iso = AgentTask(
        task_id=str(uuid.uuid4()), user_id=data_user.id, task_type="study_planning",
        input_data={"exam_date": (today + timedelta(days=3)).isoformat(), "daily_minutes": 60},
    )
    iso_ctx = AgentContext(user_id=other_user.id, username=other_user.username, db=db)
    r_iso = await agent.run(t_iso, iso_ctx)
    check("隔离-用户不一致被拒",
          (not r_iso.success) and "不一致" in (r_iso.error or ""), f"({r_iso.error})")
    other_plans = db.query(StudyPlan).filter(StudyPlan.user_id == other_user.id).count()
    check("隔离-他人无计划", other_plans == 0, f"(other={other_plans})")

    # ---------- 清理：仅删除本次生成的 plan_id + 测试学情 ----------
    del_tasks, del_plans = delete_plans(db, created_plan_ids)
    clear_user_learning(db, data_user)
    clear_user_learning(db, empty_user)
    db.query(Question).filter(Question.content.like("【测试】计划题%")).delete(
        synchronize_session=False
    )
    if kp_created:
        db.query(StudyTask).filter(StudyTask.knowledge_point_id == kp.id).delete(
            synchronize_session=False
        )
        db.delete(kp)
    db.commit()

    remaining = (
        db.query(StudyPlan)
        .filter(
            StudyPlan.user_id.in_([data_user.id, empty_user.id, other_user.id]),
            StudyPlan.title.like(f"{MARK}%"),
        )
        .count()
    )
    check("清理-无测试计划残留", remaining == 0, f"(残留 {remaining})")

    print(f"\n清理结果: 删除任务 {del_tasks} 条 / 计划 {del_plans} 条 / "
          f"测试知识点{'已删除' if kp_created else '复用未删'}")
    db.close()

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
