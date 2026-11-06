"""AES 引擎：把一次加/解密过程组装成完整的 Trace。

本模块是 Trace 的唯一生产者。前端、练习判分、AI 讲解、历史回放全部消费它的输出，
任何模块都不得自行重算算法中间态。
"""

from __future__ import annotations

from app.core.aes import rounds
from app.core.aes.key_expansion import ExpandedKey, expand_key
from app.schemas.trace import (
    AesKeyBits,
    AesMode,
    AesOp,
    CellChange,
    KeyScheduleDetail,
    KeyScheduleRound,
    Step,
    Trace,
)

# 密钥位数 -> (nk, nr)
_KEY_PARAMS: dict[AesKeyBits, tuple[int, int]] = {
    AesKeyBits.BITS_128: (4, 10),
    AesKeyBits.BITS_192: (6, 12),
    AesKeyBits.BITS_256: (8, 14),
}

_OP_LABELS: dict[AesOp, str] = {
    AesOp.SUB_BYTES: "字节替代：每个字节查 S 盒完成非线性替换",
    AesOp.SHIFT_ROWS: "行移位：第 r 行循环左移 r 个字节",
    AesOp.MIX_COLUMNS: "列混合：每列在 GF(2⁸) 上左乘固定矩阵，实现扩散",
    AesOp.ADD_ROUND_KEY: "轮密钥加：状态矩阵与本轮轮密钥逐字节异或",
    AesOp.INV_SUB_BYTES: "逆字节替代：每个字节查逆 S 盒还原",
    AesOp.INV_SHIFT_ROWS: "逆行移位：第 r 行循环右移 r 个字节",
    AesOp.INV_MIX_COLUMNS: "逆列混合：每列左乘逆矩阵还原",
}


def _round_key_matrix(expanded: ExpandedKey, round_index: int) -> list[list[int]]:
    """把第 round_index 轮的 4 个字按列装填为 4×4 轮密钥矩阵。

    密钥扩展中的 W[4*round + c] 对应状态矩阵的第 c 列。
    """
    words = expanded.words[4 * round_index : 4 * round_index + 4]
    return [[words[c][r] for c in range(4)] for r in range(4)]


def _cells(raw: list[dict]) -> list[CellChange]:
    """把 rounds 模块产出的字典明细转成契约模型。"""
    return [CellChange(**item) for item in raw]


def _build_key_schedule(
    expanded: ExpandedKey, nr: int
) -> list[KeyScheduleRound]:
    """按轮打包密钥扩展结果。"""
    schedule: list[KeyScheduleRound] = []
    for r in range(nr + 1):
        words = expanded.words[4 * r : 4 * r + 4]
        detail = expanded.details.get(r)
        schedule.append(
            KeyScheduleRound(
                round=r,
                words=[bytes(w).hex() for w in words],
                detail=None
                if detail is None
                else KeyScheduleDetail(
                    rot_word=detail.rot_word,
                    sub_word=detail.sub_word,
                    rcon=detail.rcon,
                    xor=detail.xor,
                ),
            )
        )
    return schedule


def _encrypt_steps(
    state: list[list[int]], expanded: ExpandedKey, nr: int
) -> tuple[list[Step], list[list[int]]]:
    """生成加密的逐步轨迹，返回步骤列表与最终状态。"""
    steps: list[Step] = []
    index = 0

    def record(
        round_no: int,
        op: AesOp,
        before: list[list[int]],
        after: list[list[int]],
        cells: list[dict],
        round_key: str | None = None,
    ) -> None:
        nonlocal index
        steps.append(
            Step(
                index=index,
                round=round_no,
                op=op,
                state_before=rounds.state_to_hex(before),
                state_after=rounds.state_to_hex(after),
                round_key=round_key,
                cells=_cells(cells),
                explain=f"第 {round_no} 轮 {op.value}：{_OP_LABELS[op]}",
            )
        )
        index += 1

    # 初始轮密钥加
    rk = _round_key_matrix(expanded, 0)
    before = [row[:] for row in state]
    state, cells = rounds.add_round_key(state, rk)
    record(0, AesOp.ADD_ROUND_KEY, before, state, cells, rounds.state_to_hex(rk))

    # 第 1..nr-1 轮：四步完整
    for r in range(1, nr):
        before = [row[:] for row in state]
        state, cells = rounds.sub_bytes(state)
        record(r, AesOp.SUB_BYTES, before, state, cells)

        before = [row[:] for row in state]
        state, cells = rounds.shift_rows(state)
        record(r, AesOp.SHIFT_ROWS, before, state, cells)

        before = [row[:] for row in state]
        state, cells = rounds.mix_columns(state)
        record(r, AesOp.MIX_COLUMNS, before, state, cells)

        before = [row[:] for row in state]
        rk = _round_key_matrix(expanded, r)
        state, cells = rounds.add_round_key(state, rk)
        record(r, AesOp.ADD_ROUND_KEY, before, state, cells, rounds.state_to_hex(rk))

    # 最终轮：无列混合
    before = [row[:] for row in state]
    state, cells = rounds.sub_bytes(state)
    record(nr, AesOp.SUB_BYTES, before, state, cells)

    before = [row[:] for row in state]
    state, cells = rounds.shift_rows(state)
    record(nr, AesOp.SHIFT_ROWS, before, state, cells)

    before = [row[:] for row in state]
    rk = _round_key_matrix(expanded, nr)
    state, cells = rounds.add_round_key(state, rk)
    record(nr, AesOp.ADD_ROUND_KEY, before, state, cells, rounds.state_to_hex(rk))

    return steps, state


