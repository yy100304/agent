"""第八阶段测试：主控 Agent 的 HTTP 接口（/api/agent/tasks）.

覆盖：
- POST /api/agent/tasks：自然语言需求 → 主控统一结果（含计划/意图/步骤/日志）
- options 显式参数（days / daily_minutes）优先于自然语言解析
- GET  /api/agent/tasks：当前用户任务列表
- GET  /api/agent/tasks/{id}：详情（计划、步骤、日志、结果）
- 用户隔离：他人任务不可见（404）、列表互不可见
- 鉴权：未登录 401
- 旧接口回归：/api/agent/team、/api/agent/workflows、/api/agent/runs、/api/dashboard

测试不消耗 DeepSeek 额度：llm_service.chat 被临时替换为返回 None。
用法（在 backend 目录下）：
    .\.venv\Scripts\python.exe test_master_api.py
"""
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agents.registration import register_core_agents
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.main import app
from app.models import (
    AgentExecutionLog,
    AgentTaskRecord,
    StudyPlan,
    StudyTask,
    User,
    WorkflowRecord,
    WorkflowStepRecord,
)
from app.services.llm_service import llm_service

USER_A = ("master_api_a", "master_api_a@test.com")
USER_B = ("master_api_b", "master_api_b@test.com")
PASSWORD = "test1234"


