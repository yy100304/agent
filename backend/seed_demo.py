"""演示数据种子脚本.

为 demo 用户生成完整的学习数据，用于本地演示与页面测试：
- 知识点（离散数学 6 个）
- 学习计划（离散数学备考，考试日期 = 今天 + 7 天）
- 今日任务 4 项 + 未来 7 天任务
- 题库 + 历史答题（图论正确率刻意偏低）
- 错题（含错误原因）
- 学习记录（近 7 天）与学习画像

用法：
    python seed_demo.py           # 已有数据则跳过
    python seed_demo.py --reset   # 清空学习数据后重新生成
"""
import json
import random
import sys
from datetime import date, datetime, timedelta

from app.core.logging import logger
from app.core.security import hash_password
from app.database.session import SessionLocal, init_db
from app.models import (
    Answer,
    KnowledgePoint,
    LearningProfile,
    LearningRecord,
    Question,
    StudyPlan,
    StudyTask,
    User,
    WrongQuestion,
)
from app.services.question_service import BANK

random.seed(42)

KP_SEEDS = [
    ("离散数学", "集合", "集合的基本运算、子集、幂集与容斥原理", "easy"),
    ("离散数学", "关系", "关系的性质、等价关系与偏序关系", "medium"),
    ("离散数学", "函数", "单射、满射、双射与复合函数", "medium"),
    ("离散数学", "图论", "图的基本概念、连通性、割点与割边", "hard"),
    ("离散数学", "树", "树的性质、生成树与根树", "medium"),
    ("离散数学", "命题逻辑", "命题、联结词、真值表与等价式", "easy"),
]

# 各知识点历史正确率（模拟真实掌握情况：图论薄弱）
KP_ACCURACY = {
    "集合": 0.9,
    "关系": 0.8,
    "函数": 0.65,
    "图论": 0.5,
    "树": 0.6,
    "命题逻辑": 0.85,
}

# 初始掌握度
KP_INITIAL_MASTERY = {
    "集合": 0.9,
    "关系": 0.82,
    "函数": 0.68,
    "图论": 0.52,
    "树": 0.61,
    "命题逻辑": 0.8,
}

TODAY_TASKS = [
    ("复习图论基础：连通性与割点", "图论", 30, False),
    ("完成 5 道图论练习", "图论", 20, False),
    ("复习 3 道图论错题", "图论", 15, False),
    ("学习割点与割边", "图论", 30, False),
]

FUTURE_TASK_TEMPLATES = [
    ("复习「{kp}」核心概念", 30),
    ("完成 5 道「{kp}」练习", 25),
    ("复习「{kp}」错题", 15),
]


def reset(db) -> None:
    """清空学习相关数据（保留用户表）。"""
    for model in (WrongQuestion, Answer, LearningRecord, LearningProfile,
                  StudyTask, StudyPlan, Question, KnowledgePoint):
        db.query(model).delete()
    db.commit()
    logger.info("已清空学习相关数据")


