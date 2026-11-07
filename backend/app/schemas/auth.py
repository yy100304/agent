"""鉴权相关 Schema."""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求."""

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=64)
    email: Optional[EmailStr] = None


class LoginRequest(BaseModel):
    """登录请求."""

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=64)


class Token(BaseModel):
    """登录响应."""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str