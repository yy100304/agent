"""第七阶段测试：结果验证 Agent.

覆盖：
- 题目集合：数量达标、题型/选项/答案合法性、解析完整、去重、难度校验
- 题目集合：落库记录完整性（缺失 id 能识别）
- 学习计划：必填字段、任务非空、每日时长不超限、落库数量/归属/时长一致性
- 学情分析：数据不足如实标注（不算失败）、结构完整、非关键项不否决整体
- 学情分析：与数据库真实数据交叉校验（数据不足不编造报告、夸大答题/任务数被拦截）
- 知识检索：未命中如实返回、命中但空结果报错
- 通用校验：required_fields（支持嵌套路径）
- payload 来源：context.shared 复用、target 别名与自动推断
- LLM 辅助：注入评分器（低分否决、高分通过）、未启用时不调用
- 空 payload 不抛异常；用户隔离；只读（不改变数据库）
- 与现有题目/计划数据共存（清理仅限测试标记）

测试数据标识：题目题干以「【测试】RV」开头，计划标题以「【测试】RV」开头。
测试不消耗 DeepSeek 额度：LLM 评分器通过子类注入。

用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_result_validation_agent.py
"""
import asyncio
import json
import sys
import uuid
from datetime import date, timedelta

import app.main  # noqa: F401  确认应用可正常构建
from app.agents.core import AgentContext, AgentStatus, AgentTask
from app.agents.result_validation_agent import ResultValidationAgent
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import Answer, KnowledgePoint, Question, StudyPlan, StudyTask, User

Q_PREFIX = "【测试】RV"
PLAN_PREFIX = "【测试】RV"


# ==================== 测试数据工具 ====================

