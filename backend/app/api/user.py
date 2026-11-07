"""用户相关 API."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_user
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate
from app.database.session import get_db
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/profile", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_active_user)) -> UserOut:
    """获取当前登录用户信息."""
    return UserOut.model_validate(current_user)


@router.put("/profile", response_model=UserOut)
def update_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """更新当前用户资料（仅支持 email / avatar）."""
    if payload.email is not None:
        current_user.email = payload.email
    if payload.avatar is not None:
        current_user.avatar = payload.avatar
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)