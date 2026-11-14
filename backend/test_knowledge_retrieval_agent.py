"""第四阶段测试：知识检索 Agent.

覆盖：
- 正常知识点 → 检索到内容并结构化输出（重点/难点）
- 不存在的知识点 → 明确"未检索到相关知识"
- 输出符合统一 Agent 结构
- 执行状态 / 耗时 / 日志
- 检索异常 → 失败并记录错误
- 用户不一致 → 拒绝执行（隔离）
- RAG 扩展接口预留可用
- 原有 search_knowledge_base 仍正常

用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_knowledge_retrieval_agent.py
"""
import asyncio
import sys
import uuid

import app.main  # noqa: F401  确认应用可正常构建（回归）
from app.agents.core import AgentContext, AgentStatus, AgentTask
from app.agents.knowledge_retrieval_agent import KnowledgeRetrievalAgent
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import User
from app.rag.knowledge_base import search_knowledge_base
from app.rag.rag_interface import (
    DocumentLoader,
    Embedder,
    RAGPipeline,
    ResultIntegrator,
    TextSplitter,
    VectorRetriever,
)


def get_or_create_user(db, username: str, email: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username, email=email, password_hash=hash_password("test1234")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


class BrokenRetriever:
    """用于模拟检索异常的检索后端."""

    def retrieve(self, query: str, top_k: int = 3):
        raise RuntimeError("模拟检索后端异常")


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
    user = get_or_create_user(db, "kr_user", "kr@test.com")
    ctx = AgentContext(user_id=user.id, username=user.username, db=None)

    agent = KnowledgeRetrievalAgent()

    # ---------- 1. 正常知识点：检索到内容 ----------
    task = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user.id,
        task_type="knowledge_retrieval", input_data={"query": "什么是割点？"},
    )
    res = await agent.run(task, ctx)
    out = res.result or {}

    check("命中-执行状态", res.success and task.status == AgentStatus.SUCCESS)
    check("命中-耗时记录", res.execution_time >= 0, f"({res.execution_time}s)")
    check("命中-日志", len(agent.logger.entries) >= 2,
          f"({len(agent.logger.entries)} 条)")
    check("命中-found=True", out.get("found") is True)
    check("命中-有结果", out.get("count", 0) >= 1, f"(count={out.get('count')})")
    check("命中-知识点含割点",
          any("割点" in kp for kp in out.get("knowledge_points", [])),
          f"({out.get('knowledge_points')})")
    check("命中-重点非空", bool(out.get("key_points")), f"({out.get('key_points')})")
    check("命中-难点非空", bool(out.get("difficulties")),
          f"({len(out.get('difficulties', []))} 条)")

    # ---------- 2. 不存在的知识点：未检索到 ----------
    t2 = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user.id,
        task_type="knowledge_retrieval", input_data={"query": "量子纠缠的定义"},
    )
    r2 = await agent.run(t2, ctx)
    o2 = r2.result or {}
    check("未命中-执行成功", r2.success and t2.status == AgentStatus.SUCCESS)
    check("未命中-found=False", o2.get("found") is False)
    check("未命中-提示正确", "未检索到相关知识" in (o2.get("message") or ""))
    check("未命中-结果为空", o2.get("count") == 0 and o2.get("results") == [])

    # ---------- 3. 输出结构符合统一规范 ----------
    top_keys = {"agent", "found", "query", "count", "results"}
    item_keys = {
        "id", "title", "subject", "score", "context",
        "definition", "example", "key_points", "difficulties",
    }
    check("结构-顶层字段", top_keys.issubset(out.keys()), f"({sorted(out.keys())})")
    check("结构-条目字段", bool(out.get("results")) and item_keys.issubset(out["results"][0].keys()))
    check("结构-无内部对象外泄", isinstance(out["results"][0]["title"], str))

    # ---------- 4. top_k 生效 ----------
    t3 = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user.id,
        task_type="knowledge_retrieval",
        input_data={"query": "图论 集合 关系 函数 树", "top_k": 1},
    )
    r3 = await agent.run(t3, ctx)
    check("top_k-限制生效", (r3.result or {}).get("count", 0) <= 1,
          f"(count={(r3.result or {}).get('count')})")

    # ---------- 5. 检索异常：失败并记录错误 ----------
    bad_agent = KnowledgeRetrievalAgent(retriever=BrokenRetriever())
    t4 = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user.id,
        task_type="knowledge_retrieval", input_data={"query": "割点"},
    )
    r4 = await bad_agent.run(t4, ctx)
    check("异常-状态失败", (not r4.success) and t4.status == AgentStatus.FAILED)
    check("异常-错误已记录", bool(r4.error) and "模拟检索后端异常" in (r4.error or ""),
          f"({r4.error})")
    check("异常-日志含 error", bad_agent.logger.count("error") > 0,
          f"(error={bad_agent.logger.count('error')})")

    # ---------- 6. 用户隔离：任务用户与上下文不一致 ----------
    t5 = AgentTask(
        task_id=str(uuid.uuid4()), user_id=user.id,
        task_type="knowledge_retrieval", input_data={"query": "割点"},
    )
    bad_ctx = AgentContext(user_id=user.id + 9999, username="other", db=None)
    r5 = await agent.run(t5, bad_ctx)
    check("隔离-用户不一致被拒绝",
          (not r5.success) and "不一致" in (r5.error or ""), f"({r5.error})")

    # ---------- 7. RAG 扩展接口预留 ----------
    check("RAG-接口存在",
          all(hasattr(x, "__call__") or hasattr(x, "load")
              for x in (DocumentLoader, TextSplitter, Embedder,
                        VectorRetriever, ResultIntegrator)))
    pipeline = RAGPipeline()
    check("RAG-默认无向量后端", pipeline.has_vector_backend() is False)
    docs = pipeline.retrieve("割点", top_k=2)
    check("RAG-关键词后端可用", len(docs) >= 1, f"(命中 {len(docs)})")

    # ---------- 8. 原有知识库接口不受影响 ----------
    hits = search_knowledge_base("割点", top_k=3)
    check("原有接口-仍可检索", len(hits) >= 1, f"({len(hits)} 条)")
    check("原有接口-结构不变",
          all(k in hits[0] for k in ("id", "title", "subject", "score", "context", "doc")),
          f"({sorted(hits[0].keys())})")
    check("原有接口-doc 为知识文档",
          hasattr(hits[0]["doc"], "mistakes") and hasattr(hits[0]["doc"], "summary"))

    db.close()
    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
