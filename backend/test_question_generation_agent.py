"""第六阶段测试：练习生成 Agent.

覆盖：
- 正常生成指定数量（含单选/多选/判断/简答）
- 首次不足 → 仅按缺口补充生成
- 补充时已生成题干回传模型，去重不占用有效数量
- 模型调用失败 → 优雅处理并如实报告
- 达到最大重试次数 → 准确报告实际数量，不伪装成功
- 字段不完整 → 拦截，不落库
- 落库后现有练习读取链路（_to_out）与多选批改正常
- 用户数据隔离
- 原有题库/批改逻辑不受影响

测试数据标识：题目内容统一以「【测试】QG」开头，清理仅针对本次创建的题目 id 与该前缀。
测试用脚本化生成器注入，不消耗 DeepSeek 额度；真实调用仍走 LLMService。

用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_question_generation_agent.py
"""
import asyncio
import json
import sys
import uuid
from datetime import date
from unittest.mock import patch

import app.main  # noqa: F401  确认应用可正常构建
from app.agents.core import AgentContext, AgentStatus, AgentTask
from app.agents.question_generation_agent import QuestionGenerationAgent
from app.api.questions import _to_out
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import (
    Answer,
    KnowledgePoint,
    LearningProfile,
    LearningRecord,
    Question,
    User,
    WrongQuestion,
)
from app.services.llm_service import llm_service
from app.services.question_service import BANK, QuestionService

Q_PREFIX = "【测试】QG"


def q(content, qtype="single_choice", options=None, answer="A", difficulty="medium"):
    # 选择型题目默认给 4 个选项，避免测试数据自身不合法
    if options is None and qtype in ("single_choice", "multiple_choice"):
        options = ["甲", "乙", "丙", "丁"]
    return {
        "content": content,
        "question_type": qtype,
        "options": options,
        "answer": answer,
        "explanation": "【测试】解析",
        "difficulty": difficulty,
    }


class ScriptedAgent(QuestionGenerationAgent):
    """脚本化生成器：按预设批次返回，记录每次收到的已生成题干."""

    def __init__(self, batches):
        super().__init__()
        self._batches = list(batches)
        self._calls = 0
        self.received_existing: list[list[str]] = []
        self.received_counts: list[int] = []
        self.received_types: list[list[str]] = []

    def _request_batch(self, kp, difficulty, types, count,
                       existing_contents, context_text):
        self.received_existing.append(list(existing_contents))
        self.received_counts.append(count)
        self.received_types.append(list(types))
        if self._calls < len(self._batches):
            batch = self._batches[self._calls]
            self._calls += 1
            return batch
        return None


# ==================== 测试数据工具 ====================

