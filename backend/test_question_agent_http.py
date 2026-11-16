"""第六阶段 HTTP 接入测试：/api/questions/generate 是否走练习生成 Agent.

覆盖：
- 接口真实调用练习生成 Agent（响应头回传 Agent 状态）
- LLM 不可用时自动题库兜底（数量达标、source=bank）
- 兜底数量不足时返回 partial（响应头 + 实际条数）
- 原有请求体（只有 knowledge_point_id/count）仍然兼容
- 响应结构兼容原练习页面（无 answer 泄露、字段齐全）
- 无效知识点返回 400
- 原有答题记录 / 错题集在生成前后不变

测试数据标识：知识点名称「【测试】HTTP兜底点」，清理仅删除该知识点及其题目。
不消耗 DeepSeek 额度：测试期间临时关闭 LLM。

用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_question_agent_http.py
"""
import sys
from urllib.parse import unquote

from fastapi.testclient import TestClient

from app.agents.core.registry import core_registry
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.main import app
from app.models import Answer, KnowledgePoint, Question, User, WrongQuestion
from app.services.llm_service import llm_service

KP_NAME = "【测试】HTTP兜底点"
KP_SUBJECT = "【测试】HTTP学科"
USERNAME = "http_qg_test"
PASSWORD = "test1234"


