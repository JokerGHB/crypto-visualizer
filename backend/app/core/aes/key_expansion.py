"""AES 密钥扩展（Key Expansion）。

依据 FIPS-197 第 5.2 节。输入初始密钥，产出 4*(Nr+1) 个 4 字节字，
并按轮分组返回，同时记录每轮轮密钥生成过程中 RotWord / SubWord / Rcon / XOR
四步的中间量，供前端可视化使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.aes.sbox import RCON, SBOX


def _rot_word(word: list[int]) -> list[int]:
    """循环左移一个字节：[a0,a1,a2,a3] -> [a1,a2,a3,a0]。"""
    return word[1:] + word[:1]


def _sub_word(word: list[int]) -> list[int]:
    """对 4 个字节逐个查 S 盒。"""
    return [SBOX[b] for b in word]


@dataclass
class ExpansionDetail:
    """某一轮轮密钥生成的四步中间量（十六进制）。"""

    rot_word: str
    sub_word: str
    rcon: str
    xor: str


@dataclass
class ExpandedKey:
    """密钥扩展结果。"""

    words: list[list[int]] = field(default_factory=list)
    details: dict[int, ExpansionDetail] = field(default_factory=dict)
    """键为轮次，值为该轮首个字的生成明细；第 0 轮无明细。"""


def expand_key(key: bytes, nk: int, nr: int) -> ExpandedKey:
    """执行密钥扩展。

    Args:
        key: 初始密钥字节，长度必须为 4*nk。
        nk: 密钥字个数，128 位为 4，192 位为 6，256 位为 8。
        nr: 轮数，128 位为 10，192 位为 12，256 位为 14。

    Returns:
        ExpandedKey，含全部轮密钥字与各轮生成明细。

    Raises:
        ValueError: 密钥长度与 nk 不符。
    """
    if len(key) != 4 * nk:
        raise ValueError(f"密钥长度应为 {4 * nk} 字节，实际 {len(key)} 字节")

    # 初始 nk 个字直接取自密钥
    words: list[list[int]] = [list(key[4 * i : 4 * i + 4]) for i in range(nk)]
    details: dict[int, ExpansionDetail] = {}
    total = 4 * (nr + 1)
    rcon_index = 0

    for i in range(nk, total):
        temp = list(words[i - 1])
        detail: ExpansionDetail | None = None

        if i % nk == 0:
            rot = _rot_word(temp)
            sub = _sub_word(rot)
            rcon_byte = RCON[rcon_index]
            rcon_index += 1
            sub[0] ^= rcon_byte
            detail = ExpansionDetail(
                rot_word=bytes(rot).hex(),
                sub_word=bytes(_sub_word(rot)).hex(),
                rcon=bytes([rcon_byte, 0, 0, 0]).hex(),
                xor=bytes(sub).hex(),
            )
            temp = sub
        elif nk > 6 and i % nk == 4:
            # AES-256 专有分支：只做 SubWord，不加 Rcon
            sub = _sub_word(temp)
            detail = ExpansionDetail(
                rot_word=bytes(temp).hex(),
                sub_word=bytes(sub).hex(),
                rcon=(0).to_bytes(4, "big").hex(),
                xor=bytes(sub).hex(),
            )
            temp = sub

        new_word = [a ^ b for a, b in zip(words[i - nk], temp)]
        words.append(new_word)

        # detail 产生于每 nk 个字的第一个字，其所属轮次由字下标决定：
        # 单词下标 i 属于第 i//4 轮轮密钥（W[4r..4r+3]）
        if detail is not None:
            details[i // 4] = detail

    return ExpandedKey(words=words, details=details)


def round_key_words(expanded: ExpandedKey, round_index: int) -> list[list[int]]:
    """取出第 round_index 轮的 4 个字。"""
    start = 4 * round_index
    return expanded.words[start : start + 4]