def get_or_create_user(db, username: str, email: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, email=email, password_hash=hash_password(PASSWORD))
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def cleanup(db, users: list[User]) -> None:
    """清理测试用户产生的计划与 Agent 任务记录."""
    plan_ids = [p.id for p in db.query(StudyPlan).filter(
        StudyPlan.user_id.in_([u.id for u in users])
    ).all()]
    if plan_ids:
        db.query(StudyTask).filter(StudyTask.plan_id.in_(plan_ids)).delete(
            synchronize_session=False
        )
        db.query(StudyPlan).filter(StudyPlan.id.in_(plan_ids)).delete(
            synchronize_session=False
        )
    rows = db.query(AgentTaskRecord).filter(
        AgentTaskRecord.user_id.in_([u.id for u in users])
    ).all()
    task_ids = [r.id for r in rows]
    if task_ids:
        workflow_ids = [w.id for w in db.query(WorkflowRecord).filter(
            WorkflowRecord.agent_task_id.in_(task_ids)
        ).all()]
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
    register_core_agents()
    db = SessionLocal()
    user_a = get_or_create_user(db, *USER_A)
    user_b = get_or_create_user(db, *USER_B)
    cleanup(db, [user_a, user_b])

    with patch.object(llm_service, "chat", return_value=None), TestClient(app) as client:
        # ---- 鉴权：未登录被拒 ----
        r = client.post("/api/agent/tasks", json={"message": "帮我分析一下最近的学习情况。"})
        check("鉴权-未登录返回 401", r.status_code == 401, f"({r.status_code})")

        # ---- 登录（回归：认证链路正常） ----
        r = client.post(
            "/api/auth/login", json={"username": USER_A[0], "password": PASSWORD}
        )
        check("回归-登录成功", r.status_code == 200, f"({r.status_code})")
        token_a = r.json().get("access_token", "")
        header_a = {"Authorization": f"Bearer {token_a}"}

        r = client.post(
            "/api/auth/login", json={"username": USER_B[0], "password": PASSWORD}
        )
        token_b = r.json().get("access_token", "")
        header_b = {"Authorization": f"Bearer {token_b}"}

        # ---- POST：自然语言需求 → 主控统一结果 ----
        r = client.post(
            "/api/agent/tasks",
            json={"message": "帮我分析一下最近的学习情况。"},
            headers=header_a,
        )
        body = r.json() if r.status_code == 200 else {}
        check("提交-状态码 200", r.status_code == 200, f"({r.status_code}, {r.text[:120]})")
        check("提交-返回统一字段",
              {"task_id", "task_status", "original_request", "parsed_intent",
               "execution_plan", "executed_agents", "agent_results",
               "execution_logs", "final_result", "execution_time"} <= set(body),
              f"({sorted(body.keys())})")
        task_a = body.get("task_id")
        check("提交-意图与调度正确",
              body.get("parsed_intent", {}).get("intents") == ["analysis"]
              and body.get("executed_agents") == ["learning_analysis"],
              f"({body.get('executed_agents')})")
        check("提交-任务已完成", body.get("task_status") in ("success", "partial"),
              f"({body.get('task_status')})")

        # ---- POST：options 显式参数优先 ----
        r = client.post(
            "/api/agent/tasks",
            json={
                "message": "帮我制定一个复习计划。",
                "options": {"days": 5, "daily_minutes": 60, "subject": "离散数学"},
            },
            headers=header_a,
        )
        body2 = r.json() if r.status_code == 200 else {}
        plan = (body2.get("final_result", {}).get("artifacts") or {}).get("study_planning") or {}
        check("参数-显式 options 避免追问", body2.get("task_status") != "need_input",
              f"({body2.get('task_status')})")
        check("参数-按显式每日时长生成计划",
              plan.get("daily_minutes") == 60 and plan.get("days") == 5,
              f"(daily={plan.get('daily_minutes')}, days={plan.get('days')})")
        check("参数-计划已写入数据库",
              bool(plan.get("plan_id")) and db.query(StudyPlan).filter(
                  StudyPlan.id == plan.get("plan_id")
              ).count() == 1)

        # ---- GET 列表 ----
        r = client.get("/api/agent/tasks", headers=header_a)
        rows = r.json() if r.status_code == 200 else []
        check("列表-返回当前用户任务",
              r.status_code == 200 and any(row["task_id"] == task_a for row in rows),
              f"({len(rows)} 条)")

        # ---- GET 详情 ----
        r = client.get(f"/api/agent/tasks/{task_a}", headers=header_a)
        detail = r.json() if r.status_code == 200 else {}
        check("详情-返回步骤与日志",
              r.status_code == 200
              and len(detail.get("steps") or []) >= 1
              and len(detail.get("logs") or []) >= 1
              and (detail.get("result") or {}).get("task_id") == task_a,
              f"(steps={len(detail.get('steps') or [])}, logs={len(detail.get('logs') or [])})")

        # ---- 用户隔离 ----
        r = client.get(f"/api/agent/tasks/{task_a}", headers=header_b)
        check("隔离-他人任务返回 404", r.status_code == 404, f"({r.status_code})")
        r = client.get("/api/agent/tasks", headers=header_b)
        others = r.json() if r.status_code == 200 else []
        check("隔离-他人列表不含该任务",
              all(row["task_id"] != task_a for row in others), f"({len(others)} 条)")

        # ---- 旧接口回归（不删除、不破坏） ----
        r = client.get("/api/agent/team", headers=header_a)
        check("回归-/api/agent/team 可用",
              r.status_code == 200 and len(r.json()) >= 4, f"({r.status_code})")
        r = client.get("/api/agent/workflows", headers=header_a)
        check("回归-/api/agent/workflows 可用",
              r.status_code == 200 and len(r.json()) >= 4, f"({r.status_code})")
        r = client.get("/api/agent/runs", headers=header_a)
        check("回归-/api/agent/runs 可用", r.status_code == 200, f"({r.status_code})")
        r = client.get("/api/dashboard", headers=header_a)
        check("回归-/api/dashboard 可用", r.status_code == 200, f"({r.status_code})")
        r = client.get("/health")
        check("回归-/health 可用", r.status_code == 200, f"({r.status_code})")

    # ---- 清理 ----
    cleanup(db, [user_a, user_b])
    leftover = db.query(AgentTaskRecord).filter(
        AgentTaskRecord.user_id.in_([user_a.id, user_b.id])
    ).count()
    leftover_plans = db.query(StudyPlan).filter(
        StudyPlan.user_id.in_([user_a.id, user_b.id])
    ).count()
    check("清理-测试数据已清除",
          leftover == 0 and leftover_plans == 0,
          f"(agent_tasks={leftover}, plans={leftover_plans})")

    db.close()
    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
