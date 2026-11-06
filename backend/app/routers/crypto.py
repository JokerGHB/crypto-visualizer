"""加密接口：生成 Trace、提供 S 盒表。

Trace 由 engine 统一生产，本层只做校验与可选的历史落库。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query
from sqlmodel import Session

from app.core.aes.engine import build_trace
from app.core.aes.sbox import INV_SBOX, SBOX
from app.core.errors import KeyLengthError
from app.deps import OptionalUser, SessionDep
from app.models import CryptoSession
from app.schemas.envelope import ok
from app.schemas.trace import AesKeyBits, AesRequest

router = APIRouter(prefix="/api/crypto", tags=["加密"])

# keyBits -> 十六进制字符数
_KEY_HEX_LEN: dict[AesKeyBits, int] = {
    AesKeyBits.BITS_128: 32,
    AesKeyBits.BITS_192: 48,
    AesKeyBits.BITS_256: 64,
}


def _validate(payload: AesRequest) -> tuple[str, str]:
    """校验并归一化输入，返回 (input_hex, key_hex)。

    Raises:
        KeyLengthError: 密钥长度与所选算法不匹配。
    """
    input_hex = payload.input.strip().lower()
    key_hex = payload.key.strip().lower()
    expected = _KEY_HEX_LEN[payload.key_bits]
    if len(key_hex) != expected:
        raise KeyLengthError(
            f"AES-{payload.key_bits.value} 的密钥应为 {expected} 位十六进制字符，"
            f"实际 {len(key_hex)} 位"
        )
    return input_hex, key_hex


def _save_session(
    session: Session,
    user_id: int | None,
    trace,
) -> None:
    """把本次运算写入历史记录。未登录时不落库。"""
    if user_id is None:
        return
    record = CryptoSession(
        user_id=user_id,
        algorithm=trace.algorithm,
        mode=trace.mode.value,
        key_bits=trace.key_bits.value,
        input_hex=trace.input,
        key_hex=trace.key,
        output_hex=trace.output,
        rounds=trace.rounds,
        trace_json=json.dumps(
            json.loads(trace.model_dump_json(by_alias=True)), ensure_ascii=False
        ),
    )
    session.add(record)
    session.commit()


@router.post("/aes")
def compute_aes(
    payload: AesRequest,
    session: SessionDep,
    user: OptionalUser,
) -> dict:
    """执行 AES 加/解密并返回完整 Trace。

    未登录也可使用（返回结果但不写历史）；已登录则自动记录。
    """
    input_hex, key_hex = _validate(payload)
    trace = build_trace(input_hex, key_hex, payload.key_bits, payload.mode)
    _save_session(session, user.id if user else None, trace)
    return ok(json.loads(trace.model_dump_json(by_alias=True)))


@router.get("/sbox")
def get_sbox(inverse: bool = Query(default=False, description="是否返回逆 S 盒")) -> dict:
    """返回 S 盒或逆 S 盒的 16×16 表格。"""
    table = INV_SBOX if inverse else SBOX
    grid = [table[r * 16 : (r + 1) * 16] for r in range(16)]
    return ok({"inverse": inverse, "table": grid})