def get_or_create_user(db, username: str, email: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, email=email, password_hash=hash_password("test1234"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


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


def seed_learning(db, user: User, kp: KnowledgePoint) -> None:
    questions = [
        Question(
            knowledge_point_id=kp.id, content=f"{Q_PREFIX}学情题{i}",
            question_type="single_choice", options='["A","B"]', answer="A",
            explanation="测试", difficulty="easy", source="bank",
        )
        for i in range(2)
    ]
    db.add_all(questions)
    db.commit()
    for qq in questions:
        db.refresh(qq)

    answers = [
        Answer(user_id=user.id, question_id=questions[i % 2].id,
               user_answer="A" if c else "B", is_correct=c, score=1.0 if c else 0.0)
        for i, c in enumerate([True, True, False])
    ]
    db.add_all(answers)
    db.commit()
    for a in answers:
        db.refresh(a)

    db.add(WrongQuestion(
        user_id=user.id, question_id=answers[2].question_id,
        reason="测试", suggestion="测试", mastered=False, review_count=0,
    ))
    db.add(LearningProfile(
        user_id=user.id, knowledge_point_id=kp.id, mastery_score=0.3, confidence=5,
    ))
    db.add(LearningRecord(
        user_id=user.id, knowledge_point_id=kp.id, study_minutes=60,
        mastery_score=0.3, source="practice",
    ))
    db.commit()


def db_questions(db, ids: list[int]) -> list[Question]:
    if not ids:
        return []
    return db.query(Question).filter(Question.id.in_(ids)).all()


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

    # 预清理：仅删除本测试前缀的残留题目
    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(
        synchronize_session=False
    )
    db.commit()

    user_a = get_or_create_user(db, "qg_test_a", "qg_a@test.com")
    user_b = get_or_create_user(db, "qg_test_b", "qg_b@test.com")
    clear_user_learning(db, user_a)
    clear_user_learning(db, user_b)

    kp, kp_created = ensure_kp(db, "图论")
    kp_set, kp_set_created = ensure_kp(db, "集合")
    kp_fb, kp_fb_created = ensure_kp(db, "RV兜底知识点")
    seed_learning(db, user_a, kp)

    created_ids: list[int] = []
    ctx = AgentContext(user_id=user_a.id, username=user_a.username, db=db)

    # ---------- 1. 正常生成 5 道（含 4 种题型）----------
    batch1 = [
        q(f"{Q_PREFIX}单选题一？", "single_choice", ["甲", "乙", "丙", "丁"], "A"),
        q(f"{Q_PREFIX}单选题二？", "single_choice", ["甲", "乙", "丙", "丁"], "B"),
        q(f"{Q_PREFIX}多选题一？", "multiple_choice", ["甲", "乙", "丙", "丁"], "AC"),
        q(f"{Q_PREFIX}判断题一。", "true_false", None, "正确"),
        q(f"{Q_PREFIX}简答题一？", "short_answer", None, "删除后连通分量增加的顶点"),
    ]
    agent1 = ScriptedAgent([batch1])
    task1 = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user_a.id,
        task_type="question_generation", input_data={"count": 5},
    )
    res1 = await agent1.run(task1, ctx)
    out1 = res1.result or {}
    created_ids += out1.get("question_ids", [])

    check("正常-执行成功", res1.success and task1.status == AgentStatus.SUCCESS)
    check("正常-数量达标", out1.get("created") is True and out1.get("count_met") is True)
    check("正常-实际数量=5", out1.get("actual_count") == 5, f"({out1.get('actual_count')})")
    check("正常-优先薄弱知识点", (out1.get("knowledge_point") or {}).get("name") == "图论",
          f"({out1.get('knowledge_point')})")
    check("正常-难度随掌握度=简单", out1.get("difficulty") == "easy",
          f"({out1.get('difficulty')})")

    persisted1 = db_questions(db, out1.get("question_ids", []))
    types1 = {x.question_type for x in persisted1}
    check("正常-四种题型齐全",
          {"single_choice", "multiple_choice", "true_false", "short_answer"} <= types1,
          f"({types1})")
    check("正常-解析完整", all((x.explanation or "").strip() for x in persisted1))
    multi = next((x for x in persisted1 if x.question_type == "multiple_choice"), None)
    opts = json.loads(multi.options) if multi and multi.options else []
    check("正常-多选选项与答案",
          multi is not None and len(opts) == 4 and multi.answer == "AC",
          f"(answer={multi.answer if multi else None})")
    check("正常-来源标记 ai", all(x.source == "ai" for x in persisted1))

    # ---------- 2. 首次不足 → 补充生成 ----------
    agent2 = ScriptedAgent([
        [q(f"{Q_PREFIX}补充题1？"), q(f"{Q_PREFIX}补充题2？")],
        [q(f"{Q_PREFIX}补充题3？"), q(f"{Q_PREFIX}补充题4？"), q(f"{Q_PREFIX}补充题5？")],
    ])
    task2 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                      task_type="question_generation", input_data={"count": 5})
    res2 = await agent2.run(task2, ctx)
    out2 = res2.result or {}
    created_ids += out2.get("question_ids", [])
    check("补充-数量达标", out2.get("count_met") is True and out2.get("actual_count") == 5)
    check("补充-分两轮完成", out2.get("attempts") == 2, f"({out2.get('attempts')})")
    check("补充-第二次只请求缺口", agent2.received_counts[1] == 3,
          f"(counts={agent2.received_counts})")
    check("补充-已生成题干回传",
          agent2.received_existing[1] == [f"{Q_PREFIX}补充题1？", f"{Q_PREFIX}补充题2？"],
          f"({agent2.received_existing[1]})")

    # ---------- 3. 去重：重复题不占有效数量 ----------
    agent3 = ScriptedAgent([
        [q(f"{Q_PREFIX}去重题1？"), q(f"{Q_PREFIX}去重题2？")],
        [q(f"{Q_PREFIX}去重题1？"), q(f"{Q_PREFIX}去重题3？"),
         q(f"{Q_PREFIX}去重题4？"), q(f"{Q_PREFIX}去重题5？")],
    ])
    task3 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                      task_type="question_generation", input_data={"count": 5})
    res3 = await agent3.run(task3, ctx)
    out3 = res3.result or {}
    created_ids += out3.get("question_ids", [])
    check("去重-数量达标", out3.get("count_met") is True and out3.get("actual_count") == 5)
    contents3 = [x.content for x in db_questions(db, out3.get("question_ids", []))]
    check("去重-无重复题干", len(contents3) == len(set(contents3)),
          f"(unique={len(set(contents3))}/{len(contents3)})")

    # ---------- 4. 模型调用失败 + 题库也无可用题（兜底置空）----------
    agent4 = ScriptedAgent([])   # 始终返回 None
    task4 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                      task_type="question_generation", input_data={"count": 3})
    with patch.object(QuestionService, "bank_fallback_items", return_value=[]):
        res4 = await agent4.run(task4, ctx)
    out4 = res4.result or {}
    check("失败-优雅处理（执行成功）", res4.success and task4.status == AgentStatus.SUCCESS)
    check("失败-未创建", out4.get("created") is False and out4.get("actual_count") == 0)
    check("失败-状态为 failed", out4.get("status") == "failed", f"({out4.get('status')})")
    check("失败-原因含模型调用", "模型调用失败" in (out4.get("reason") or ""),
          f"({out4.get('reason')})")

    # ---------- 5. 达到最大重试 → 准确报告实际数量 ----------
    agent5 = ScriptedAgent([
        [q(f"{Q_PREFIX}重试题1？")],
        [q(f"{Q_PREFIX}重试题2？")],
        [q(f"{Q_PREFIX}重试题3？")],
    ])
    task5 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                      task_type="question_generation", input_data={"count": 5})
    with patch.object(QuestionService, "bank_fallback_items", return_value=[]):
        res5 = await agent5.run(task5, ctx)
    out5 = res5.result or {}
    created_ids += out5.get("question_ids", [])
    check("重试-达到上限", out5.get("attempts") == 3, f"({out5.get('attempts')})")
    check("重试-如实报告 3/5",
          out5.get("actual_count") == 3 and out5.get("requested_count") == 5
          and out5.get("count_met") is False,
          f"({out5.get('actual_count')}/{out5.get('requested_count')})")
    check("重试-提示最大补充次数", "最大补充次数" in (out5.get("reason") or ""),
          f"({out5.get('reason')})")
    check("重试-标记部分成功",
          out5.get("status") == "partial" and out5.get("created") is True,
          f"({out5.get('status')})")
    check("重试-保存已生成的有效题目", len(out5.get("question_ids") or []) == 3,
          f"({len(out5.get('question_ids') or [])})")

    # ---------- 6. 字段不完整 → 拦截 ----------
    agent6 = ScriptedAgent([[
        {"content": "短", "question_type": "single_choice", "options": ["A", "B"],
         "answer": "A", "explanation": "x", "difficulty": "easy"},
        {"content": f"{Q_PREFIX}无解析题？", "question_type": "single_choice",
         "options": ["A", "B", "C", "D"], "answer": "A", "explanation": "", "difficulty": "easy"},
        {"content": f"{Q_PREFIX}错答案题？", "question_type": "single_choice",
         "options": ["A", "B", "C", "D"], "answer": "Z", "explanation": "x", "difficulty": "easy"},
        {"content": f"{Q_PREFIX}多选单答案？", "question_type": "multiple_choice",
         "options": ["A", "B", "C", "D"], "answer": "A", "explanation": "x", "difficulty": "easy"},
        {"content": f"{Q_PREFIX}判断非法？", "question_type": "true_false",
         "options": None, "answer": "maybe", "explanation": "x", "difficulty": "easy"},
    ]])
    task6 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                      task_type="question_generation", input_data={"count": 2})
    with patch.object(QuestionService, "bank_fallback_items", return_value=[]):
        res6 = await agent6.run(task6, ctx)
    out6 = res6.result or {}
    check("拦截-未创建", out6.get("created") is False and out6.get("actual_count") == 0)
    check("拦截-全部被拒", out6.get("rejected_count", 0) >= 4,
          f"(rejected={out6.get('rejected_count')})")
    check("拦截-无落库", (out6.get("question_ids") or []) == [])

    # ---------- 7. 落库后可被现有练习读取 + 多选批改 ----------
    stored = db_questions(db, [multi.id]) if multi else []
    check("读取-多选可查询", bool(stored))
    if stored:
        out_dto = _to_out(stored[0])
        check("读取-_to_out 正常",
              out_dto.question_type == "multiple_choice"
              and isinstance(out_dto.options, list) and len(out_dto.options) == 4,
              f"({out_dto.question_type}, {out_dto.options})")

    if multi:
        service = QuestionService(db)
        check("批改-多选顺序无关", service.grade(multi, "CA")[0] is True)
        check("批改-多选少选判错", service.grade(multi, "A")[0] is False)
    single = next((x for x in persisted1 if x.question_type == "single_choice"), None)
    if single:
        check("批改-单选仍正常", QuestionService(db).grade(single, single.answer)[0] is True)

    # ---------- 8. 用户隔离 ----------
    task8 = AgentTask(task_id=str(uuid.uuid4()), user_id=user_b.id,
                      task_type="question_generation", input_data={"count": 2})
    ctx_b = AgentContext(user_id=user_a.id, username=user_a.username, db=db)
    res8 = await ScriptedAgent([batch1]).run(task8, ctx_b)
    check("隔离-用户不一致被拒",
          (not res8.success) and "不一致" in (res8.error or ""), f"({res8.error})")

    # ---------- 9. 原有题库/批改不受影响 ----------
    check("原有-内置题库可用", len(BANK) > 0)
    bank_qs = QuestionService(db)._generate_from_bank(kp, 2)
    check("原有-题库降级生成", len(bank_qs) == 2 and all(x.source == "bank" for x in bank_qs))
    # 简答题批改默认会调用 LLM；此处临时置为不可用以避免额度消耗，验证降级关键词评分
    old_flag = llm_service._available
    llm_service._available = False
    try:
        fake_single = Question(knowledge_point_id=kp.id, content="测试", question_type="single_choice",
                               options='["A","B"]', answer="A", explanation="e",
                               difficulty="easy", source="bank")
        fake_tf = Question(knowledge_point_id=kp.id, content="测试", question_type="true_false",
                           options=None, answer="正确", explanation="e",
                           difficulty="easy", source="bank")
        fake_short = Question(knowledge_point_id=kp.id, content="测试", question_type="short_answer",
                              options=None, answer="割点 连通 分量", explanation="e",
                              difficulty="easy", source="bank")
        svc = QuestionService(db)
        check("原有-单选批改", svc.grade(fake_single, "A")[0] is True)
        check("原有-判断批改", svc.grade(fake_tf, "正确")[0] is True)
        check("原有-简答关键词批改", svc.grade(fake_short, "割点 连通 分量 删除")[0] is True)
    finally:
        llm_service._available = old_flag

    # ---------- 9. LLM 失败 → 复用 QuestionService 题库兜底 ----------
    agent_fb = ScriptedAgent([])          # 模型始终失败
    task_fb = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user_a.id,
        task_type="question_generation",
        input_data={"count": 5, "knowledge_point": kp_fb.name},
    )
    res_fb = await agent_fb.run(task_fb, ctx)
    out_fb = res_fb.result or {}
    created_ids += out_fb.get("question_ids", [])
    fb_rows = db_questions(db, out_fb.get("question_ids", []))
    check("兜底-数量达标",
          out_fb.get("status") == "success" and out_fb.get("actual_count") == 5,
          f"({out_fb.get('status')}, {out_fb.get('actual_count')})")
    check("兜底-标记题库来源",
          out_fb.get("fallback_used") is True and out_fb.get("fallback_count") == 5,
          f"(fallback={out_fb.get('fallback_count')})")
    check("兜底-全部来自题库",
          bool(fb_rows) and all(x.source == "bank" for x in fb_rows),
          f"({[x.source for x in fb_rows]})")
    check("兜底-无重复题干", len({x.content for x in fb_rows}) == len(fb_rows))

    # 再跑一次：兜底不得产生重复数据库记录
    res_fb2 = await ScriptedAgent([]).run(
        AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                  task_type="question_generation",
                  input_data={"count": 5, "knowledge_point": kp_fb.name}),
        ctx,
    )
    out_fb2 = res_fb2.result or {}
    created_ids += out_fb2.get("question_ids", [])
    fb2_contents = {x.content for x in db_questions(db, out_fb2.get("question_ids", []))}
    check("兜底-不与已有题目重复",
          bool(fb2_contents) and not (fb2_contents & {x.content for x in fb_rows}),
          f"(overlap={len(fb2_contents & {x.content for x in fb_rows})})")

    # 同类型题库不足 → 如实返回 partial
    res_fb3 = await ScriptedAgent([]).run(
        AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                  task_type="question_generation",
                  input_data={"count": 3, "knowledge_point": kp_fb.name,
                              "question_types": ["short_answer"]}),
        ctx,
    )
    out_fb3 = res_fb3.result or {}
    created_ids += out_fb3.get("question_ids", [])
    fb3_saved = len(out_fb3.get("question_ids") or [])
    check("兜底不足-返回 partial",
          out_fb3.get("status") == "partial" and out_fb3.get("count_met") is False,
          f"({out_fb3.get('status')})")
    check("兜底不足-如实数量",
          0 < fb3_saved < 3 and out_fb3.get("actual_count") == fb3_saved,
          f"({fb3_saved}/3)")
    check("兜底不足-说明原因", "不足" in (out_fb3.get("reason") or ""),
          f"({out_fb3.get('reason')})")

    # ---------- 9.1 题库多选题样本完整性 ----------
    multi_entries = [q for q in BANK if q["type"] == "multiple_choice"]
    check("题库-含多选题样本", len(multi_entries) >= 6, f"({len(multi_entries)})")
    validator = QuestionGenerationAgent()
    invalid_bank = [
        q["content"] for q in BANK if validator._validate_and_normalize(q) is None
    ]
    check("题库-全部通过格式校验", not invalid_bank, f"({invalid_bank[:2]})")
    check("题库-多选题均为多答案",
          all(len(set(q["answer"])) >= 2 for q in multi_entries),
          f"({[q['answer'] for q in multi_entries]})")
    check("题库-多选题选项完整",
          all(isinstance(q["options"], list) and len(q["options"]) == 4
              for q in multi_entries))

    # 多选题兜底
    res_multi = await ScriptedAgent([]).run(
        AgentTask(task_id=str(uuid.uuid4()), user_id=user_a.id,
                  task_type="question_generation",
                  input_data={"count": 3, "knowledge_point": kp_fb.name,
                              "question_types": ["multiple_choice"]}),
        ctx,
    )
    out_multi = res_multi.result or {}
    created_ids += out_multi.get("question_ids", [])
    multi_rows = db_questions(db, out_multi.get("question_ids", []))
    check("兜底多选-数量达标",
          out_multi.get("status") == "success" and out_multi.get("actual_count") == 3,
          f"({out_multi.get('status')}, {out_multi.get('actual_count')})")
    check("兜底多选-题型均为多选",
          bool(multi_rows) and all(x.question_type == "multiple_choice" for x in multi_rows),
          f"({[x.question_type for x in multi_rows]})")

    # ---------- 10. 题型参数：只生成多选题 ----------
    agent_types = ScriptedAgent([
        [
            q(f"{Q_PREFIX}题型单选题？", "single_choice", ["甲", "乙", "丙", "丁"], "A"),
            q(f"{Q_PREFIX}题型多选甲？", "multiple_choice", ["甲", "乙", "丙", "丁"], "AC"),
            q(f"{Q_PREFIX}题型多选乙？", "multiple_choice", ["甲", "乙", "丙", "丁"], "BD"),
        ],
        [q(f"{Q_PREFIX}题型多选丙？", "multiple_choice", ["甲", "乙", "丙", "丁"], "AB")],
    ])
    task_types = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user_a.id,
        task_type="question_generation",
        input_data={"count": 3, "knowledge_point": "图论",
                    "question_types": ["multiple_choice"]},
    )
    res_types = await agent_types.run(task_types, ctx)
    out_types = res_types.result or {}
    created_ids += out_types.get("question_ids", [])
    types_saved = {
        x.question_type for x in db_questions(db, out_types.get("question_ids", []))
    }
    check("题型-只落库多选题", types_saved == {"multiple_choice"}, f"({types_saved})")
    check("题型-单选被过滤", out_types.get("invalid_count", 0) >= 1,
          f"(invalid={out_types.get('invalid_count')})")
    check("题型-缺口补足到 3",
          out_types.get("actual_count") == 3 and out_types.get("attempts") == 2,
          f"({out_types.get('actual_count')}, attempts={out_types.get('attempts')})")
    check("题型-已传递给模型",
          bool(agent_types.received_types)
          and all(t == ["multiple_choice"] for t in agent_types.received_types),
          f"({agent_types.received_types})")

    # ---------- 11. 中文题型 / 中文难度 ----------
    agent_cn = ScriptedAgent([[
        {"content": f"{Q_PREFIX}中文多选？", "question_type": "多选题",
         "options": ["甲", "乙", "丙", "丁"], "answer": "AC",
         "explanation": "解析", "difficulty": "困难"},
    ]])
    task_cn = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user_a.id,
        task_type="question_generation",
        input_data={"count": 1, "knowledge_point": "图论",
                    "difficulty": "困难", "question_types": "多选题"},
    )
    res_cn = await agent_cn.run(task_cn, ctx)
    out_cn = res_cn.result or {}
    created_ids += out_cn.get("question_ids", [])
    check("中文-难度归一化为 hard", out_cn.get("difficulty") == "hard",
          f"({out_cn.get('difficulty')})")
    check("中文-题型归一化为多选", out_cn.get("question_types") == ["multiple_choice"],
          f"({out_cn.get('question_types')})")
    check("中文-生成成功",
          out_cn.get("status") == "success" and out_cn.get("actual_count") == 1,
          f"({out_cn.get('status')})")

    # ---------- 12. 关闭「结合薄弱点」----------
    agent_no_weak = ScriptedAgent([[q(f"{Q_PREFIX}不结合弱项？")]])
    task_no_weak = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user_a.id,
        task_type="question_generation",
        input_data={"count": 1, "subject": "离散数学", "use_weak_points": False},
    )
    res_no_weak = await agent_no_weak.run(task_no_weak, ctx)
    out_no_weak = res_no_weak.result or {}
    created_ids += out_no_weak.get("question_ids", [])
    check("弱项-关闭时不优先薄弱点",
          (out_no_weak.get("knowledge_point") or {}).get("name") != "图论",
          f"({out_no_weak.get('knowledge_point')})")
    check("弱项-开关回传", out_no_weak.get("use_weak_points") is False)

    # ---------- 13. 数据库已有题目判重 ----------
    db_existing = Question(
        knowledge_point_id=kp.id, content=f"{Q_PREFIX}数据库已有题？",
        question_type="single_choice", options='["甲","乙","丙","丁"]',
        answer="A", explanation="测试", difficulty="easy", source="ai",
    )
    db.add(db_existing)
    db.commit()
    db.refresh(db_existing)
    created_ids.append(db_existing.id)

    agent_dbdup = ScriptedAgent([
        [q(f"{Q_PREFIX}数据库已有题？"), q(f"{Q_PREFIX}数据库新题1？")],
        [q(f"{Q_PREFIX}数据库新题2？")],
    ])
    task_dbdup = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user_a.id,
        task_type="question_generation",
        input_data={"count": 2, "knowledge_point": "图论"},
    )
    res_dbdup = await agent_dbdup.run(task_dbdup, ctx)
    out_dbdup = res_dbdup.result or {}
    created_ids += out_dbdup.get("question_ids", [])
    check("库判重-命中重复题目", out_dbdup.get("duplicate_count", 0) >= 1,
          f"(duplicate={out_dbdup.get('duplicate_count')})")
    check("库判重-数量仍达标", out_dbdup.get("actual_count") == 2,
          f"({out_dbdup.get('actual_count')})")
    saved_dbdup = [x.content for x in db_questions(db, out_dbdup.get("question_ids", []))]
    check("库判重-未重复保存已有题干",
          f"{Q_PREFIX}数据库已有题？" not in saved_dbdup, f"({saved_dbdup})")

    # ---------- 14. 输出字段完整性（Agent 统一规范）----------
    check("输出-状态字段", out1.get("status") == "success", f"({out1.get('status')})")
    check("输出-执行耗时",
          isinstance(out1.get("execution_time"), float) and out1["execution_time"] >= 0,
          f"({out1.get('execution_time')})")
    check("输出-执行日志",
          isinstance(out1.get("logs"), list) and len(out1["logs"]) >= 2,
          f"(logs={len(out1.get('logs') or [])})")
    check("输出-题目明细数量一致",
          len(out1.get("questions") or []) == out1.get("actual_count"),
          f"({len(out1.get('questions') or [])}/{out1.get('actual_count')})")
    first_q = (out1.get("questions") or [{}])[0]
    check("输出-明细含答案与解析",
          bool(first_q.get("answer")) and bool(first_q.get("explanation")))
    check("输出-用户要求数量与实际数量",
          out1.get("requested_count") == 5 and out1.get("actual_count") == 5)

    # ---------- 15. 统一注册表 ----------
    from app.agents.core import core_registry
    from app.agents.registration import register_core_agents

    names_1 = register_core_agents()
    names_2 = register_core_agents()
    check("注册表-包含练习生成", core_registry.get("question_generation") is not None)
    check("注册表-幂等", names_1 == names_2 and "question_generation" in names_1,
          f"({names_1})")
    registered = core_registry.require("question_generation")
    check("注册表-可按名调度", isinstance(registered, QuestionGenerationAgent))

    # ---------- 16. 参数非法 ----------
    bad_inputs = [
        ({"count": 0}, "数量"),
        ({"count": 3, "question_types": ["填空题"]}, "题型"),
        ({"count": 3, "difficulty": "超难"}, "难度"),
    ]
    for payload, label in bad_inputs:
        task_bad = AgentTask(
            task_id=str(uuid.uuid4()), user_id=user_a.id,
            task_type="question_generation",
            input_data={"knowledge_point": "图论", **payload},
        )
        res_bad = await ScriptedAgent([]).run(task_bad, ctx)
        out_bad = res_bad.result or {}
        check(f"参数-{label}非法被拒",
              out_bad.get("status") == "failed" and out_bad.get("actual_count") == 0,
              f"({out_bad.get('reason')})")

    # ---------- 17. 原有答题记录 / 错题集不受影响 ----------
    ans_before = db.query(Answer).filter(Answer.user_id == user_a.id).count()
    wrong_before = db.query(WrongQuestion).filter(WrongQuestion.user_id == user_a.id).count()
    agent_keep = ScriptedAgent([[q(f"{Q_PREFIX}不影响记录？")]])
    task_keep = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user_a.id,
        task_type="question_generation",
        input_data={"count": 1, "knowledge_point": "图论"},
    )
    res_keep = await agent_keep.run(task_keep, ctx)
    created_ids += (res_keep.result or {}).get("question_ids", [])
    check("原有-答题记录不变",
          db.query(Answer).filter(Answer.user_id == user_a.id).count() == ans_before,
          f"({ans_before})")
    check("原有-错题记录不变",
          db.query(WrongQuestion).filter(WrongQuestion.user_id == user_a.id).count() == wrong_before,
          f"({wrong_before})")

    # ---------- 清理：仅删除本次创建的题目 id + 测试前缀残留 + 测试学情 ----------
    db.query(Question).filter(Question.id.in_(created_ids)).delete(synchronize_session=False) if created_ids else None
    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(synchronize_session=False)
    clear_user_learning(db, user_a)
    clear_user_learning(db, user_b)
    if kp_created:
        db.delete(kp)
    if kp_set_created:
        db.delete(kp_set)
    if kp_fb_created:
        db.delete(kp_fb)
    db.commit()

    leftover = db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).count()
    check("清理-无测试题目残留", leftover == 0, f"(残留 {leftover})")

    print(f"\n清理结果: 本次生成题目 {len(created_ids)} 条，测试前缀残留 {leftover} 条，"
          f"测试知识点{'已删除' if kp_created else '复用未删'}")
    db.close()

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
