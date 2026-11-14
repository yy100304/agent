"""第三阶段测试：学情分析 Agent.

覆盖：
- 有真实数据 → 正确读取并分析（数字必须与写入的一致）
- 无数据 → 明确返回"数据不足"并说明缺失项
- 用户隔离 → 空用户不会借用他人的数据
- 执行成功/失败的状态与错误记录
- 原有 LearningService.analyze_learning 仍正常工作

用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_learning_agent.py
"""
import asyncio
import sys
import uuid
from datetime import date, timedelta

from app.agents.core import AgentContext, AgentStatus, AgentTask, CoreAgentRegistry
from app.agents.learning_analysis_agent import LearningAnalysisAgent
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
from app.services.learning_service import LearningService

DATA_USER = "la_data_user"
EMPTY_USER = "la_empty_user"


# ==================== 数据准备工具 ====================

def get_or_create_user(db, username: str, email: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password("test1234"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def clear_user_data(db, user: User) -> None:
    """清理某个测试用户的学习数据（保证测试可重复运行）."""
    db.query(WrongQuestion).filter(WrongQuestion.user_id == user.id).delete(
        synchronize_session=False
    )
    db.query(Answer).filter(Answer.user_id == user.id).delete(
        synchronize_session=False
    )
    db.query(LearningRecord).filter(LearningRecord.user_id == user.id).delete(
        synchronize_session=False
    )
    db.query(LearningProfile).filter(LearningProfile.user_id == user.id).delete(
        synchronize_session=False
    )
    plan_ids = [
        p.id for p in db.query(StudyPlan).filter(StudyPlan.user_id == user.id).all()
    ]
    if plan_ids:
        db.query(StudyTask).filter(StudyTask.plan_id.in_(plan_ids)).delete(
            synchronize_session=False
        )
    db.query(StudyPlan).filter(StudyPlan.user_id == user.id).delete(
        synchronize_session=False
    )
    db.commit()


def ensure_two_kps(db) -> tuple[KnowledgePoint, KnowledgePoint]:
    kps = db.query(KnowledgePoint).limit(2).all()
    while len(kps) < 2:
        kp = KnowledgePoint(
            subject="测试学科",
            name=f"测试知识点{uuid.uuid4().hex[:4]}",
            description="测试用",
            difficulty="medium",
        )
        db.add(kp)
        db.commit()
        db.refresh(kp)
        kps.append(kp)
    return kps[0], kps[1]


def seed_data(db, user, kp_weak, kp_strong) -> None:
    """写入确定性的学习数据：5 题(3 对 2 错)、70 分钟、2 任务(1 完成) 等."""
    # 清理历史测试题（按内容前缀）
    db.query(Question).filter(Question.content.like("【测试】%")).delete(
        synchronize_session=False
    )
    db.commit()

    questions = [
        Question(
            knowledge_point_id=kp_weak.id,
            content=f"【测试】学情题{i}",
            question_type="single_choice",
            options='["A","B"]',
            answer="A",
            explanation="测试解析",
            difficulty="medium",
            source="bank",
        )
        for i in range(3)
    ]
    db.add_all(questions)
    db.commit()
    for q in questions:
        db.refresh(q)

    # 5 次答题：3 对 2 错 → 正确率 0.6
    flags = [True, True, True, False, False]
    answers = [
        Answer(
            user_id=user.id,
            question_id=questions[i % 3].id,
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

    # 2 道错题（对应两道错答，指向不同题目）→ wrong_distribution[kp_weak] = 2
    db.add_all([
        WrongQuestion(
            user_id=user.id,
            question_id=answers[3].question_id,
            reason="测试错误原因",
            suggestion="测试学习建议",
            mastered=False,
            review_count=0,
        ),
        WrongQuestion(
            user_id=user.id,
            question_id=answers[4].question_id,
            reason="测试错误原因",
            suggestion="测试学习建议",
            mastered=False,
            review_count=0,
        ),
    ])
    db.commit()

    # 画像：kp_weak=0.4（薄弱）、kp_strong=0.9（强项）
    db.add_all([
        LearningProfile(
            user_id=user.id, knowledge_point_id=kp_weak.id,
            mastery_score=0.4, confidence=5,
        ),
        LearningProfile(
            user_id=user.id, knowledge_point_id=kp_strong.id,
            mastery_score=0.9, confidence=5,
        ),
    ])
    db.commit()

    # 学习时长：30 + 40 = 70 分钟
    db.add_all([
        LearningRecord(
            user_id=user.id, knowledge_point_id=kp_weak.id,
            study_minutes=30, mastery_score=0.4, source="practice",
        ),
        LearningRecord(
            user_id=user.id, knowledge_point_id=kp_strong.id,
            study_minutes=40, mastery_score=0.9, source="practice",
        ),
    ])
    db.commit()

    # 学习计划 + 2 个今日任务（1 完成）
    plan = StudyPlan(
        user_id=user.id,
        title="测试计划",
        subject="测试学科",
        exam_date=date.today() + timedelta(days=7),
        daily_minutes=60,
        status="active",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    db.add_all([
        StudyTask(
            plan_id=plan.id, knowledge_point_id=kp_weak.id, title="测试任务1",
            estimated_minutes=30, completed=True, scheduled_date=date.today(),
        ),
        StudyTask(
            plan_id=plan.id, knowledge_point_id=kp_strong.id, title="测试任务2",
            estimated_minutes=30, completed=False, scheduled_date=date.today(),
        ),
    ])
    db.commit()


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

    kp_weak, kp_strong = ensure_two_kps(db)
    data_user = get_or_create_user(db, DATA_USER, "la_data@test.com")
    empty_user = get_or_create_user(db, EMPTY_USER, "la_empty@test.com")

    # 保证每次运行起点一致
    clear_user_data(db, data_user)
    clear_user_data(db, empty_user)
    seed_data(db, data_user, kp_weak, kp_strong)

    # 测试时关闭 LLM（规则建议→确定性、零额度消耗）；LLM 路径已实现可随时开启
    agent = LearningAnalysisAgent(use_llm=False)

    # ---------- 1. 有数据：成功分析 ----------
    task = AgentTask(
        task_id=str(uuid.uuid4()), user_id=data_user.id,
        task_type="learning_analysis", input_data={},
    )
    ctx = AgentContext(user_id=data_user.id, username=data_user.username, db=db)
    res = await agent.run(task, ctx)

    check("成功-执行状态", res.success and task.status == AgentStatus.SUCCESS)
    check("成功-执行耗时", res.execution_time >= 0, f"({res.execution_time}s)")
    check("成功-执行日志", len(agent.logger.entries) >= 2,
          f"({len(agent.logger.entries)} 条)")

    out = res.result or {}
    check("成功-数据充分", out.get("sufficient") is True)
    report = out.get("report", {})
    ov = report.get("overview", {})
    check("成功-答题数=5", ov.get("total_questions") == 5, f"({ov.get('total_questions')})")
    check("成功-正确率=0.6", abs((ov.get("recent_accuracy") or 0) - 0.6) < 1e-6,
          f"({ov.get('recent_accuracy')})")
    check("成功-学习时长>=70", (ov.get("total_study_minutes") or 0) >= 70,
          f"({ov.get('total_study_minutes')})")
    check("成功-任务完成 1/2",
          ov.get("task_total") == 2 and ov.get("task_completed") == 1,
          f"({ov.get('task_completed')}/{ov.get('task_total')})")
    check("成功-薄弱知识点", kp_weak.name in report.get("weak_points", []),
          f"({report.get('weak_points')})")
    check("成功-强项知识点", kp_strong.name in report.get("strong_points", []),
          f"({report.get('strong_points')})")
    check("成功-错题分布",
          report.get("wrong_question_distribution", {}).get(kp_weak.name) == 2,
          f"({report.get('wrong_question_distribution')})")
    check("成功-建议非空", bool(out.get("advice")))

    # ---------- 2. 无数据：明确"数据不足" ----------
    etask = AgentTask(
        task_id=str(uuid.uuid4()), user_id=empty_user.id,
        task_type="learning_analysis", input_data={},
    )
    ectx = AgentContext(user_id=empty_user.id, username=empty_user.username, db=db)
    eres = await agent.run(etask, ectx)

    check("不足-执行成功", eres.success and etask.status == AgentStatus.SUCCESS)
    eout = eres.result or {}
    check("不足-标记为不充分", eout.get("sufficient") is False)
    check("不足-提示含数据不足", "数据不足" in (eout.get("message") or ""))
    missing = eout.get("missing") or []
    check("不足-说明缺失项", any("答题" in m for m in missing), f"({missing})")
    check("不足-快照为空", (eout.get("data_snapshot") or {}).get("total_questions") == 0)

    # ---------- 3. 用户隔离：空用户不借用他人数据 ----------
    ls = LearningService(db)
    check("隔离-空用户答题数为0", ls.analyze_learning(empty_user.id)["total_questions"] == 0)
    check("隔离-数据用户仍为5", ls.analyze_learning(data_user.id)["total_questions"] == 5)

    # 越权保护：任务用户与上下文用户不一致应失败
    bad_task = AgentTask(
        task_id=str(uuid.uuid4()), user_id=data_user.id,
        task_type="learning_analysis", input_data={},
    )
    bad_ctx = AgentContext(user_id=empty_user.id, username=empty_user.username, db=db)
    bad_res = await agent.run(bad_task, bad_ctx)
    check("隔离-用户不一致被拒绝",
          (not bad_res.success) and "不一致" in (bad_res.error or ""),
          f"({bad_res.error})")

    # ---------- 4. 执行失败：记录错误 ----------
    fail_agent = LearningAnalysisAgent(use_llm=False)
    ftask = AgentTask(
        task_id=str(uuid.uuid4()), user_id=data_user.id,
        task_type="learning_analysis", input_data={},
    )
    fctx = AgentContext(user_id=data_user.id, username=data_user.username, db=None)
    fres = await fail_agent.run(ftask, fctx)
    check("失败-状态为失败", (not fres.success) and ftask.status == AgentStatus.FAILED)
    check("失败-错误已记录", bool(fres.error), f"({fres.error})")
    check("失败-日志含错误", fail_agent.logger.count("error") > 0,
          f"(error={fail_agent.logger.count('error')})")

    # ---------- 5. 注册机制 ----------
    registry = CoreAgentRegistry()
    registry.register(agent)
    check("注册-可按名取回", registry.require("learning_analysis") is agent)
    check("注册-元信息完整", registry.to_dicts()[0]["name"] == "learning_analysis")

    # ---------- 6. 原有学习分析接口仍正常 ----------
    analysis = ls.analyze_learning(data_user.id)
    expected_keys = {
        "total_study_minutes", "recent_accuracy", "total_questions",
        "task_total", "task_completed", "task_completion_rate",
        "wrong_question_distribution", "weak_points", "strong_points",
    }
    check("原有接口-返回字段完整", expected_keys.issubset(analysis.keys()))
    total_trend = sum(ls.minutes_by_day(data_user.id, 30).values())
    check("原有接口-时长趋势已修复", total_trend >= 70, f"({total_trend}m)")
    summary = ls.get_learning_profile_summary(data_user.id)
    check("原有接口-画像摘要正常",
          isinstance(summary.get("mastery"), dict)
          and summary.get("wrong_question_count", 0) >= 2)

    # ---------- 清理测试数据（不触碰业务表与既有用户）----------
    clear_user_data(db, data_user)
    clear_user_data(db, empty_user)
    db.query(Question).filter(Question.content.like("【测试】%")).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
