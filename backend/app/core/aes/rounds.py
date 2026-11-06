"""AES 轮函数：字节替代、行移位、列混合、轮密钥加及其逆运算。

状态表示：state[r][c]，r 为行、c 为列，取值 0..255。
展平规则为列主序：flat[4*c + r] == state[r][c]。

所有函数均为纯函数：接受旧状态，返回新状态与逐格变化明细，绝不原地修改入参。
这样 engine 才能安全地保存每一步的 before/after 快照。
"""

from __future__ import annotations

from app.core.aes.gf import gmul, xtime
from app.core.aes.sbox import INV_SBOX, SBOX

# 列混合使用的固定矩阵（FIPS-197 第 5.1.3 节）
MIX_MATRIX: list[list[int]] = [
    [0x02, 0x03, 0x01, 0x01],
    [0x01, 0x02, 0x03, 0x01],
    [0x01, 0x01, 0x02, 0x03],
    [0x03, 0x01, 0x01, 0x02],
]

# 逆列混合矩阵（FIPS-197 第 5.3.3 节）
INV_MIX_MATRIX: list[list[int]] = [
    [0x0E, 0x0B, 0x0D, 0x09],
    [0x09, 0x0E, 0x0B, 0x0D],
    [0x0D, 0x09, 0x0E, 0x0B],
    [0x0B, 0x0D, 0x09, 0x0E],
]


def state_from_bytes(data: bytes) -> list[list[int]]:
    """把 16 字节按列主序装填为 4×4 状态矩阵。"""
    if len(data) != 16:
        raise ValueError(f"分组长度应为 16 字节，实际 {len(data)} 字节")
    return [[data[4 * c + r] for c in range(4)] for r in range(4)]


def state_to_bytes(state: list[list[int]]) -> bytes:
    """把 4×4 状态矩阵按列主序展平为 16 字节。"""
    return bytes(state[r][c] for c in range(4) for r in range(4))


def state_to_hex(state: list[list[int]]) -> str:
    """状态矩阵转 32 位小写十六进制字符串。"""
    return state_to_bytes(state).hex()


def _cell(row: int, col: int, before: int, after: int, aux: str | None) -> dict:
    return {
        "row": row,
        "col": col,
        "before": f"{before:02x}",
        "after": f"{after:02x}",
        "aux": aux,
    }


def sub_bytes(state: list[list[int]]) -> tuple[list[list[int]], list[dict]]:
    """字节替代：每字节查 S 盒。"""
    new = [[0] * 4 for _ in range(4)]
    cells: list[dict] = []
    for r in range(4):
        for c in range(4):
            old = state[r][c]
            new[r][c] = SBOX[old]
            cells.append(_cell(r, c, old, new[r][c], f"sbox[{old:02x}]"))
    return new, cells


def inv_sub_bytes(state: list[list[int]]) -> tuple[list[list[int]], list[dict]]:
    """逆字节替代：每字节查逆 S 盒。"""
    new = [[0] * 4 for _ in range(4)]
    cells: list[dict] = []
    for r in range(4):
        for c in range(4):
            old = state[r][c]
            new[r][c] = INV_SBOX[old]
            cells.append(_cell(r, c, old, new[r][c], f"inv_sbox[{old:02x}]"))
    return new, cells


def shift_rows(state: list[list[int]]) -> tuple[list[list[int]], list[dict]]:
    """行移位：第 r 行循环左移 r 个字节。"""
    new = [[0] * 4 for _ in range(4)]
    cells: list[dict] = []
    for r in range(4):
        for c in range(4):
            src_c = (c + r) % 4
            new[r][c] = state[r][src_c]
            cells.append(
                _cell(
                    r,
                    c,
                    state[r][c],
                    new[r][c],
                    f"from r{r}c{src_c}",
                )
            )
    return new, cells


def inv_shift_rows(state: list[list[int]]) -> tuple[list[list[int]], list[dict]]:
    """逆行移位：第 r 行循环右移 r 个字节。"""
    new = [[0] * 4 for _ in range(4)]
    cells: list[dict] = []
    for r in range(4):
        for c in range(4):
            src_c = (c - r) % 4
            new[r][c] = state[r][src_c]
            cells.append(
                _cell(
                    r,
                    c,
                    state[r][c],
                    new[r][c],
                    f"from r{r}c{src_c}",
                )
            )
    return new, cells


def _mix_columns_with(
    state: list[list[int]], matrix: list[list[int]], inverse: bool
) -> tuple[list[list[int]], list[dict]]:
    """列混合通用实现：每列左乘固定矩阵。"""
    new = [[0] * 4 for _ in range(4)]
    cells: list[dict] = []
    for c in range(4):
        column = [state[r][c] for r in range(4)]
        for r in range(4):
            value = 0
            for k in range(4):
                value ^= gmul(column[k], matrix[r][k])
            new[r][c] = value

            # aux 展示该格的主乘项：正向取首个非 1 系数，逆向取首个非 1 系数
            coeff = matrix[r][0]
            if coeff in (0x02, 0x0E):
                aux = f"xtime({column[0]:02x})={xtime(column[0]):02x}"
            else:
                aux = f"gf_mul({column[0]:02x},{coeff:02x})={gmul(column[0], coeff):02x}"
            cells.append(_cell(r, c, column[r], value, aux))
    return new, cells


def mix_columns(state: list[list[int]]) -> tuple[list[list[int]], list[dict]]:
    """列混合：每列在 GF(2^8) 上左乘固定矩阵。"""
    return _mix_columns_with(state, MIX_MATRIX, False)


def inv_mix_columns(state: list[list[int]]) -> tuple[list[list[int]], list[dict]]:
    """逆列混合。"""
    return _mix_columns_with(state, INV_MIX_MATRIX, True)


def add_round_key(
    state: list[list[int]], round_key: list[list[int]]
) -> tuple[list[list[int]], list[dict]]:
    """轮密钥加：状态矩阵与轮密钥逐字节异或。"""
    new = [[0] * 4 for _ in range(4)]
    cells: list[dict] = []
    for r in range(4):
        for c in range(4):
            k = round_key[r][c]
            new[r][c] = state[r][c] ^ k
            cells.append(_cell(r, c, state[r][c], new[r][c], f"{k:02x}"))
    return new, cells