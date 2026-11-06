"""数据库引擎与会话管理。

开发默认 SQLite（零配置），生产通过 DATABASE_URL 切 MySQL。
本期不引入 Alembic，建表用 SQLModel.metadata.create_all，理由见 design.md。
"""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

# SQLite 需要关闭同线程检查（FastAPI 的依赖注入会跨线程）
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)
# echo=False 避免日志噪音；pool_pre_ping 让 MySQL 空闲断连后自动重连
engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=_connect_args,
    pool_pre_ping=True,
)


def init_db() -> None:
    """创建所有表。幂等，可重复调用。"""
    # 触发模型注册
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供数据库会话。"""
    with Session(engine) as session:
        yield session