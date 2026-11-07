"""用户相关 Schema."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None


class UserOut(UserBase):
    """对外暴露的用户信息."""

    id: int
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """更新用户信息."""

    email: Optional[EmailStr] = None
    avatar: Optional[str] = None