def get_or_create_user(db, username: str, email: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, email=email, password_hash=hash_password("test1234"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def ensure_kp(db, name: str) -> tuple[KnowledgePoint, bool]:
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.name == name).first()
    if kp:
        return kp, False
    kp = KnowledgePoint(subject="离散数学", name=name, description="测试用", difficulty="hard")
    db.add(kp)
    db.commit()
    db.refresh(kp)
    return kp, True


def make_questions(db, kp) -> list[Question]:
    rows = [
        Question(
            knowledge_point_id=kp.id, content=f"{Q_PREFIX}单选题？",
            question_type="single_choice", options='["甲","乙","丙","丁"]',
            answer="B", explanation="测试解析", difficulty="easy", source="ai",
        ),
        Question(
            knowledge_point_id=kp.id, content=f"{Q_PREFIX}多选题？",
            question_type="multiple_choice", options='["甲","乙","丙","丁"]',
            answer="AC", explanation="测试解析", difficulty="medium", source="ai",
        ),
        Question(
            knowledge_point_id=kp.id, content=f"{Q_PREFIX}判断题。",
            question_type="true_false", options=None,
            answer="正确", explanation="测试解析", difficulty="easy", source="ai",
        ),
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def make_answers(db, user: User, rows: list[Question]) -> list[Answer]:
    """写入真实答题记录，供学情报告的数据库交叉校验使用."""
    answers = [
        Answer(user_id=user.id, question_id=rows[0].id, user_answer="B",
               is_correct=True, score=1.0),
        Answer(user_id=user.id, question_id=rows[1].id, user_answer="AC",
               is_correct=False, score=0.5),
        Answer(user_id=user.id, question_id=rows[2].id, user_answer="正确",
               is_correct=True, score=1.0),
    ]
    db.add_all(answers)
    db.commit()
    for row in answers:
        db.refresh(row)
    return answers


def make_plan(db, user: User, kp) -> StudyPlan:
    plan = StudyPlan(
        user_id=user.id, title=f"{PLAN_PREFIX}两天计划", subject="离散数学",
        exam_date=date.today() + timedelta(days=3), daily_minutes=60,
        status="active", adjustment_log=json.dumps({"source": "test"}, ensure_ascii=False),
    )
    db.add(plan)
    db.flush()
    for i in range(4):
        db.add(StudyTask(
            plan_id=plan.id, knowledge_point_id=kp.id,
            title=f"{PLAN_PREFIX}任务{i}", description="测试",
            estimated_minutes=30, completed=False,
            scheduled_date=date.today() + timedelta(days=i // 2),
        ))
    db.commit()
    db.refresh(plan)
    return plan


def question_payload(rows: list[Question], requested: int) -> dict:
    """构造与练习生成 Agent 对齐的结果结构（不传明细，走数据库补齐路径）."""
    return {
        "agent": "question_generation",
        "created": True,
        "count_met": True,
        "requested_count": requested,
        "actual_count": len(rows),
        "question_ids": [r.id for r in rows],
    }


def plan_payload(plan: StudyPlan) -> dict:
    day1 = date.today()
    day2 = day1 + timedelta(days=1)
    return {
        "agent": "study_planning",
        "created": True,
        "plan_id": plan.id,
        "title": plan.title,
        "subject": plan.subject,
        "exam_date": plan.exam_date.isoformat(),
        "daily_minutes": plan.daily_minutes,
        "days": 2,
        "task_count": 4,
        "daily_summary": {
            day1.isoformat(): {"new": 60, "existing": 0, "total": 60, "limit": 60},
            day2.isoformat(): {"new": 60, "existing": 0, "total": 60, "limit": 60},
        },
    }


class StubLLMAgent(ResultValidationAgent):
    """注入 LLM 评分器，避免真实调用；记录调用次数."""

    def __init__(self, score: float, feedback: str = ""):
        super().__init__()
        self._score = score
        self._feedback = feedback
        self.calls = 0

    def _llm_review(self, target, payload, requirement):
        self.calls += 1
        return self._score, self._feedback


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

    def failed_names(out: dict) -> set[str]:
        return {c["name"] for c in out.get("checks", []) if not c["passed"]}

    init_db()
    db = SessionLocal()

    # 预清理：仅删除本测试标记的残留题目/计划
    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(
        synchronize_session=False
    )
    stale_plans = [
        p.id for p in db.query(StudyPlan).filter(StudyPlan.title.like(f"{PLAN_PREFIX}%")).all()
    ]
    if stale_plans:
        db.query(StudyTask).filter(StudyTask.plan_id.in_(stale_plans)).delete(
            synchronize_session=False
        )
        db.query(StudyPlan).filter(StudyPlan.id.in_(stale_plans)).delete(
            synchronize_session=False
        )
    db.commit()

    user_a = get_or_create_user(db, "rv_test_a", "rv_a@test.com")
    user_b = get_or_create_user(db, "rv_test_b", "rv_b@test.com")
    kp, kp_created = ensure_kp(db, "RV验证知识点")
    questions = make_questions(db, kp)
    plan = make_plan(db, user_a, kp)

    ctx = AgentContext(user_id=user_a.id, username=user_a.username, db=db)
    agent = ResultValidationAgent()

    async def run(payload, **data):
        task = AgentTask(
            task_id=str(uuid.uuid4()), user_id=user_a.id,
            task_type="result_validation",
            input_data={"payload": payload, **data},
        )
        res = await agent.run(task, ctx)
        return res, (res.result or {}), task

    # ---------- 1. 题目集合：合法结果 ----------
    res1, out1, _ = await run(question_payload(questions, 3))
    check("题目-执行成功", res1.success and out1.get("passed") is True,
          f"({out1.get('message')})")
    check("题目-target 自动推断", out1.get("target") == "question_set",
          f"({out1.get('target')})")
    check("题目-触发落库比对", out1.get("db_checked") is True)
    check("题目-全部通过", out1.get("failed_count") == 0 and out1.get("score") == 1.0,
          f"(score={out1.get('score')})")
    check("题目-检查项覆盖数量与去重",
          {"数量达标", "题干去重", "答案合法性", "落库记录完整"} <= {c["name"] for c in out1["checks"]})

    # ---------- 2. 数量不足 ----------
    _, out2, _ = await run(question_payload(questions, 5))
    check("数量不足-校验不通过", out2.get("passed") is False)
    check("数量不足-关键项命中", "数量达标" in out2.get("critical_failed", []),
          f"({out2.get('critical_failed')})")
    check("数量不足-说明期望与实际", "期望 5 道" in out2.get("reason", ""),
          f"({out2.get('reason')})")
    check("数量不足-给出修正建议", any("数量" in s for s in out2.get("suggestions", [])),
          f"({out2.get('suggestions')})")

    # ---------- 3. 字段/格式非法 ----------
    bad_items = [
        {"content": f"{Q_PREFIX}正常题？", "question_type": "single_choice",
         "options": ["甲", "乙", "丙", "丁"], "answer": "A",
         "explanation": "解析", "difficulty": "easy"},
        {"content": f"{Q_PREFIX}正常题？", "question_type": "single_choice",
         "options": ["甲", "乙", "丙", "丁"], "answer": "A",
         "explanation": "", "difficulty": "very_hard"},
        {"content": f"{Q_PREFIX}多选单答案？", "question_type": "multiple_choice",
         "options": ["甲", "乙"], "answer": "A", "explanation": "解析", "difficulty": "easy"},
        {"content": "短", "question_type": "unknown_type", "answer": "",
         "explanation": "", "difficulty": "easy"},
    ]
    _, out3, _ = await run({"questions": bad_items, "requested_count": 4})
    names3 = failed_names(out3)
    check("非法内容-整体不通过", out3.get("passed") is False)
    check("非法内容-命中解析缺失", "解析完整性" in names3, f"({names3})")
    check("非法内容-命中答案非法", "答案合法性" in names3)
    check("非法内容-命中题型非法", "题型合法性" in names3)
    check("非法内容-命中重复题干", "题干去重" in names3)
    check("非法内容-难度非法仅告警",
          "难度合法性" in names3 and "难度合法性" not in out3.get("critical_failed", []))
    check("非法内容-建议非空", len(out3.get("suggestions", [])) >= 3,
          f"({out3.get('suggestions')})")

    # ---------- 4. 落库记录缺失 ----------
    ghost = question_payload(questions, 3)
    ghost["question_ids"] = [r.id for r in questions] + [99999999]
    _, out4, _ = await run(ghost)
    check("落库缺失-识别缺口",
          {"落库记录完整", "落库数量一致"} <= failed_names(out4), f"({failed_names(out4)})")
    check("落库缺失-整体不通过", out4.get("passed") is False)

    # ---------- 5. 学习计划：合法 ----------
    _, out5, _ = await run(plan_payload(plan))
    check("计划-执行通过", out5.get("passed") is True, f"({out5.get('message')})")
    check("计划-target 自动推断", out5.get("target") == "study_plan",
          f"({out5.get('target')})")
    check("计划-落库校验生效", out5.get("db_checked") is True and out5.get("failed_count") == 0,
          f"({out5.get('issues')})")

    # ---------- 6. 学习计划：每日超限 ----------
    over = plan_payload(plan)
    today_key = date.today().isoformat()
    over["daily_summary"][today_key]["total"] = 90
    _, out6, _ = await run(over)
    check("计划超限-不通过", out6.get("passed") is False)
    check("计划超限-命中每日时长", "每日时长不超限" in failed_names(out6),
          f"({failed_names(out6)})")
    check("计划超限-说明超限明细", "90>60" in out6.get("reason", ""),
          f"({out6.get('reason')})")

    # ---------- 7. 学习计划：缺少必要字段 ----------
    _, out7, _ = await run({"plan_id": None, "title": "", "task_count": 0}, target="plan")
    check("计划缺字段-不通过", out7.get("passed") is False)
    check("计划缺字段-命中必填与任务",
          {"必填字段完整", "任务非空"} <= failed_names(out7), f"({failed_names(out7)})")
    check("计划缺字段-别名识别", out7.get("target") == "study_plan",
          f"({out7.get('target')})")

    # ---------- 8. 学习计划：归属不一致 ----------
    ctx_b = AgentContext(user_id=user_b.id, username=user_b.username, db=db)
    task8 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_b.id,
                      task_type="result_validation",
                      input_data={"payload": plan_payload(plan)})
    res8 = await agent.run(task8, ctx_b)
    out8 = res8.result or {}
    check("归属-识别不一致", res8.success and "归属正确" in failed_names(out8),
          f"({failed_names(out8)})")
    check("归属-整体不通过", out8.get("passed") is False)

    # ---------- 9. 学情分析：数据不足如实标注 ----------
    _, out9, _ = await run({
        "agent": "learning_analysis", "sufficient": False,
        "missing": ["答题/练习记录"], "report": {},
    })
    check("学情不足-不算失败", out9.get("passed") is True, f"({out9.get('issues')})")
    check("学情不足-检查标注项", "数据不足已标注" in {c["name"] for c in out9["checks"]})

    # ---------- 10. 学情分析：结构完整 + 与数据库真实数据交叉校验 ----------
    answers = make_answers(db, user_a, questions)
    real_task_total = db.query(StudyTask).filter(StudyTask.plan_id == plan.id).count()
    report = {
        "overview": {"total_study_minutes": 120, "total_questions": len(answers),
                     "task_total": real_task_total, "task_completed": 1},
        "mastery": {"图论": 0.6}, "weak_points": ["图论"], "strong_points": [],
    }
    _, out10a, _ = await run({
        "agent": "learning_analysis", "sufficient": True, "summary": "整体正常",
        "report": report,
    })
    check("学情完整-通过", out10a.get("passed") is True, f"({out10a.get('issues')})")
    check("学情-触发数据库交叉校验", out10a.get("db_checked") is True)
    check("学情-真实数据依据成立",
          "真实数据依据" in {c["name"] for c in out10a["checks"]}
          and "真实数据依据" not in failed_names(out10a))

    report["overview"]["total_questions"] = -1
    _, out10b, _ = await run({
        "agent": "learning_analysis", "sufficient": True, "summary": "整体正常",
        "report": report,
    })
    check("学情负数-仅告警不改结论",
          out10b.get("passed") is True and "数值合法性" in failed_names(out10b),
          f"({failed_names(out10b)})")

    # 夸大统计：报告声称的答题数远超数据库真实值 → 关键项拦截
    report["overview"]["total_questions"] = len(answers) + 100
    _, out10c, _ = await run({
        "agent": "learning_analysis", "sufficient": True, "summary": "整体正常",
        "report": report,
    })
    check("学情夸大答题数-被拦截",
          out10c.get("passed") is False
          and "结论不超出真实数据" in failed_names(out10c),
          f"({failed_names(out10c)})")

    # 夸大任务数：报告声称的任务数超过数据库真实值 → 关键项拦截
    report["overview"]["total_questions"] = len(answers)
    report["overview"]["task_total"] = real_task_total + 10
    _, out10d, _ = await run({
        "agent": "learning_analysis", "sufficient": True, "summary": "整体正常",
        "report": report,
    })
    check("学情夸大任务数-被拦截",
          out10d.get("passed") is False
          and "任务数与真实数据一致" in failed_names(out10d),
          f"({failed_names(out10d)})")

    # ---------- 11. 知识检索 ----------
    _, out11a, _ = await run({
        "agent": "knowledge_retrieval", "found": False, "results": [],
        "summary": "未检索到相关知识",
    })
    check("检索未命中-通过", out11a.get("passed") is True, f"({out11a.get('issues')})")

    _, out11b, _ = await run({
        "agent": "knowledge_retrieval", "found": True, "results": [], "count": 0,
    })
    check("检索空结果-不通过",
          out11b.get("passed") is False and "命中结果非空" in failed_names(out11b),
          f"({failed_names(out11b)})")

    # ---------- 12. 通用字段校验 ----------
    _, out12a, _ = await run({"a": 1, "b": {"c": 2}},
                             target="generic", required_fields=["a", "b.c"])
    check("通用-字段齐全通过", out12a.get("passed") is True, f"({out12a.get('issues')})")

    _, out12b, _ = await run({"a": 1}, target="generic", required_fields=["a", "b.c"])
    check("通用-缺字段不通过",
          out12b.get("passed") is False and "b.c" in out12b.get("reason", ""),
          f"({out12b.get('reason')})")

    # ---------- 13. 从 context.shared 取结果 ----------
    shared_ctx = AgentContext(
        user_id=user_a.id, username=user_a.username, db=db,
        shared={"question_generation": question_payload(questions, 3)},
    )
    task13 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                       task_type="result_validation",
                       input_data={"shared_key": "question_generation"})
    res13 = await agent.run(task13, shared_ctx)
    out13 = res13.result or {}
    check("共享结果-可取到", res13.success and out13.get("passed") is True,
          f"({out13.get('message')})")
    check("共享结果-target 推断", out13.get("target") == "question_set")

    # ---------- 14. 空 payload：不抛异常 ----------
    res14, out14, _ = await run(None)
    check("空结果-执行不崩溃", res14.success and res14.result is not None)
    check("空结果-判定不通过",
          out14.get("passed") is False and "结果存在性" in failed_names(out14),
          f"({out14.get('issues')})")

    # ---------- 15. LLM 辅助 ----------
    stub_low = StubLLMAgent(0.2, "内容偏浅")
    task15 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                       task_type="result_validation",
                       input_data={"payload": question_payload(questions, 3),
                                   "use_llm": True, "goal": "出 3 道图论题"})
    res15 = await stub_low.run(task15, ctx)
    out15 = res15.result or {}
    check("LLM-低分否决", out15.get("passed") is False and out15.get("llm_score") == 0.2,
          f"({out15.get('llm_score')}, {out15.get('passed')})")
    check("LLM-记录反馈", out15.get("llm_feedback") == "内容偏浅")
    check("LLM-检查项非关键",
          "需求契合度（LLM）" not in out15.get("critical_failed", []),
          f"({out15.get('critical_failed')})")

    stub_high = StubLLMAgent(0.9)
    task16 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                       task_type="result_validation",
                       input_data={"payload": question_payload(questions, 3), "use_llm": True})
    res16 = await stub_high.run(task16, ctx)
    out16 = res16.result or {}
    check("LLM-高分通过", out16.get("passed") is True and out16.get("llm_score") == 0.9,
          f"({out16.get('llm_score')}, {out16.get('passed')})")

    stub_off = StubLLMAgent(0.1)
    task17 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                       task_type="result_validation",
                       input_data={"payload": question_payload(questions, 3)})
    res17 = await stub_off.run(task17, ctx)
    check("LLM-默认不调用", stub_off.calls == 0 and (res17.result or {}).get("llm_score") is None,
          f"(calls={stub_off.calls})")

    # ---------- 16. 用户隔离 ----------
    task18 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_b.id,
                       task_type="result_validation",
                       input_data={"payload": question_payload(questions, 3)})
    res18 = await agent.run(task18, ctx)
    check("隔离-用户不一致被拒",
          (not res18.success) and "不一致" in (res18.error or ""), f"({res18.error})")

    # ---------- 17. 只读性：不改变数据库 ----------
    q_before = db.query(Question).count()
    p_before = db.query(StudyPlan).count()
    t_before = db.query(StudyTask).count()
    await run(question_payload(questions, 3))
    await run(plan_payload(plan))
    await run({"agent": "learning_analysis", "sufficient": False, "missing": ["x"]})
    check("只读-题目数量不变", db.query(Question).count() == q_before)
    check("只读-计划数量不变", db.query(StudyPlan).count() == p_before)
    check("只读-任务数量不变", db.query(StudyTask).count() == t_before)

    # ---------- 18. 任务状态与耗时 ----------
    check("执行-状态为成功", (await run(plan_payload(plan)))[2].status == AgentStatus.SUCCESS)
    check("执行-耗时记录", res1.execution_time >= 0)

    # ---------- 清理：仅删除本次创建的题目/答题/计划/知识点 ----------
    if answers:
        db.query(Answer).filter(Answer.id.in_([a.id for a in answers])).delete(
            synchronize_session=False
        )
    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(
        synchronize_session=False
    )
    db.query(StudyTask).filter(StudyTask.plan_id == plan.id).delete(synchronize_session=False)
    db.query(StudyPlan).filter(StudyPlan.id == plan.id).delete(synchronize_session=False)
    if kp_created:
        db.delete(kp)
    db.commit()

    leftover_q = db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).count()
    leftover_p = db.query(StudyPlan).filter(StudyPlan.title.like(f"{PLAN_PREFIX}%")).count()
    check("清理-无测试数据残留", leftover_q == 0 and leftover_p == 0,
          f"(题目 {leftover_q}，计划 {leftover_p})")

    print(f"\n清理结果: 测试题目 {len(questions)} 条、测试计划 1 条已删除，"
          f"测试知识点{'已删除' if kp_created else '复用未删'}")
    db.close()

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
