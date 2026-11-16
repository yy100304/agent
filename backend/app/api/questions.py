"""练习 / 题目 / 答题 API."""
import asyncio
import json
import uuid
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import Answer, LearningProfile, Question, User
from app.schemas.question import (
    AnswerRequest,
    AnswerResult,
    GenerateQuestionsRequest,
    QuestionDetail,
    QuestionOut,
)
from app.services.learning_service import LearningService
from app.services.question_service import QuestionService
from app.services.wrong_question_service import WrongQuestionService

router = APIRouter()


def _to_out(q: Question) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        knowledge_point_id=q.knowledge_point_id,
        knowledge_point_name=q.knowledge_point.name if q.knowledge_point else None,
        subject=q.knowledge_point.subject if q.knowledge_point else None,
        content=q.content,
        question_type=q.question_type,
        options=json.loads(q.options) if q.options else None,
        difficulty=q.difficulty,
        source=q.source,
    )


@router.post("/generate", response_model=List[QuestionOut])
def generate_questions(
    payload: GenerateQuestionsRequest,
    response: Response,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[QuestionOut]:
    """AI 生成练习题（统一走第六阶段练习生成 Agent）.

    兼容原有调用方式：路径、请求体（新增字段全部可选）、响应体仍是题目列表。
    Agent 的执行状态通过响应头回传，便于前端区分 success / partial / failed：
      X-Agent-Status / X-Requested-Count / X-Actual-Count /
      X-Agent-Attempts / X-Agent-Fallback
    """
    # 根据掌握度动态决定难度（保留原有行为）
    mastery_hint = None
    if payload.knowledge_point_id:
        learning = LearningService(db)
        profile = learning.get_or_create_profile(current_user.id, payload.knowledge_point_id)
        mastery_hint = profile.mastery_score if profile.confidence > 0 else None

    from app.agents.core import AgentContext, AgentTask
    from app.agents.core.registry import core_registry
    from app.agents.question_generation_agent import QuestionGenerationAgent

    agent = core_registry.get("question_generation") or QuestionGenerationAgent()
    task = AgentTask(
        task_id=str(uuid.uuid4()),
        user_id=current_user.id,
        task_type="question_generation",
        input_data={
            "count": payload.count,
            "knowledge_point_id": payload.knowledge_point_id,
            "knowledge_point": payload.knowledge_point,
            "subject": payload.subject,
            "difficulty": payload.difficulty,
            "question_types": payload.question_types,
            "use_weak_points": payload.use_weak_points,
            "mastery_hint": mastery_hint,
        },
    )
    ctx = AgentContext(
        user_id=current_user.id, username=current_user.username, db=db
    )

    try:
        result = asyncio.run(agent.run(task, ctx))
    except Exception as e:
        logger.exception(f"生成题目失败：{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="题目生成失败，请稍后再试",
        )

    if not result.success or not isinstance(result.result, dict):
        logger.error(f"练习生成 Agent 执行失败：{result.error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="题目生成失败，请稍后再试",
        )

    data = result.result
    agent_status = str(data.get("status") or "failed")
    response.headers["X-Agent-Status"] = agent_status
    response.headers["X-Requested-Count"] = str(data.get("requested_count", payload.count))
    response.headers["X-Actual-Count"] = str(data.get("actual_count", 0))
    response.headers["X-Agent-Attempts"] = str(data.get("attempts", 0))
    response.headers["X-Agent-Fallback"] = str(int(data.get("fallback_count", 0)))
    # 失败/部分成功原因（中文需 URL 编码，HTTP 头只允许 ASCII）
    response.headers["X-Agent-Reason"] = quote(str(data.get("reason") or ""))[:600]

    ids = [int(i) for i in (data.get("question_ids") or [])]
    if not ids:
        # 与旧接口一致：未生成任何题目时按 400 返回明确原因
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=data.get("reason") or "未生成有效题目，请稍后再试",
        )

    rows = db.query(Question).filter(Question.id.in_(ids)).all()
    order = {qid: idx for idx, qid in enumerate(ids)}
    rows.sort(key=lambda q: order.get(q.id, len(order)))
    return [_to_out(q) for q in rows]


@router.post("/{question_id}/answer", response_model=AnswerResult)
def submit_answer(
    question_id: int,
    payload: AnswerRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> AnswerResult:
    """提交答案：自动批改 → 保存答题 → 错题入库（AI 分析）→ 更新画像."""
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目不存在")

    q_service = QuestionService(db)
    is_correct, score = q_service.grade(question, payload.user_answer)

    # 1. 保存答题记录
    answer = Answer(
        user_id=current_user.id,
        question_id=question.id,
        user_answer=payload.user_answer,
        is_correct=is_correct,
        score=score,
    )
    db.add(answer)
    db.commit()

    # 2. 错题入库（含 AI 错误分析，降级为规则模板）
    wrong_question_id = None
    if not is_correct:
        w_service = WrongQuestionService(db)
        wrong = w_service.create_wrong_question(
            current_user, question, payload.user_answer
        )
        wrong_question_id = wrong.id

    # 3. 更新学习画像（增量公式）
    learning = LearningService(db)
    learning.update_mastery_on_answer(
        current_user.id, question.knowledge_point_id, is_correct, question.difficulty
    )
    # 4. 记录学习行为（练习每题按 1 分钟计）
    learning.add_record(
        current_user.id, question.knowledge_point_id, 1, source="practice"
    )

    return AnswerResult(
        is_correct=is_correct,
        score=score,
        correct_answer=question.answer,
        explanation=question.explanation,
        wrong_question_id=wrong_question_id,
    )