"""登录注册相关 API."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.security import create_access_token
from app.database.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, Token
from app.schemas.user import UserOut
from app.services.user_service import UserService

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> Token:
    """注册新用户."""
    service = UserService(db)

    # 唯一性校验
    if service.get_by_username(payload.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被占用",
        )
    if payload.email and service.get_by_email(payload.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册",
        )

    try:
        user = service.create_user(payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="注册失败，请稍后再试",
        )

    token = create_access_token(subject=user.id)
    return Token(access_token=token, user_id=user.id, username=user.username)


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """登录."""
    service = UserService(db)
    user = service.authenticate(payload)

    if not user:
        logger.warning(f"登录失败：{payload.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    token = create_access_token(subject=user.id)
    logger.info(f"用户登录成功：{user.username}")
    return Token(access_token=token, user_id=user.id, username=user.username)