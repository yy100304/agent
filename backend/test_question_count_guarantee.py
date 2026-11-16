"""回归测试：练习生成「数量不达标」修复.

背景：`/api/questions/generate`（前端练习入口）走的是 QuestionService.generate，
原实现只向模型请求一次、整批 Pydantic 校验、题库只按本知识点抽题，
因此经常出现「要 5 道只给 3 道」。本脚本锁定修复后的几条保证：

- 单轮题量过大导致 JSON 截断/解析失败时，不再整批作废；
- 单条题目字段非法只丢弃该条，不拖累整批；
- 数量不足时按缺口继续请求（多轮补题）；
- 重复题干不占有效数量；
- 仍不足时按「本知识点 → 同学科 → 全库」用真实题库补齐；
- 题库也无更多不重复题目时如实返回实际数量，且绝不产生重复题干。

测试不消耗外部额度：llm_service.chat 由脚本注入。
测试数据标识：模型生成的题目题干以「【测试】QGC」开头，清理按本次返回的 id 精确删除。

用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_question_count_guarantee.py
"""
import json
import sys

import app.main  # noqa: F401  确认应用可正常构建
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import KnowledgePoint, Question, User
from app.services.llm_service import llm_service
from app.services.question_service import QuestionService

Q_PREFIX = "【测试】QGC"


# ==================== 测试工具 ====================

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


def item(content: str, qtype="single_choice", answer="A", options=None,
         difficulty="easy", explanation="测试解析") -> dict:
    if options is None and qtype in ("single_choice", "multiple_choice"):
        options = ["甲", "乙", "丙", "丁"]
    return {
        "content": content, "question_type": qtype, "options": options,
        "answer": answer, "explanation": explanation, "difficulty": difficulty,
    }


def batch(*items: dict) -> str:
    return json.dumps({"questions": list(items)}, ensure_ascii=False)


class StubChat:
    """按队列返回预设模型响应，并记录每次请求的提示词."""

    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.prompts: list[str] = []

    def __call__(self, messages, temperature=0.7, max_tokens=2000):
        self.prompts.append(messages[-1]["content"])
        if self.responses:
            return self.responses.pop(0)
        return None


def use_llm(stub: StubChat, available: bool = True) -> None:
    llm_service._available = available
    llm_service.chat = stub


def restore_llm(original_chat, original_available) -> None:
    llm_service.chat = original_chat
    llm_service._available = original_available


# ==================== 测试主体 ====================