# 加密操作 -> 解密操作 的映射
_INVERSE_OP: dict[AesOp, AesOp] = {
    AesOp.ADD_ROUND_KEY: AesOp.ADD_ROUND_KEY,
    AesOp.SUB_BYTES: AesOp.INV_SUB_BYTES,
    AesOp.SHIFT_ROWS: AesOp.INV_SHIFT_ROWS,
    AesOp.MIX_COLUMNS: AesOp.INV_MIX_COLUMNS,
}


def _decrypt_steps(
    ciphertext_state: list[list[int]], expanded: ExpandedKey, nr: int
) -> tuple[list[Step], list[list[int]]]:
    """生成解密的逐步轨迹。

    实现策略：先算出对应明文下的加密步骤，再整体逆序并把操作名换成逆操作，
    同时互换 before/after。这样解密动画与加密动画天然逐帧对应，也不会写错逆向顺序。
    """
    plaintext_state = _decrypt_block(ciphertext_state, expanded, nr)
    enc_steps, _ = _encrypt_steps(plaintext_state, expanded, nr)

    steps: list[Step] = []
    for new_index, enc in enumerate(reversed(enc_steps)):
        op = _INVERSE_OP[enc.op]
        steps.append(
            Step(
                index=new_index,
                round=enc.round,
                op=op,
                state_before=enc.state_after,
                state_after=enc.state_before,
                round_key=enc.round_key,
                cells=[
                    CellChange(
                        row=cell.row,
                        col=cell.col,
                        before=cell.after,
                        after=cell.before,
                        aux=cell.aux,
                    )
                    for cell in enc.cells
                ],
                explain=f"第 {enc.round} 轮 {op.value}：{_OP_LABELS[op]}",
            )
        )
    return steps, plaintext_state


def _decrypt_block(
    ciphertext_state: list[list[int]], expanded: ExpandedKey, nr: int
) -> list[list[int]]:
    """执行解密本体，返回明文状态（供解密轨迹反推使用）。"""
    state = [row[:] for row in ciphertext_state]

    rk = _round_key_matrix(expanded, nr)
    state, _ = rounds.add_round_key(state, rk)

    for r in range(nr - 1, 0, -1):
        state, _ = rounds.inv_shift_rows(state)
        state, _ = rounds.inv_sub_bytes(state)
        rk = _round_key_matrix(expanded, r)
        state, _ = rounds.add_round_key(state, rk)
        state, _ = rounds.inv_mix_columns(state)

    state, _ = rounds.inv_shift_rows(state)
    state, _ = rounds.inv_sub_bytes(state)
    rk = _round_key_matrix(expanded, 0)
    state, _ = rounds.add_round_key(state, rk)

    return state


def encrypt_block(input_hex: str, key_hex: str, key_bits: AesKeyBits) -> bytes:
    """只做加密，返回密文字节（供内部与测试使用）。"""
    nk, nr = _KEY_PARAMS[key_bits]
    expanded = expand_key(bytes.fromhex(key_hex), nk, nr)
    state = rounds.state_from_bytes(bytes.fromhex(input_hex))
    steps, final = _encrypt_steps(state, expanded, nr)
    return rounds.state_to_bytes(final)


def decrypt_block(input_hex: str, key_hex: str, key_bits: AesKeyBits) -> bytes:
    """只做解密，返回明文字节（供内部与测试使用）。"""
    nk, nr = _KEY_PARAMS[key_bits]
    expanded = expand_key(bytes.fromhex(key_hex), nk, nr)
    state = rounds.state_from_bytes(bytes.fromhex(input_hex))
    steps, final = _decrypt_steps(state, expanded, nr)
    return rounds.state_to_bytes(final)


def build_trace(
    input_hex: str,
    key_hex: str,
    key_bits: AesKeyBits,
    mode: AesMode,
) -> Trace:
    """构建完整的加/解密轨迹。

    Args:
        input_hex: 明文（加密）或密文（解密），32 位十六进制。
        key_hex: 密钥，长度与 key_bits 匹配。
        key_bits: 密钥长度。
        mode: 运算方向。

    Returns:
        可直接序列化给前端的 Trace 对象。
    """
    input_hex = input_hex.lower()
    key_hex = key_hex.lower()
    nk, nr = _KEY_PARAMS[key_bits]

    expanded = expand_key(bytes.fromhex(key_hex), nk, nr)
    state = rounds.state_from_bytes(bytes.fromhex(input_hex))

    if mode is AesMode.ENCRYPT:
        steps, final_state = _encrypt_steps(state, expanded, nr)
    else:
        steps, final_state = _decrypt_steps(state, expanded, nr)

    trace = Trace(
        algorithm="AES",
        key_bits=key_bits,
        mode=mode,
        rounds=nr,
        input=input_hex,
        key=key_hex,
        output=rounds.state_to_hex(final_state),
        key_schedule=_build_key_schedule(expanded, nr),
        steps=steps,
    )

    # 首尾一致性自检：这是契约的核心不变量
    assert trace.steps[0].state_before == input_hex, "首步输入状态与 input 不一致"
    assert trace.steps[-1].state_after == trace.output, "末步输出状态与 output 不一致"
    return trace