def get_or_create_user(db) -> User:
    user = db.query(User).filter(User.username == USERNAME).first()
    if not user:
        user = User(username=USERNAME, email="http_qg@test.com",
                    password_hash=hash_password(PASSWORD))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_or_create_kp(db) -> tuple[KnowledgePoint, bool]:
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.name == KP_NAME).first()
    if kp:
        return kp, False
    kp = KnowledgePoint(subject=KP_SUBJECT, name=KP_NAME,
                        description="接口测试专用", difficulty="easy")
    db.add(kp)
    db.commit()
    db.refresh(kp)
    return kp, True


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
    user = get_or_create_user(db)
    kp, kp_created = get_or_create_kp(db)
    created_ids: list[int] = []
    original_available = llm_service._available

    try:
        llm_service._available = False     # 强制走题库兜底，验证离线可用性

        with TestClient(app) as client:
            res = client.post("/api/auth/login",
                              json={"username": USERNAME, "password": PASSWORD})
            check("登录-测试账号可用", res.status_code == 200, f"({res.status_code})")
            headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

            # ---------- 1. 接口真正走 Agent + 题库兜底 ----------
            ans_before = db.query(Answer).filter(Answer.user_id == user.id).count()
            wrong_before = db.query(WrongQuestion).filter(
                WrongQuestion.user_id == user.id
            ).count()

            res1 = client.post("/api/questions/generate", headers=headers,
                               json={"knowledge_point_id": kp.id, "count": 3})
            data1 = res1.json()
            check("接口-返回 200", res1.status_code == 200, f"({res1.status_code})")
            check("接口-走到 Agent（带状态头）",
                  res1.headers.get("x-agent-status") is not None,
                  f"({dict(res1.headers).get('x-agent-status')})")
            check("接口-数量正确",
                  isinstance(data1, list) and len(data1) == 3,
                  f"({len(data1) if isinstance(data1, list) else data1})")
            check("接口-状态头 success",
                  res1.headers.get("x-agent-status") == "success",
                  f"({res1.headers.get('x-agent-status')})")
            check("接口-实际数量头一致",
                  res1.headers.get("x-actual-count") == "3",
                  f"({res1.headers.get('x-actual-count')})")
            check("接口-兜底数量头",
                  res1.headers.get("x-agent-fallback") == "3",
                  f"({res1.headers.get('x-agent-fallback')})")
            check("接口-题目来自题库",
                  all(q["source"] == "bank" for q in data1),
                  f"({[q['source'] for q in data1]})")
            created_ids += [q["id"] for q in data1]

            # ---------- 2. 兜底不足 → partial ----------
            res2 = client.post("/api/questions/generate", headers=headers,
                               json={"knowledge_point_id": kp.id, "count": 3,
                                     "question_types": ["short_answer"]})
            data2 = res2.json()
            created_ids += [q["id"] for q in data2]
            check("partial-状态头", res2.headers.get("x-agent-status") == "partial",
                  f"({res2.headers.get('x-agent-status')})")
            check("partial-实际数量小于要求", 0 < len(data2) < 3, f"({len(data2)}/3)")
            check("partial-响应体数量与头一致",
                  res2.headers.get("x-actual-count") == str(len(data2)),
                  f"({res2.headers.get('x-actual-count')} vs {len(data2)})")
            check("partial-仅返回多选/简答题型",
                  all(q["question_type"] == "short_answer" for q in data2),
                  f"({[q['question_type'] for q in data2]})")

            check("partial-失败原因可通过响应头获取",
                  bool(unquote(res2.headers.get("x-agent-reason", ""))),
                  f"({unquote(res2.headers.get('x-agent-reason', ''))[:40]})")

            # ---------- 2.1 多选题兜底 ----------
            res2b = client.post("/api/questions/generate", headers=headers,
                               json={"knowledge_point_id": kp.id, "count": 3,
                                     "question_types": ["multiple_choice"]})
            data2b = res2b.json()
            created_ids += [q["id"] for q in data2b]
            check("多选兜底-数量达标", len(data2b) == 3, f"({len(data2b)}/3)")
            check("多选兜底-状态 success",
                  res2b.headers.get("x-agent-status") == "success",
                  f"({res2b.headers.get('x-agent-status')})")
            check("多选兜底-题型均为多选",
                  all(q["question_type"] == "multiple_choice" for q in data2b),
                  f"({[q['question_type'] for q in data2b]})")

            # ---------- 2.2 多选题兜底不足 → partial ----------
            res2c = client.post("/api/questions/generate", headers=headers,
                               json={"knowledge_point_id": kp.id, "count": 7,
                                     "question_types": ["multiple_choice"]})
            data2c = res2c.json()
            created_ids += [q["id"] for q in data2c]
            check("多选不足-返回 partial",
                  res2c.headers.get("x-agent-status") == "partial",
                  f"({res2c.headers.get('x-agent-status')})")
            check("多选不足-实际数量小于要求", 0 < len(data2c) < 7, f"({len(data2c)}/7)")
            check("多选不足-实际数量头一致",
                  res2c.headers.get("x-actual-count") == str(len(data2c)),
                  f"({res2c.headers.get('x-actual-count')} vs {len(data2c)})")

            # ---------- 3. 旧调用方式（不传新增字段）----------
            res3 = client.post("/api/questions/generate", headers=headers,
                               json={"knowledge_point_id": kp.id, "count": 2})
            data3 = res3.json()
            created_ids += [q["id"] for q in data3]
            check("兼容-旧请求体仍可用",
                  res3.status_code == 200 and len(data3) == 2,
                  f"({res3.status_code}, {len(data3)})")

            # ---------- 4. 原练习页面字段兼容 ----------
            item = data1[0]
            check("页面-字段齐全",
                  {"id", "knowledge_point_id", "content", "question_type",
                   "options", "difficulty", "source"} <= set(item.keys()),
                  f"({sorted(item.keys())})")
            check("页面-不泄露答案", "answer" not in item)
            check("页面-知识点名正确",
                  item.get("knowledge_point_name") == KP_NAME,
                  f"({item.get('knowledge_point_name')})")

            # ---------- 5. 无效知识点 → 400 ----------
            res4 = client.post("/api/questions/generate", headers=headers,
                               json={"knowledge_point_id": 99999999, "count": 1})
            check("无效知识点-返回 400", res4.status_code == 400,
                  f"({res4.status_code})")

            # ---------- 5.1 CORS 暴露自定义响应头（浏览器可读）----------
            res_cors = client.get(
                "/api/knowledge-points",
                headers={**headers, "Origin": "http://localhost:5173"},
            )
            exposed = res_cors.headers.get("access-control-expose-headers", "").lower()
            check("CORS-暴露 x-agent-status", "x-agent-status" in exposed, f"({exposed})")
            check("CORS-暴露 x-agent-reason", "x-agent-reason" in exposed, f"({exposed})")
            check("CORS-暴露 x-actual-count", "x-actual-count" in exposed, f"({exposed})")

            # ---------- 6. 原有答题记录 / 错题集不受影响 ----------
            check("原有-答题记录不变",
                  db.query(Answer).filter(Answer.user_id == user.id).count() == ans_before,
                  f"({ans_before})")
            check("原有-错题记录不变",
                  db.query(WrongQuestion).filter(
                      WrongQuestion.user_id == user.id).count() == wrong_before,
                  f"({wrong_before})")

        # ---------- 7. 注册表 ----------
        check("注册表-可用 Agent", core_registry.get("question_generation") is not None)

        # ---------- 8. 落库核对 ----------
        rows = db.query(Question).filter(Question.id.in_(created_ids)).all() if created_ids else []
        check("落库-数量一致", len(rows) == len(created_ids),
              f"(db={len(rows)}, 返回={len(created_ids)})")
        check("落库-归属测试知识点",
              all(r.knowledge_point_id == kp.id for r in rows))
    finally:
        llm_service._available = original_available

    # ---------- 清理：仅删除本次创建的题目与测试知识点 ----------
    if created_ids:
        db.query(Question).filter(Question.id.in_(created_ids)).delete(
            synchronize_session=False
        )
    db.commit()
    if kp_created:
        db.query(Question).filter(Question.knowledge_point_id == kp.id).delete(
            synchronize_session=False
        )
        db.delete(kp)
        db.commit()

    leftover = db.query(Question).filter(
        Question.knowledge_point_id == kp.id
    ).count() if kp_created else 0
    check("清理-无测试数据残留", leftover == 0, f"(残留 {leftover})")

    print(f"\n清理结果: 删除本次题目 {len(created_ids)} 条，"
          f"测试知识点{'已删除' if kp_created else '复用未删'}")
    db.close()

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
