"""科目 API：列表（带内容统计）与新增.

科目名称是各模块之间的连接键：
- 知识点 / 题目 → `knowledge_points.subject`
- 学习计划 → `study_plans.subject`
- 知识库资料 → `knowledge_documents.subject`
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.logging import logger
from app.database.session import get_db
from app.models import (
    KnowledgeDocument,
    KnowledgePoint,
    Question,
    StudyPlan,
    Subject,
    User,
)

router = APIRouter()

# 内置科目（新环境/空库时至少可用）
DEFAULT_SUBJECTS = ("离散数学", "数据结构", "高等数学", "英语")


class SubjectOut(BaseModel):
    name: str
    custom: bool = False
    knowledge_points: int = 0
    questions: int = 0
    plans: int = 0
    documents: int = 0


class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)


def _count_by_name(db: Session, column, *extra_filters) -> dict[str, int]:
    rows = (
        db.query(column, func.count())
        .filter(*extra_filters)
        .group_by(column)
        .all()
    )
    return {name: count for name, count in rows if name}


@router.get("", response_model=List[SubjectOut])
def list_subjects(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[SubjectOut]:
    """科目列表：自建科目 + 知识点/计划/资料中出现的科目，并带内容统计."""
    kp_counts = _count_by_name(db, KnowledgePoint.subject)
    # 题目数需要 join，单独统计
    q_rows = (
        db.query(KnowledgePoint.subject, func.count(Question.id))
        .join(Question, Question.knowledge_point_id == KnowledgePoint.id)
        .group_by(KnowledgePoint.subject)
        .all()
    )
    question_counts = {name: count for name, count in q_rows if name}

    plan_counts = _count_by_name(
        db, StudyPlan.subject, StudyPlan.user_id == current_user.id
    )
    doc_counts = _count_by_name(
        db,
        KnowledgeDocument.subject,
        KnowledgeDocument.user_id == current_user.id,
    )

    custom_names = {s.name for s in db.query(Subject).all()}
    names = list(DEFAULT_SUBJECTS) + sorted(
        custom_names
        | set(kp_counts) | set(plan_counts) | set(doc_counts)
    )
    seen: set[str] = set()
    result: List[SubjectOut] = []
    for name in names:
        key = name.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(SubjectOut(
            name=key,
            custom=key in custom_names,
            knowledge_points=kp_counts.get(key, 0),
            questions=question_counts.get(key, 0),
            plans=plan_counts.get(key, 0),
            documents=doc_counts.get(key, 0),
        ))
    # 有内容的科目优先，其次按名称
    result.sort(key=lambda s: (-(s.knowledge_points + s.plans + s.documents),
                               not s.custom, s.name))
    return result


@router.post("", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> SubjectOut:
    """新增科目（重名直接返回已有科目，名称 1~20 字）."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="科目名称不能为空")

    exists = db.query(Subject).filter(func.lower(Subject.name) == name.lower()).first()
    if exists:
        return SubjectOut(name=exists.name, custom=True)

    subject = Subject(name=name, custom=1)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    logger.info(f"新增科目 user={current_user.id} name={name}")
    return SubjectOut(name=subject.name, custom=True)
