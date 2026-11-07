"""错题集 API."""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import Question, User
from app.schemas.question import QuestionOut
from app.schemas.wrong_question import (
    MasterResult,
    WrongQuestionDetail,
    WrongQuestionListResponse,
)
from app.services.wrong_question_service import WrongQuestionService

router = APIRouter()


@router.get("", response_model=WrongQuestionListResponse)
def list_wrong_questions(
    subject: Optional[str] = Query(default="all"),
    knowledge_point_id: Optional[int] = Query(default=None),
    wrong_status: Optional[str] = Query(default="all", alias="status"),
    difficulty: Optional[str] = Query(default="all"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> WrongQuestionListResponse:
    """错题列表：支持按科目/知识点/状态/难度筛选."""
    service = WrongQuestionService(db)
    items = service.list_wrong_questions(
        current_user,
        subject=subject,
        knowledge_point_id=knowledge_point_id,
        status=wrong_status,
        difficulty=difficulty,
    )
    stats = service.get_stats(current_user)
    return WrongQuestionListResponse(
        stats=stats,  # type: ignore[arg-type]
        items=items,  # type: ignore[arg-type]
    )


@router.get("/{wrong_id}", response_model=WrongQuestionDetail)
def get_wrong_question_detail(
    wrong_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> WrongQuestionDetail:
    """错题详情：原题 / 我的答案 / 正确答案 / AI 解析 / 错误原因 / 学习建议."""
    service = WrongQuestionService(db)
    detail = service.get_detail(current_user, wrong_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="错题不存在")
    return WrongQuestionDetail(**detail)


@router.put("/{wrong_id}/master", response_model=MasterResult)
def mark_mastered(
    wrong_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> MasterResult:
    """标记已掌握：mastered=true，画像掌握度温和 +5%."""
    service = WrongQuestionService(db)
    result = service.mark_mastered(current_user, wrong_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="错题不存在")
    return MasterResult(
        success=True,
        new_mastery=result["new_mastery"],
        message=f"已标记为掌握，该知识点掌握度提升至 {round(result['new_mastery'] * 100)}%",
    )


@router.post("/{wrong_id}/practice", response_model=List[QuestionOut])
def practice_similar(
    wrong_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[QuestionOut]:
    """重新练习：根据错题知识点/难度/掌握度生成类似题."""
    service = WrongQuestionService(db)
    try:
        questions = service.similar_questions(current_user, wrong_id, count=3)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception(f"生成类似题失败：{e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成类似题失败，请稍后再试",
        )

    return [
        QuestionOut(
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
        for q in questions
    ]