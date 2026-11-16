"""第八阶段测试：主控 Agent（Master Agent）.

覆盖：
1. 单 Agent 调度：学情分析 / 知识检索 / 学习计划 / 练习生成
2. 多 Agent 协同：学情 → 检索 → 计划 → 出题 → 校验
3. 真实数据传递：前序 Agent 输出是否注入后序 Agent 的输入
4. 参数缺失：追问用户，不执行任何专业 Agent
5. 异常：前置 Agent 失败 → 下游 skipped、整体 failed，不谎报成功
6. 部分成功：出题数量不足 → partial，摘要按真实数量报告
7. 仅校验已有结果：校验不通过时如实失败
8. 用户隔离：用户 B 读不到用户 A 的学情数据，任务记录按用户隔离
9. 执行留痕：agent_tasks / workflows / workflow_steps / agent_execution_logs

测试不消耗 DeepSeek 额度：llm_service.chat 被临时替换为返回 None，
所有 Agent 走既有的规则/题库降级路径（与线上无 Key 时的行为一致）。

用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_master_agent.py
"""
import asyncio
import sys
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import app.main  # noqa: F401  确认应用可正常构建
from app.agents.core import AgentContext, AgentTask
from app.agents.core.registry import core_registry
from app.agents.master.master_agent import MasterAgent
from app.agents.registration import register_core_agents
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import (
    AgentExecutionLog,
    AgentTaskRecord,
    Answer,
    KnowledgePoint,
    LearningProfile,
    LearningRecord,
    Question,
    StudyPlan,
    StudyTask,
    User,
    WorkflowRecord,
    WorkflowStepRecord,
    WrongQuestion,
)
from app.services.llm_service import llm_service

KP_NAME = "关系与闭包"          # 命中知识库关键词「关系」，同时是独立测试知识点
Q_PREFIX = "【测试】MS"


# ==================== 测试数据工具 ====================

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


def clear_user_learning(db, user: User) -> None:
    db.query(WrongQuestion).filter(WrongQuestion.user_id == user.id).delete(
        synchronize_session=False
    )
    db.query(Answer).filter(Answer.user_id == user.id).delete(synchronize_session=False)
    db.query(LearningRecord).filter(LearningRecord.user_id == user.id).delete(
        synchronize_session=False
    )
    db.query(LearningProfile).filter(LearningProfile.user_id == user.id).delete(
        synchronize_session=False
    )
    db.commit()


def seed_learning_data(db, user: User, kp: KnowledgePoint) -> None:
    """为测试用户造确定性学情：3 次答题(2 对 1 错)、薄弱点=该知识点."""
    questions = [
        Question(
            knowledge_point_id=kp.id,
            content=f"{Q_PREFIX}题{i}",
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
            user_answer="A" if correct else "B",
            is_correct=correct,
            score=1.0 if correct else 0.0,
        )
        for i, correct in enumerate(flags)
    ]
    db.add_all(answers)
    db.commit()
    for a in answers:
        db.refresh(a)

    db.add(WrongQuestion(
        user_id=user.id, question_id=answers[2].question_id,
        reason="测试错误原因", suggestion="测试建议", mastered=False, review_count=0,
    ))
    db.add(LearningProfile(
        user_id=user.id, knowledge_point_id=kp.id, mastery_score=0.35, confidence=5,
    ))
    db.add(LearningRecord(
        user_id=user.id, knowledge_point_id=kp.id, study_minutes=60,
        mastery_score=0.35, source="practice",
    ))
    db.commit()


def delete_master_records(db, users: list[User]) -> None:
    """删除测试用户的主控任务相关记录（日志 → 步骤 → 工作流 → 任务）."""
    task_rows = (
        db.query(AgentTaskRecord)
        .filter(AgentTaskRecord.user_id.in_([u.id for u in users]))
        .all()
    )
    task_ids = [r.id for r in task_rows]
    if not task_ids:
        return
    workflow_ids = [
        w.id for w in db.query(WorkflowRecord)
        .filter(WorkflowRecord.agent_task_id.in_(task_ids)).all()
    ]
    if workflow_ids:
        db.query(WorkflowStepRecord).filter(
            WorkflowStepRecord.workflow_id.in_(workflow_ids)
        ).delete(synchronize_session=False)
        db.query(WorkflowRecord).filter(
            WorkflowRecord.id.in_(workflow_ids)
        ).delete(synchronize_session=False)
    db.query(AgentExecutionLog).filter(
        AgentExecutionLog.agent_task_id.in_(task_ids)
    ).delete(synchronize_session=False)
    db.query(AgentTaskRecord).filter(
        AgentTaskRecord.id.in_(task_ids)
    ).delete(synchronize_session=False)
    db.commit()


