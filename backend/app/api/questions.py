"""练习 / 题目 / 答题 API."""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[QuestionOut]:
    """AI 生成练习题（LLM 不可用时自动降级为内置题库）."""
    service = QuestionService(db)

    # 根据掌握度动态决定难度
    mastery_hint = None
    if payload.knowledge_point_id:
        learning = LearningService(db)
        profile = learning.get_or_create_profile(current_user.id, payload.knowledge_point_id)
        mastery_hint = profile.mastery_score if profile.confidence > 0 else None

    try:
        questions = service.generate(
            user=current_user,
            knowledge_point_id=payload.knowledge_point_id,
            subject=payload.subject,
            count=payload.count,
            difficulty=payload.difficulty,
            mastery_hint=mastery_hint,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"生成题目失败：{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="题目生成失败，请稍后再试",
        )

    return [_to_out(q) for q in questions]


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