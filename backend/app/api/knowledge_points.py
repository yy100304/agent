"""知识点 API."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.database.session import get_db
from app.models import KnowledgePoint, User
from app.schemas.question import KnowledgePointOut

router = APIRouter()


@router.get("", response_model=List[KnowledgePointOut])
def list_knowledge_points(
    subject: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[KnowledgePointOut]:
    """知识点列表（练习页/错题筛选使用）."""
    query = db.query(KnowledgePoint)
    if subject:
        query = query.filter(KnowledgePoint.subject == subject)
    points = query.order_by(KnowledgePoint.subject, KnowledgePoint.id).all()
    return [KnowledgePointOut.model_validate(p) for p in points]