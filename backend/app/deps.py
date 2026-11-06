"""FastAPI 依赖：数据库会话与当前用户。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.core.errors import TokenInvalidError
from app.core.security import decode_access_token
from app.database import get_session
from app.models import User

# auto_error=False：自行抛出统一错误，避免 FastAPI 默认的 403 响应格式
_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> User:
    """解析 Bearer 令牌并返回当前用户。"""
    if credentials is None or not credentials.credentials:
        raise TokenInvalidError("未提供登录凭证")
    username = decode_access_token(credentials.credentials)
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise TokenInvalidError("用户不存在")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_user(
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ] = None,
) -> User | None:
    """可选登录：令牌缺失或无效时返回 None，不抛异常。"""
    if credentials is None or not credentials.credentials:
        return None
    try:
        username = decode_access_token(credentials.credentials)
    except Exception:  # noqa: BLE001 - 可选路径不得因令牌问题中断主流程
        return None
    return session.exec(select(User).where(User.username == username)).first()


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_client_ip(request: Request) -> str:
    """取客户端 IP，用于限流。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"