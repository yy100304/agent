"""第二阶段冒烟测试：Agent 基础架构.

覆盖：注册机制 / 统一执行接口 / 状态管理 / 执行日志 / 落库 / 失败重试 / 超时。

用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_agent_core.py
"""
import asyncio
import json
import sys
import uuid

from app.agents.core import (
    AgentContext,
    AgentStatus,
    AgentTask,
    CoreAgentRegistry,
    EchoAgent,
    ExecutionLogger,
    FlakyAgent,
    SlowAgent,
)
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import AgentExecutionLog, AgentTaskRecord, User


def get_or_create_test_user(db) -> User:
    """获取/创建测试用户（不影响 demo 等既有用户）."""
    user = db.query(User).filter(User.username == "coretest").first()
    if not user:
        user = User(
            username="coretest",
            email="coretest@example.com",
            password_hash=hash_password("coretest123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def new_task(user_id: int, text: str = "hello") -> AgentTask:
    return AgentTask(
        task_id=str(uuid.uuid4()),
        user_id=user_id,
        task_type="demo",
        input_data={"text": text},
    )


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

    # ---- 初始化数据库（create_all 只会新增表，不动旧表）----
    init_db()
    db = SessionLocal()
    user = get_or_create_test_user(db)
    ctx = AgentContext(user_id=user.id, username=user.username, db=db)

    # ---- 1. 注册机制 ----
    registry = CoreAgentRegistry()
    registry.register(EchoAgent())
    registry.register(FlakyAgent(fail_times=1))
    check("注册-数量", len(registry.list_all()) == 2, f"({registry.names()})")
    check("注册-按名查找", registry.get("echo") is not None)
    check("注册-列表元信息", all("name" in d for d in registry.to_dicts()))

    dup_ok = False
    try:
        registry.register(EchoAgent())
    except ValueError:
        dup_ok = True
    check("注册-重复注册报错", dup_ok)

    # ---- 2. 成功执行 + 状态 + 日志 ----
    echo = registry.require("echo")
    echo_logger = ExecutionLogger()
    echo.logger = echo_logger
    task = new_task(user.id, "你好，Agent")
    result = await echo.run(task, ctx)
    check("执行-成功", result.success and task.status == AgentStatus.SUCCESS)
    check("执行-结果回显", result.result.get("echo") == "你好，Agent")
    check("执行-耗时记录", result.execution_time >= 0)
    check("执行-完成时间", task.completed_at is not None)
    check("日志-记录条目", len(echo_logger.entries) >= 2, f"({len(echo_logger.entries)} 条)")

    # ---- 3. 失败后重试并最终成功 ----
    flaky = registry.require("flaky")
    flaky_logger = ExecutionLogger()
    flaky.logger = flaky_logger
    ftask = new_task(user.id)
    fresult = await flaky.run(ftask, ctx)
    check("重试-最终成功", fresult.success and ftask.status == AgentStatus.SUCCESS)
    check("重试-尝试次数", fresult.metadata.get("attempts") == 2,
          f"(attempts={fresult.metadata.get('attempts')})")
    check("重试-日志含重试", any("重试" in e.message for e in flaky_logger.entries))

    # ---- 4. 超过重试次数 → 失败 ----
    always_fail = FlakyAgent(fail_times=99)
    always_fail.logger = ExecutionLogger()
    atask = new_task(user.id)
    aresult = await always_fail.run(atask, ctx)
    check("失败-结果失败", (not aresult.success) and atask.status == AgentStatus.FAILED)
    check("失败-错误信息", bool(aresult.error), f"({aresult.error})")
    check("失败-尝试次数达上限", aresult.metadata.get("attempts") == 3,
          f"(attempts={aresult.metadata.get('attempts')})")

    # ---- 5. 超时控制 ----
    slow = SlowAgent()
    slow.logger = ExecutionLogger()
    stask = new_task(user.id)
    sresult = await slow.run(stask, ctx)
    check("超时-失败", (not sresult.success) and stask.status == AgentStatus.FAILED)
    check("超时-错误信息", "超时" in (sresult.error or ""), f"({sresult.error})")

    # ---- 6. 落库（任务记录 + 执行日志）----
    row = AgentTaskRecord(
        task_id=task.task_id,
        user_id=user.id,
        title="core smoke",
        task_type="demo",
        input_json=json.dumps(task.input_data, ensure_ascii=False),
        status=task.status.value,
        result_json=json.dumps(result.result, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    written = echo_logger.flush(db, row.id)
    persisted = (
        db.query(AgentExecutionLog)
        .filter(AgentExecutionLog.agent_task_id == row.id)
        .count()
    )
    check("落库-任务记录", row.id > 0)
    check("落库-日志条数一致", written == persisted == len(echo_logger.entries),
          f"(written={written}, db={persisted}, mem={len(echo_logger.entries)})")

    # ---- 7. 清理测试数据（不触碰业务表与既有用户）----
    db.query(AgentExecutionLog).filter(AgentExecutionLog.agent_task_id == row.id).delete()
    db.query(AgentTaskRecord).filter(AgentTaskRecord.id == row.id).delete()
    db.commit()
    db.close()

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    asyncio.run(main())
