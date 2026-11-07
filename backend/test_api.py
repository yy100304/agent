"""全链路 API 冒烟测试：登录 → Dashboard → 错题集 → 练习 → 批改 → 掌握 → 重练."""
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000/api"


def main() -> None:
    client = httpx.Client(timeout=30)
    ok, fail = 0, 0

    def check(name: str, cond: bool, extra: str = ""):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"[PASS] {name} {extra}")
        else:
            fail += 1
            print(f"[FAIL] {name} {extra}")

    # 登录
    r = client.post(f"{BASE}/auth/login", json={"username": "demo", "password": "demo123"})
    check("登录", r.status_code == 200)
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    # Dashboard
    r = client.get(f"{BASE}/dashboard", headers=h)
    d = r.json()
    check("Dashboard", r.status_code == 200 and d["study_day_count"] >= 1)
    print(f"       学习第{d['study_day_count']}天 距考试{d['exam']['days_left']}天 "
          f"今日任务{len(d['today_tasks'])}项 建议:{d['agent_suggestion']['text'][:40]}")

    # 今日任务完成
    if d["today_tasks"]:
        tid = d["today_tasks"][0]["id"]
        r = client.put(f"{BASE}/tasks/{tid}/complete", headers=h)
        check("完成任务", r.status_code == 200 and r.json()["completed"])

    # 知识点
    r = client.get(f"{BASE}/knowledge-points", headers=h)
    kps = r.json()
    check("知识点列表", r.status_code == 200 and len(kps) >= 5)
    graph_kp = next((k for k in kps if k["name"] == "图论"), kps[0])

    # 生成题目（无 LLM Key → 题库降级）
    r = client.post(
        f"{BASE}/questions/generate",
        json={"knowledge_point_id": graph_kp["id"], "count": 3},
        headers=h,
    )
    questions = r.json()
    check("生成题目", r.status_code == 200 and len(questions) == 3,
          f"(kp={graph_kp['name']}, source={questions[0]['source'] if questions else '?'})")

    # 答题（故意答错第一题 → 产生错题；答对第二题）
    q1, q2 = questions[0], questions[1]
    wrong_answer = "Z" if q1["question_type"] == "single_choice" else "胡乱回答"
    r = client.post(f"{BASE}/questions/{q1['id']}/answer",
                    json={"user_answer": wrong_answer}, headers=h)
    a1 = r.json()
    check("批改-答错", r.status_code == 200 and a1["is_correct"] is False
          and a1["wrong_question_id"] is not None,
          f"(错题#{a1['wrong_question_id']})")

    r = client.post(f"{BASE}/questions/{q2['id']}/answer",
                    json={"user_answer": _correct_for(q2, a1)}, headers=h)
    a2 = r.json()
    check("批改-答对", r.status_code == 200 and a2["is_correct"] is True)

    # 错题列表 + 筛选
    r = client.get(f"{BASE}/wrong-questions", headers=h)
    w = r.json()
    check("错题列表", r.status_code == 200 and w["stats"]["total"] >= 1,
          f"(total={w['stats']['total']} unmastered={w['stats']['unmastered']})")
    r = client.get(f"{BASE}/wrong-questions", params={"status": "unmastered", "subject": "离散数学"}, headers=h)
    check("错题筛选", r.status_code == 200)

    # 错题详情
    wid = a1["wrong_question_id"]
    r = client.get(f"{BASE}/wrong-questions/{wid}", headers=h)
    detail = r.json()
    check("错题详情", r.status_code == 200 and detail["reason"],
          f"(reason={detail['reason'][:30]})")

    # 重新练习（类似题）
    r = client.post(f"{BASE}/wrong-questions/{wid}/practice", headers=h)
    similar = r.json()
    check("错题重练-生成类似题", r.status_code == 200 and len(similar) >= 1)
    # 复习后状态应为 reviewing
    r = client.get(f"{BASE}/wrong-questions/{wid}", headers=h)
    check("重练后状态=复习中", r.json()["status"] == "reviewing")

    # 标记已掌握
    r = client.put(f"{BASE}/wrong-questions/{wid}/master", headers=h)
    m = r.json()
    check("标记已掌握", r.status_code == 200 and m["success"],
          f"(new_mastery={round(m['new_mastery'] * 100)}%)")

    # Dashboard 学习时间应已增加（完成任务+答题记录）
    r = client.get(f"{BASE}/dashboard", headers=h)
    d2 = r.json()
    check("Dashboard 数据联动", d2["stats"]["today_minutes"] >= d["stats"]["today_minutes"])

    # 未登录访问应 401
    r = client.get(f"{BASE}/wrong-questions")
    check("未登录鉴权拦截", r.status_code == 401)

    print(f"\n结果: {ok} 通过, {fail} 失败")
    sys.exit(1 if fail else 0)


def _correct_for(q: dict, prev: dict) -> str:
    """第二题尽量答对：从上一题解析拿不到，直接尝试常见正确值."""
    if q["question_type"] == "single_choice":
        return "A"
    if q["question_type"] == "true_false":
        return "正确"
    return "割点是删除后使连通分量增加的顶点"


if __name__ == "__main__":
    main()
