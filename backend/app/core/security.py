"""安全基础：口令散列与 JWT 编解码。

注意：本项目直接使用 bcrypt 库，不使用 passlib。
原因：passlib 1.7.4 与 bcrypt 5.x 不兼容（读取已移除的 bcrypt.__about__.__version__），
会抛 ValueError，且其对超长口令的处理与 bcrypt 5 冲突。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

# bcrypt 只处理前 72 字节，超长口令必须显式拒绝而不是静默截断
BCRYPT_MAX_BYTES = 72
# cost=12 在安全性与登录耗时之间取平衡
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """生成 bcrypt 口令散列。

    Raises:
        ValueError: 口令超过 72 字节，或为空。
    """
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        raise ValueError(f"口令不得超过 {BCRYPT_MAX_BYTES} 字节")
    if not raw:
        raise ValueError("口令不得为空")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验口令。任何异常均视为校验失败，不向上抛出。"""
    try:
        raw = password.encode("utf-8")
        if len(raw) > BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str) -> str:
    """签发 JWT，subject 为用户名。"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> str:
    """解码 JWT，返回用户名。

    Raises:
        TokenInvalidError: 令牌无效或已过期。
    """
    from app.core.errors import TokenInvalidError

    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise TokenInvalidError() from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenInvalidError()
    return subject