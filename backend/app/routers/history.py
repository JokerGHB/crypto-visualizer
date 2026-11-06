"""历史记录接口。

安全要点：所有读写都按 user_id 过滤；访问他人记录一律返回 404，
不区分"不存在"与"无权访问"，避免泄露资源存在性。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query, status
from sqlmodel import func, select

from app.core.errors import NotFoundError
from app.deps import CurrentUser, SessionDep
from app.models import CryptoSession
from app.schemas.envelope import ok

router = APIRouter(prefix="/api/history", tags=["历史记录"])


def _summary(row: CryptoSession) -> dict:
    """列表项摘要，不含完整 trace 以减小响应体积。"""
    return {
        "id": row.id,
        "algorithm": row.algorithm,
        "mode": row.mode,
        "keyBits": row.key_bits,
        "input": row.input_hex,
        "key": row.key_hex,
        "output": row.output_hex,
        "rounds": row.rounds,
        "createdAt": row.created_at.isoformat(),
    }


def _own_session(session, session_id: int, user_id: int) -> CryptoSession:
    """取出属于该用户的记录。

    Raises:
        NotFoundError: 记录不存在或不属于该用户。
    """
    row = session.get(CryptoSession, session_id)
    if row is None or row.user_id != user_id:
        raise NotFoundError("记录不存在")
    return row


@router.get("/sessions")
def list_sessions(
    session: SessionDep,
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """分页列出当前用户的历史记录。"""
    total = session.exec(
        select(func.count())
        .select_from(CryptoSession)
        .where(CryptoSession.user_id == user.id)
    ).one()

    rows = session.exec(
        select(CryptoSession)
        .where(CryptoSession.user_id == user.id)
        .order_by(CryptoSession.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    return ok(
        {
            "items": [_summary(r) for r in rows],
            "total": total,
            "page": page,
            "size": size,
        }
    )


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: int, session: SessionDep, user: CurrentUser
) -> dict:
    """读取单条记录并返回完整 Trace 供回放。"""
    row = _own_session(session, session_id, user.id)
    return ok(
        {
            "meta": _summary(row),
            "trace": json.loads(row.trace_json),
        }
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int, session: SessionDep, user: CurrentUser
) -> None:
    """删除本人记录。"""
    row = _own_session(session, session_id, user.id)
    session.delete(row)
    session.commit()