def main() -> None:
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

    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(
        synchronize_session=False
    )
    db.commit()

    user = get_or_create_user(db, "qgc_test", "qgc@test.com")
    kp, kp_created = ensure_kp(db, "图论")
    service = QuestionService(db)
    created_ids: list[int] = []

    original_chat = llm_service.chat
    original_available = llm_service._available

    try:
        # ---------- 1. 首轮不足 → 按缺口补题 ----------
        stub = StubChat([
            batch(item(f"{Q_PREFIX}补齐1？"), item(f"{Q_PREFIX}补齐2？")),
            batch(item(f"{Q_PREFIX}补齐3？"), item(f"{Q_PREFIX}补齐4？"),
                  item(f"{Q_PREFIX}补齐5？")),
        ])
        use_llm(stub)
        got = service.generate(user, kp.id, None, 5, "easy")
        created_ids += [q.id for q in got]
        check("补题-数量达标", len(got) == 5, f"({len(got)}/5)")
        check("补题-分两轮请求", len(stub.prompts) == 2, f"(calls={len(stub.prompts)})")
        check("补题-第二轮只请求缺口",
              len(stub.prompts) == 2 and "出 3 道题" in stub.prompts[1],
              f"({stub.prompts[1][:60] if len(stub.prompts) > 1 else ''})")
        check("补题-全部来自模型", all(q.source == "ai" for q in got))

        # ---------- 2. 重复题干 + 非法条目 → 去重后题库补齐 ----------
        stub = StubChat([
            batch(
                item(f"{Q_PREFIX}去重甲？"), item(f"{Q_PREFIX}去重甲？"),
                item(f"{Q_PREFIX}去重乙？"),
                item(f"{Q_PREFIX}非法答案？", answer="Z"),
                item("短", explanation=""),
            ),
            "这不是 JSON，模型跑偏了。",
        ])
        use_llm(stub)
        got = service.generate(user, kp.id, None, 5, "medium")
        created_ids += [q.id for q in got]
        contents = [q.content for q in got]
        check("去重-数量达标", len(got) == 5, f"({len(got)}/5)")
        check("去重-无重复题干", len(set(contents)) == len(contents))
        check("去重-题库参与补齐", any(q.source == "bank" for q in got),
              f"({[q.source for q in got]})")
        check("去重-非法条目未落库",
              not any("非法答案" in c for c in contents) and "短" not in contents)

        # ---------- 3. markdown 包裹 + 中文题型/难度 → 宽容解析 ----------
        stub = StubChat([
            "```json\n" + batch(
                item(f"{Q_PREFIX}中文题型？", qtype="多选题", answer="AC",
                     options=["甲", "乙", "丙", "丁"], difficulty="简单"),
                item(f"{Q_PREFIX}判断题。", qtype="判断题", answer="正确", difficulty="基础"),
            ) + "\n```",
            batch(item(f"{Q_PREFIX}补充题？", difficulty="中等")),
        ])
        use_llm(stub)
        got = service.generate(user, kp.id, None, 3, None)
        created_ids += [q.id for q in got]
        types = {q.question_type for q in got}
        check("宽容解析-数量达标", len(got) == 3, f"({len(got)}/3)")
        check("宽容解析-中文题型归一化",
              {"multiple_choice", "true_false"} <= types, f"({types})")
        multi = next((q for q in got if q.question_type == "multiple_choice"), None)
        check("宽容解析-多选答案规范化",
              multi is not None and multi.answer == "AC",
              f"({multi.answer if multi else None})")
        check("宽容解析-中文难度归一化",
              all(q.difficulty in ("easy", "medium", "hard") for q in got),
              f"({[q.difficulty for q in got]})")

        # ---------- 4. 解析失败 → 题库兜底 ----------
        stub = StubChat(["完全无法解析的文本", "依旧无法解析"])
        use_llm(stub)
        got = service.generate(user, kp.id, None, 3, "easy")
        created_ids += [q.id for q in got]
        check("解析失败-数量达标", len(got) == 3, f"({len(got)}/3)")
        check("解析失败-题库兜底", all(q.source == "bank" for q in got))

        # ---------- 5. LLM 不可用 → 题库按知识点+同学科补齐 ----------
        use_llm(StubChat([]), available=False)
        got = service.generate(user, kp.id, None, 5, None)
        created_ids += [q.id for q in got]
        check("无模型-数量达标", len(got) == 5, f"({len(got)}/5)")
        check("无模型-全部来自题库", all(q.source == "bank" for q in got))
        check("无模型-无重复题干", len({q.content for q in got}) == len(got))

        # ---------- 6. 超出题库容量 → 如实返回且不重复 ----------
        got = service.generate(user, kp.id, None, 20, None)
        created_ids += [q.id for q in got]
        check("超容量-不超过请求数", len(got) <= 20, f"({len(got)})")
        check("超容量-跨知识点补齐生效", len(got) > 4, f"({len(got)})")
        check("超容量-无重复题干", len({q.content for q in got}) == len(got))

        # ---------- 7. 边界：count=1 ----------
        got = service.generate(user, kp.id, None, 1, None)
        created_ids += [q.id for q in got]
        check("边界-count=1", len(got) == 1, f"({len(got)})")

        # ---------- 8. 落库一致性 ----------
        stored = db.query(Question).filter(Question.id.in_(created_ids)).all() if created_ids else []
        check("落库-数量一致", len(stored) == len(created_ids),
              f"(db={len(stored)}, returned={len(created_ids)})")
        check("落库-字段完整",
              all(q.content and q.answer and q.question_type for q in stored))
        multi_rows = [q for q in stored if q.question_type == "multiple_choice"]
        check("落库-多选选项可解析",
              all(json.loads(q.options) for q in multi_rows if q.options))

        # ---------- 9. 旧调用兼容 ----------
        bank_qs = service._generate_from_bank(kp, 2)
        check("兼容-_generate_from_bank 旧签名",
              len(bank_qs) == 2 and all(q.source == "bank" for q in bank_qs))
    finally:
        restore_llm(original_chat, original_available)

    # ---------- 清理 ----------
    if created_ids:
        db.query(Question).filter(Question.id.in_(created_ids)).delete(
            synchronize_session=False
        )
    db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).delete(
        synchronize_session=False
    )
    if kp_created:
        db.delete(kp)
    db.commit()

    leftover = db.query(Question).filter(Question.content.like(f"{Q_PREFIX}%")).count()
    check("清理-无测试数据残留", leftover == 0, f"(残留 {leftover})")

    print(f"\n清理结果: 本次生成题目 {len(created_ids)} 条，测试前缀残留 {leftover} 条，"
          f"测试知识点{'已删除' if kp_created else '复用未删'}")
    db.close()

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