def ensure_demo_user(db) -> User:
    user = db.query(User).filter(User.username == "demo").first()
    if not user:
        user = User(
            username="demo",
            email="demo@studyflow.com",
            password_hash=hash_password("demo123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("创建 demo 用户")
    # 演示叙事：学习第 12 天
    user.created_at = datetime.utcnow() - timedelta(days=11)
    db.commit()
    return user


def seed(db, user: User) -> None:
    today = date.today()

    # ---- 知识点 ----
    kps: dict[str, KnowledgePoint] = {}
    for subject, name, desc, diff in KP_SEEDS:
        kp = KnowledgePoint(subject=subject, name=name, description=desc, difficulty=diff)
        db.add(kp)
        kps[name] = kp
    db.commit()

    # ---- 学习计划（考试 = 7 天后）----
    plan = StudyPlan(
        user_id=user.id,
        title="离散数学期末备考",
        subject="离散数学",
        exam_date=today + timedelta(days=7),
        daily_minutes=120,
        status="active",
    )
    db.add(plan)
    db.commit()

    # ---- 今日任务 ----
    for title, kp_name, minutes, done in TODAY_TASKS:
        db.add(StudyTask(
            plan_id=plan.id,
            knowledge_point_id=kps[kp_name].id,
            title=title,
            description=None,
            estimated_minutes=minutes,
            completed=done,
            scheduled_date=today,
        ))

    # ---- 未来 6 天任务 ----
    for offset in range(1, 7):
        for kp_name in ["图论", "函数", "树", "关系", "集合", "命题逻辑"]:
            for tpl, minutes in random.sample(FUTURE_TASK_TEMPLATES, 2):
                db.add(StudyTask(
                    plan_id=plan.id,
                    knowledge_point_id=kps[kp_name].id,
                    title=tpl.format(kp=kp_name),
                    estimated_minutes=minutes,
                    completed=False,
                    scheduled_date=today + timedelta(days=offset),
                ))
    db.commit()

    # ---- 题目（内置题库入库）----
    questions: list[Question] = []
    for item in BANK:
        q = Question(
            knowledge_point_id=kps[item["kp"]].id,
            content=item["content"],
            question_type=item["type"],
            options=json.dumps(item["options"], ensure_ascii=False) if item["options"] else None,
            answer=item["answer"],
            explanation=item["explanation"],
            difficulty=item["difficulty"],
            source="bank",
        )
        db.add(q)
        questions.append(q)
    db.commit()

    # ---- 历史答题（近 7 天，按知识点模拟正确率）----
    wrong_by_kp: dict[str, list[tuple[Question, str]]] = {}
    answer_rows = []
    for day_offset in range(6, -1, -1):
        day = today - timedelta(days=day_offset)
        # 每天答 4~6 题
        day_questions = random.sample(questions, random.randint(4, 6))
        for q in day_questions:
            kp_name = q.knowledge_point.name if q.knowledge_point else "集合"
            # 用题库答案模拟对错
            correct = random.random() < KP_ACCURACY.get(kp_name, 0.7)
            if q.question_type == "single_choice":
                correct_letter = q.answer
                if correct:
                    user_answer = correct_letter
                else:
                    others = [o for o in "ABCD" if o != correct_letter]
                    user_answer = random.choice(others)
            elif q.question_type == "true_false":
                user_answer = q.answer if correct else ("正确" if q.answer == "错误" else "错误")
            else:
                user_answer = "割点是删除后使连通分量增加的顶点" if correct else "割点就是度数为 1 的顶点"
            created = datetime.combine(day, datetime.min.time()).replace(
                hour=random.randint(9, 21), minute=random.randint(0, 59)
            )
            answer_rows.append(Answer(
                user_id=user.id,
                question_id=q.id,
                user_answer=user_answer,
                is_correct=correct,
                score=1.0 if correct else 0.0,
                created_at=created,
            ))
            if not correct:
                wrong_by_kp.setdefault(kp_name, []).append((q, user_answer))
    db.add_all(answer_rows)
    db.commit()

    # ---- 错题（含规则生成的错误原因）----
    for kp_name, wrongs in wrong_by_kp.items():
        for q, user_answer in wrongs:
            if q.question_type == "short_answer":
                reason = f"简答题回答不完整，涉及「{kp_name}」的关键概念表述不到位。"
            else:
                reason = f"对「{kp_name}」相关概念理解不准确，混淆了易错点。"
            suggestion = f"建议重新学习「{kp_name}」的相关概念，然后完成针对性练习。"
            db.add(WrongQuestion(
                user_id=user.id,
                question_id=q.id,
                reason=reason,
                suggestion=suggestion,
                mastered=False,
                review_count=0,
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 6)),
            ))
    db.commit()

    # ---- 学习记录（近 7 天）----
    daily_minutes = [45, 60, 30, 75, 90, 40, 55]
    for i, minutes in enumerate(daily_minutes):
        day = today - timedelta(days=6 - i)
        created = datetime.combine(day, datetime.min.time()).replace(hour=20)
        db.add(LearningRecord(
            user_id=user.id,
            knowledge_point_id=random.choice(list(kps.values())).id,
            study_minutes=minutes,
            mastery_score=KP_INITIAL_MASTERY[random.choice(list(KP_INITIAL_MASTERY))],
            source=random.choice(["practice", "task"]),
            created_at=created,
        ))
    db.commit()

    # ---- 学习画像 ----
    for name, kp in kps.items():
        db.add(LearningProfile(
            user_id=user.id,
            knowledge_point_id=kp.id,
            mastery_score=KP_INITIAL_MASTERY[name],
            confidence=random.randint(5, 15),
            last_updated=datetime.utcnow(),
        ))
    db.commit()

    logger.info(f"演示数据生成完成：{len(questions)} 题 / {len(answer_rows)} 答题记录 / "
                f"{sum(len(v) for v in wrong_by_kp.values())} 错题")


def main() -> None:
    reset_mode = "--reset" in sys.argv
    init_db()
    db = SessionLocal()
    try:
        if reset_mode:
            reset(db)

        # 幂等：已有知识点则跳过
        if db.query(KnowledgePoint).count() > 0 and not reset_mode:
            logger.info("检测到已有学习数据，跳过生成（使用 --reset 重新生成）")
            return

        user = ensure_demo_user(db)
        seed(db, user)
        print("演示数据生成完成：demo / demo123")
    finally:
        db.close()


if __name__ == "__main__":
    main()