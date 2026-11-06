"""用户名口令注册 / 登录。

登录成功后签发 JWT，前端放 Authorization: Bearer <token>。
不使用 Cookie 会话，因此天然规避 CSRF（见 design.md 安全设计）。
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.core.errors import AuthFailedError, UserExistsError
from app.core.security import (
    BCRYPT_MAX_BYTES,
    create_access_token,
    hash_password,
    verify_password,
)
from app.deps import CurrentUser, SessionDep
from app.models import User
from app.schemas.envelope import ok

router = APIRouter(prefix="/api/auth", tags=["认证"])


class RegisterRequest(BaseModel):
    """注册请求。"""

    username: str = Field(
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9_\u4e00-\u9fa5]+$",
        description="3-32 位字母、数字、下划线或中文",
    )
    password: str = Field(min_length=6, max_length=BCRYPT_MAX_BYTES)


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=BCRYPT_MAX_BYTES)


def _public_user(user: User) -> dict:
    """只暴露非敏感字段。"""
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "createdAt": user.created_at.isoformat(),
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: SessionDep) -> dict:
    """注册新用户。"""
    exists = session.exec(
        select(User).where(User.username == payload.username)
    ).first()
    if exists is not None:
        raise UserExistsError()

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role="student",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return ok(_public_user(user))


@router.post("/login")
def login(payload: LoginRequest, session: SessionDep) -> dict:
    """登录并返回访问令牌。"""
    user = session.exec(
        select(User).where(User.username == payload.username)
    ).first()
    # 无论用户不存在还是口令错误，均返回同一错误，避免枚举用户名
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthFailedError()

    token = create_access_token(user.username)
    return ok(
        {
            "accessToken": token,
            "tokenType": "bearer",
            "user": _public_user(user),
        }
    )


@router.get("/me")
def me(current_user: CurrentUser) -> dict:
    """返回当前登录用户信息。"""
    return ok(_public_user(current_user))