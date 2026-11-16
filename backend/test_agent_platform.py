"""多智能体平台端到端测试：团队/工作流/SSE 对话/轨迹落库."""
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000/api"


def sse_events(client: httpx.Client, url: str, payload: dict, headers: dict) -> list[dict]:
    events = []
    with client.stream("POST", url, json=payload, headers=headers, timeout=60) as resp:
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        for line in resp.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def main() -> None:
    client = httpx.Client()
    ok, fail = 0, 0

    def check(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"[PASS] {name} {extra}")
        else:
            fail += 1
            print(f"[FAIL] {name} {extra}")

    # 登录
    r = client.post(f"{BASE}/auth/login", json={"username": "demo", "password": "demo123"})
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # 团队定义
    r = client.get(f"{BASE}/agent/team", headers=h)
    team = r.json()
    check("Agent 团队定义", r.status_code == 200 and len(team) == 4,
          f"({[a['id'] for a in team]})")

    # 工作流定义
    r = client.get(f"{BASE}/agent/workflows", headers=h)
    wfs = r.json()
    check("工作流定义", r.status_code == 200 and len(wfs) == 4,
          f"({[w['label_name'] + ('↻' if w['self_loop'] else '') for w in wfs]})")

    # 场景1：知识点讲解（SSE 全链路）
    ev = sse_events(client, f"{BASE}/agent/chat",
                    {"message": "什么是割点？", "session_id": "test-e2e"}, h)
    types = [e["type"] for e in ev]
    dispatch = next((e for e in ev if e["type"] == "dispatch"), {})
    final = next((e for e in ev if e["type"] == "final"), {})
    tool = next((e for e in ev if e["type"] == "tool"), {})
    validate = next((e for e in ev if e["type"] == "validate"), {})
    done = next((e for e in ev if e["type"] == "done"), {})
    check("讲解-调度", dispatch.get("label") == "knowledge_explain",
          f"(channel={dispatch.get('channel')})")
    check("讲解-知识库检索", bool(tool.get("summary")), f"({tool.get('summary', '')[:30]})")
    check("讲解-验证器运行", "validate" in types and validate.get("passed") is True)
    check("讲解-最终输出", "割点" in final.get("content", ""),
          f"(长度 {len(final.get('content', ''))})")
    check("讲解-完成事件", "done" in types and done.get("run_id") > 0,
          f"(latency={done.get('latency_ms')}ms)")

    # 流式输出：delta 事件存在，且「最后一次 delta_reset 之后」的拼接结果与 final 一致
    # （Self-Loop 重试时会先推送 delta_reset 丢弃未通过验证的内容）
    deltas = [e for e in ev if e["type"] == "delta"]
    streamed_parts: list[str] = []
    resets = 0
    for item in ev:
        if item["type"] == "delta":
            streamed_parts.append(item.get("text", ""))
        elif item["type"] == "delta_reset":
            streamed_parts.clear()
            resets += 1
    streamed = "".join(streamed_parts)
    check("讲解-流式delta输出", len(deltas) >= 3,
          f"(共 {len(deltas)} 个分块，reset {resets} 次)")
    check("讲解-流式内容完整性", streamed == final.get("content", ""),
          f"(delta {len(streamed)} 字符 == final {len(final.get('content', ''))} 字符)")

    # 场景2：习题答疑
    ev = sse_events(client, f"{BASE}/agent/chat",
                    {"message": "帮我出5道图论题", "session_id": "test-e2e"}, h)
    dispatch = next((e for e in ev if e["type"] == "dispatch"), {})
    final = next((e for e in ev if e["type"] == "final"), {})
    check("答疑-调度", dispatch.get("label") == "quiz_coaching")
    check("答疑-输出非空", len(final.get("content", "")) > 50)

    # 场景3：多任务组合（编排）
    ev = sse_events(client, f"{BASE}/agent/chat",
                    {"message": "讲解一下树，然后出2道练习题", "session_id": "test-e2e"}, h)
    dispatch = next((e for e in ev if e["type"] == "dispatch"), {})
    plan = next((e for e in ev if e["type"] == "plan"), {})
    final = next((e for e in ev if e["type"] == "final"), {})
    check("多任务-调度", dispatch.get("label") == "multi_task")
    check("多任务-任务拆解", plan.get("tasks") and len(plan["tasks"]) == 2,
          f"({[t['title'] for t in plan.get('tasks', [])]})")
    check("多任务-汇总输出", "任务清单" in final.get("content", "")
          and "汇总" in final.get("content", ""))

    # 场景4：非学习请求
    ev = sse_events(client, f"{BASE}/agent/chat",
                    {"message": "你好", "session_id": "test-e2e"}, h)
    dispatch = next((e for e in ev if e["type"] == "dispatch"), {})
    final = next((e for e in ev if e["type"] == "final"), {})
    check("非学习-拦截引导", dispatch.get("label") == "non_learning"
          and "智学" in final.get("content", ""))

    # 场景5：笔记整理
    ev = sse_events(client, f"{BASE}/agent/chat",
                    {"message": "整理笔记：树是无回路连通图。n个顶点有n-1条边。任意两点路径唯一。",
                     "session_id": "test-e2e"}, h)
    dispatch = next((e for e in ev if e["type"] == "dispatch"), {})
    final = next((e for e in ev if e["type"] == "final"), {})
    check("笔记-调度", dispatch.get("label") == "notes_organizing")
    check("笔记-结构化输出", "- " in final.get("content", ""))

    # 运行记录（轨迹落库）
    r = client.get(f"{BASE}/agent/runs", params={"limit": 10}, headers=h)
    runs = r.json()
    check("执行轨迹落库", r.status_code == 200 and len(runs) >= 5,
          f"(共 {len(runs)} 条，标签 {sorted(set(x['label_name'] for x in runs))})")

    # 未登录拦截
    r = client.get(f"{BASE}/agent/team")
    check("未登录拦截", r.status_code == 401)

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