async def run_master(
    master: MasterAgent, user: User, db, message: str, **options
) -> dict:
    task = AgentTask(
        task_id=str(uuid.uuid4()),
        user_id=user.id,
        task_type="master",
        input_data={"message": message, **options},
    )
    context = AgentContext(
        user_id=user.id, username=user.username, db=db,
        request={"message": message},
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

    user_a = get_or_create_user(db, "master_test_a", "master_a@test.com")
    user_b = get_or_create_user(db, "master_test_b", "master_b@test.com")

    # ---- 预清理：仅清理本测试用户的数据与标记过的测试题目/计划 ----
    for user in (user_a, user_b):
        clear_user_learning(db, user)
    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(
        synchronize_session=False
    )
    stale = [
        p.id for p in db.query(StudyPlan)
        .filter(StudyPlan.user_id.in_([user_a.id, user_b.id])).all()
    ]
    if stale:
        db.query(StudyTask).filter(StudyTask.plan_id.in_(stale)).delete(
            synchronize_session=False
        )
        db.query(StudyPlan).filter(StudyPlan.id.in_(stale)).delete(
            synchronize_session=False
        )
    db.commit()
    delete_master_records(db, [user_a, user_b])

    kp, kp_created = ensure_kp(db, KP_NAME)
    seed_learning_data(db, user_a, kp)

    ctx_task_ids: list[str] = []
    created_plan_ids: list[int] = []
    created_question_ids: list[int] = []

    def remember(result: dict) -> dict:
        ctx_task_ids.append(result["task_id"])
        plan = (result.get("final_result", {}).get("artifacts") or {}).get("study_planning")
        if isinstance(plan, dict) and plan.get("plan_id"):
            created_plan_ids.append(int(plan["plan_id"]))
        questions = (result.get("final_result", {}).get("artifacts") or {}).get("question_generation")
        if isinstance(questions, dict):
            created_question_ids.extend(int(i) for i in (questions.get("question_ids") or []))
        return result

    # 规则解析 + 无 LLM：chat 一律返回 None（走降级路径，不消耗额度）
    master = MasterAgent(use_llm_intent=False)

    with patch.object(llm_service, "chat", return_value=None):
        # ---------- 1. 单 Agent：学情分析 ----------
        out = remember(await run_master(master, user_a, db, "帮我分析一下最近的学习情况。"))
        analysis = out["final_result"]["artifacts"].get("learning_analysis") or {}
        check("单-Agent 学情-调度正确",
              out["executed_agents"] == ["learning_analysis"], f"({out['executed_agents']})")
        check("单-Agent 学情-状态成功", out["task_status"] == "success",
              f"({out['task_status']})")
        check("单-Agent 学情-读到真实薄弱点",
              analysis.get("sufficient") is True
              and KP_NAME in ((analysis.get("report") or {}).get("weak_points") or []),
              f"(weak={(analysis.get('report') or {}).get('weak_points')})")

        # ---------- 2. 单 Agent：知识检索 ----------
        out = remember(await run_master(
            master, user_a, db, "帮我解释一下离散数学中的关系与闭包。"
        ))
        retrieval = out["final_result"]["artifacts"].get("knowledge_retrieval") or {}
        check("单-Agent 检索-调度正确",
              out["executed_agents"] == ["knowledge_retrieval"], f"({out['executed_agents']})")
        check("单-Agent 检索-真实命中",
              retrieval.get("found") is True and retrieval.get("count", 0) >= 1,
              f"(count={retrieval.get('count')})")

        # ---------- 3. 单 Agent：学习计划（含依赖与校验） ----------
        out = remember(await run_master(
            master, user_a, db,
            "我还有7天就要考离散数学了，每天能学习2小时，帮我制定复习计划。",
        ))
        artifacts = out["final_result"]["artifacts"]
        plan = artifacts.get("study_planning") or {}
        plan_checks = out["final_result"]["validations"]
        check("计划-调度链路正确",
              out["executed_agents"] == [
                  "learning_analysis", "knowledge_retrieval",
                  "study_planning", "result_validation",
              ], f"({out['executed_agents']})")
        check("计划-已真实落库",
              bool(plan.get("plan_id")) and plan.get("task_count", 0) >= 1,
              f"(plan_id={plan.get('plan_id')}, tasks={plan.get('task_count')})")
        check("计划-每日预算不超过用户上限",
              all(info["total"] <= 120 for info in (plan.get("daily_summary") or {}).values()))
        check("计划-复用真实学情薄弱点", KP_NAME in (plan.get("weak_points") or []),
              f"(weak={plan.get('weak_points')})")
        check("计划-复用真实检索内容", plan.get("retrieval_used") is True)
        check("计划-结果校验通过",
              bool(plan_checks) and plan_checks[0]["passed"] is True,
              f"({[v.get('issues') for v in plan_checks]})")
        check("计划-整体成功", out["task_status"] == "success", f"({out['task_status']})")

        # 清理该计划：它已占用未来 7 天全部学习时长，会挤占后续场景的每日预算
        if plan.get("plan_id"):
            pid = int(plan["plan_id"])
            db.query(StudyTask).filter(StudyTask.plan_id == pid).delete(
                synchronize_session=False
            )
            db.query(StudyPlan).filter(StudyPlan.id == pid).delete(
                synchronize_session=False
            )
            db.commit()
            if pid in created_plan_ids:
                created_plan_ids.remove(pid)

        # ---------- 4. 单 Agent：练习生成 ----------
        out = remember(await run_master(
            master, user_a, db, "帮我生成2道离散数学的中等难度单选题。"
        ))
        questions = out["final_result"]["artifacts"].get("question_generation") or {}
        check("出题-只调度出题 Agent",
              out["executed_agents"] == ["question_generation"], f"({out['executed_agents']})")
        check("出题-数量与参数准确",
              questions.get("actual_count") == 2
              and questions.get("requested_count") == 2
              and questions.get("difficulty") == "medium"
              and questions.get("question_types") == ["single_choice"],
              f"(actual={questions.get('actual_count')}, "
              f"difficulty={questions.get('difficulty')}, "
              f"types={questions.get('question_types')})")

        # ---------- 5. 多 Agent 协同 ----------
        out = remember(await run_master(
            master, user_a, db,
            "我还有7天就要考离散数学了，每天可以学习2小时，"
            "帮我制定计划，并根据我的薄弱知识点生成练习题。",
        ))
        artifacts = out["final_result"]["artifacts"]
        plan = artifacts.get("study_planning") or {}
        questions = artifacts.get("question_generation") or {}
        steps_out = out["agent_results"]
        check("协同-调度 5 类 Agent",
              out["executed_agents"] == [
                  "learning_analysis", "knowledge_retrieval",
                  "study_planning", "question_generation", "result_validation",
              ], f"({out['executed_agents']})")
        check("协同-执行 5 个步骤（含 1 次校验）", len(steps_out) == 5,
              f"({[s['agent'] for s in steps_out]})")
        check("协同-计划与出题均已落库",
              bool(plan.get("plan_id")) and questions.get("actual_count") == 5,
              f"(plan_id={plan.get('plan_id')}, questions={questions.get('actual_count')})")

        q_inputs = next(
            (s for s in steps_out if s["agent"] == "question_generation"), {}
        ).get("input_summary") or {}
        plan_inputs = next(
            (s for s in steps_out if s["agent"] == "study_planning"), {}
        ).get("input_summary") or {}
        check("协同-出题真实接收学情/检索结果",
              "analysis_result" in q_inputs and "retrieval_result" in q_inputs,
              f"({sorted(q_inputs.keys())})")
        check("协同-计划真实接收学情/检索结果",
              "analysis_result" in plan_inputs and "retrieval_result" in plan_inputs,
              f"({sorted(plan_inputs.keys())})")
        check("协同-出题知识点来自学情薄弱点",
              (questions.get("knowledge_point") or {}).get("name") in
              ((plan.get("weak_points") or []) + [KP_NAME]),
              f"(kp={(questions.get('knowledge_point') or {}).get('name')})")
        check("协同-结果校验通过",
              bool(out["final_result"]["validations"])
              and all(v["passed"] for v in out["final_result"]["validations"] if v["executed"]),
              f"({[v.get('issues') for v in out['final_result']['validations']]})")
        check("协同-整体成功", out["task_status"] == "success", f"({out['task_status']})")

        # ---------- 6. 参数缺失：追问用户 ----------
        plans_before = db.query(StudyPlan).filter(StudyPlan.user_id == user_a.id).count()
        out = remember(await run_master(master, user_a, db, "帮我制定一个复习计划。"))
        pending = out["final_result"].get("pending_questions") or []
        plans_after = db.query(StudyPlan).filter(StudyPlan.user_id == user_a.id).count()
        check("缺参-状态为追问", out["task_status"] == "need_input", f"({out['task_status']})")
        check("缺参-明确追问考试日期与每日时长",
              len(pending) == 2 and any("考试日期" in p for p in pending)
              and any("分钟" in p for p in pending), f"({pending})")
        check("缺参-不执行任何专业 Agent",
              out["executed_agents"] == [] and plans_after == plans_before)

        # ---------- 7. 异常：前置 Agent 失败 → 下游阻断 ----------
        agent = core_registry.require("study_planning")
        original_execute = agent.execute

        async def boom(task, context):
            raise RuntimeError("模拟学习计划写入失败")

        agent.execute = boom
        try:
            out = remember(await run_master(
                master, user_a, db,
                "我还有7天就要考离散数学了，每天能学习2小时，帮我制定复习计划。",
            ))
        finally:
            agent.execute = original_execute

        step_status = {s["agent"]: s["status"] for s in out["agent_results"]}
        check("异常-计划步骤失败", step_status.get("study_planning") == "failed",
              f"({step_status})")
        check("异常-依赖步骤被跳过", step_status.get("result_validation") == "skipped",
              f"({step_status})")
        check("异常-整体判定为失败", out["task_status"] == "failed", f"({out['task_status']})")
        check("异常-不谎报计划已保存",
              "已保存学习计划" not in out["final_result"]["summary"]
              and "study_planning" not in out["final_result"]["artifacts"],
              f"({out['final_result']['summary'][:60]})")
        check("异常-给出可读问题",
              any("学习计划" in item for item in out["final_result"]["issues"]),
              f"({out['final_result']['issues']})")

        # ---------- 8. 部分成功：题量不足如实上报 ----------
        out = remember(await run_master(
            master, user_a, db, "帮我生成10道离散数学的困难简答题。"
        ))
        questions = out["final_result"]["artifacts"].get("question_generation") or {}
        actual = questions.get("actual_count")
        check("部分成功-整体为 partial", out["task_status"] in ("partial", "failed"),
              f"({out['task_status']})")
        check("部分成功-数量如实（10 道未凑满）",
              isinstance(actual, int) and actual < 10, f"(actual={actual})")
        check("部分成功-摘要使用真实数字",
              f"{actual}/10" in out["final_result"]["summary"],
              f"({out['final_result']['summary'][:80]})")

        # ---------- 9. 仅校验已有结果 ----------
        bad_plan = StudyPlan(
            user_id=user_a.id, title="【测试】无考试日期的计划", subject="离散数学",
            exam_date=None, daily_minutes=60, status="active",
        )
        db.add(bad_plan)
        db.commit()
        db.refresh(bad_plan)
        db.add(StudyTask(
            plan_id=bad_plan.id, title="【测试】任务", description="测试",
            estimated_minutes=30, completed=False, scheduled_date=date.today(),
        ))
        db.commit()
        created_plan_ids.append(bad_plan.id)

        out = remember(await run_master(master, user_a, db, "检查一下我的学习计划是否合理。"))
        validations = out["final_result"]["validations"]
        check("校验已有结果-只调度校验 Agent",
              out["executed_agents"] == ["result_validation"], f"({out['executed_agents']})")
        check("校验已有结果-真实执行并识别问题",
              bool(validations) and validations[0]["executed"] is True
              and validations[0]["passed"] is False
              and any("考试日期" in i for i in validations[0]["issues"]),
              f"({validations[0]['issues'] if validations else None})")
        check("校验已有结果-整体如实失败", out["task_status"] == "failed",
              f"({out['task_status']})")

        # ---------- 10. 用户隔离 ----------
        out_b = remember(await run_master(master, user_b, db, "帮我分析一下最近的学习情况。"))
        analysis_b = out_b["final_result"]["artifacts"].get("learning_analysis") or {}
        check("隔离-用户B读不到用户A的学情",
              analysis_b.get("sufficient") is False, f"({analysis_b.get('sufficient')})")
        check("隔离-用户B任务未产生任何计划",
              analysis_b.get("sufficient") is False
              and db.query(StudyPlan).filter(StudyPlan.user_id == user_b.id).count() == 0)

        # ---------- 11. 身份不一致被拒 ----------
        mismatch = AgentTask(
            task_id=str(uuid.uuid4()), user_id=user_b.id, task_type="master",
            input_data={"message": "帮我分析一下最近的学习情况。"},
        )
        ctx_a = AgentContext(user_id=user_a.id, username=user_a.username, db=db)
        bad = await master.run(mismatch, ctx_a)
        check("隔离-任务用户与登录用户不一致被拒",
              bad.success is False and "不一致" in (bad.error or ""), f"({bad.error})")

    # ---------- 12. 执行留痕（落库） ----------
    last_task_id = ctx_task_ids[4] if len(ctx_task_ids) > 4 else ctx_task_ids[-1]
    record = db.query(AgentTaskRecord).filter(
        AgentTaskRecord.task_id == last_task_id
    ).first()
    check("落库-任务主记录存在",
          record is not None and record.user_id == user_a.id,
          f"(status={record.status if record else None})")
    workflow = None
    if record:
        workflow = db.query(WorkflowRecord).filter(
            WorkflowRecord.agent_task_id == record.id
        ).order_by(WorkflowRecord.id.desc()).first()
    check("落库-执行计划存在", workflow is not None)
    steps = (
        db.query(WorkflowStepRecord)
        .filter(WorkflowStepRecord.workflow_id == workflow.id)
        .order_by(WorkflowStepRecord.step_order.asc()).all()
        if workflow else []
    )
    check("落库-步骤记录完整",
          len(steps) == 5 and all(s.output_json for s in steps),
          f"({[s.agent_name for s in steps]})")
    logs = (
        db.query(AgentExecutionLog)
        .filter(AgentExecutionLog.agent_task_id == record.id).count()
        if record else 0
    )
    check("落库-执行日志存在", logs > 0, f"({logs} 条)")
    check("落库-步骤输入包含真实数据传递",
          any(s.input_json and "analysis_result" in s.input_json for s in steps
              if s.agent_name == "study_planning"))

    # ---------- 清理 ----------
    if created_plan_ids:
        db.query(StudyTask).filter(StudyTask.plan_id.in_(created_plan_ids)).delete(
            synchronize_session=False
        )
        db.query(StudyPlan).filter(StudyPlan.id.in_(created_plan_ids)).delete(
            synchronize_session=False
        )
    if created_question_ids:
        db.query(Question).filter(Question.id.in_(created_question_ids)).delete(
            synchronize_session=False
        )
    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(
        synchronize_session=False
    )
    for user in (user_a, user_b):
        clear_user_learning(db, user)
    db.commit()
    delete_master_records(db, [user_a, user_b])
    if kp_created:
        db.delete(kp)
        db.commit()

    leftover_plans = db.query(StudyPlan).filter(
        StudyPlan.user_id.in_([user_a.id, user_b.id])
    ).count()
    leftover_tasks = db.query(AgentTaskRecord).filter(
        AgentTaskRecord.user_id.in_([user_a.id, user_b.id])
    ).count()
    check("清理-测试数据已清除",
          leftover_plans == 0 and leftover_tasks == 0,
          f"(plans={leftover_plans}, agent_tasks={leftover_tasks})")

    db.close()
    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
