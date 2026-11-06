"""GF(2^8) 有限域运算。

AES 在 GF(2^8) 上以不可约多项式 x^8 + x^4 + x^3 + x + 1（即 0x11b）构造。
本模块只提供最基础的两个运算，列混合、密钥扩展与 S 盒推导均基于它们。
"""

from __future__ import annotations

# 不可约多项式 x^8 + x^4 + x^3 + x + 1 的低 8 位
AES_MOD_POLY: int = 0x1B


def xtime(b: int) -> int:
    """在 GF(2^8) 中乘以 2（即 x）。

    左移一位；若原最高位为 1，则与 0x1b 异或完成模约简。
    """
    b <<= 1
    if b & 0x100:
        b ^= 0x1B
    return b & 0xFF


def gmul(a: int, b: int) -> int:
    """在 GF(2^8) 中乘法（俄罗斯农民乘法）。

    逐位检查 b 的每一位，为 1 则异或累加 a 的当前值，
    每轮 a 乘 2（xtime），b 右移一位。
    """
    product = 0
    for _ in range(8):
        if b & 1:
            product ^= a
        a = xtime(a)
        b >>= 1
    return product


def ginv(a: int) -> int:
    """在 GF(2^8) 中求乘法逆元。0 的逆元定义为 0（供 S 盒推导使用）。

    以暴力查找实现，仅用于测试对照与 S 盒推导，不在加解密热路径上调用。
    """
    if a == 0:
        return 0
    for x in range(1, 256):
        if gmul(a, x) == 1:
            return x
    raise ValueError(f"{a:#04x} 在 GF(2^8) 中不存在乘法逆元")