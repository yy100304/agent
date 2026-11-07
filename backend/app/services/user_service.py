"""用户业务逻辑."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


class UserService:
    """用户相关的服务封装."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- CRUD ----

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, payload: RegisterRequest) -> User:
        """创建新用户."""
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"创建用户成功：{user.username} (id={user.id})")
        return user

    def authenticate(self, payload: LoginRequest) -> Optional[User]:
        """验证用户名密码."""
        user = self.get_by_username(payload.username)
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(payload.password, user.password_hash):
            return None

        # 更新最后登录时间
        user.last_login_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user