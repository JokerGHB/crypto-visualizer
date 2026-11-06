"""AES 引擎单元测试。

覆盖：FIPS-197 标准对拍、步数、列主序、加解密互逆、雪崩、S 盒推导复核、
MixColumns 手算验证、Trace 契约不变量。
"""

from __future__ import annotations

import random

import pytest

from app.core.aes.engine import build_trace, decrypt_block, encrypt_block
from app.core.aes.gf import ginv, gmul, xtime
from app.core.aes.rounds import state_from_bytes, state_to_bytes
from app.core.aes.sbox import INV_SBOX, SBOX
from app.schemas.trace import AesKeyBits, AesMode

# FIPS-197 标准测试向量：(key_bits, key, plaintext, expected_ciphertext)
FIPS197_VECTORS = [
    (
        AesKeyBits.BITS_128,
        "2b7e151628aed2a6abf7158809cf4f3c",
        "3243f6a8885a308d313198a2e0370734",
        "3925841d02dc09fbdc118597196a0b32",
    ),
    (
        AesKeyBits.BITS_128,
        "00000000000000000000000000000000",
        "00000000000000000000000000000000",
        "66e94bd4ef8a2c3b884cfa59ca342b2e",
    ),
    (
        AesKeyBits.BITS_192,
        "000102030405060708090a0b0c0d0e0f1011121314151617",
        "00112233445566778899aabbccddeeff",
        "dda97ca4864cdfe06eaf70a0ec0d7191",
    ),
    (
        AesKeyBits.BITS_256,
        "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
        "00112233445566778899aabbccddeeff",
        "8ea2b7ca516745bfeafc49904b496089",
    ),
]


class TestFips197Vectors:
    """FIPS-197 标准向量对拍，这是算法正确性的黄金标准。"""

    @pytest.mark.parametrize("key_bits,key,plaintext,expected", FIPS197_VECTORS)
    def test_encrypt_matches_standard(self, key_bits, key, plaintext, expected):
        assert encrypt_block(plaintext, key, key_bits).hex() == expected

    @pytest.mark.parametrize("key_bits,key,plaintext,expected", FIPS197_VECTORS)
    def test_decrypt_matches_standard(self, key_bits, key, plaintext, expected):
        assert decrypt_block(expected, key, key_bits).hex() == plaintext

    @pytest.mark.parametrize("key_bits,key,plaintext,expected", FIPS197_VECTORS)
    def test_trace_output_field(self, key_bits, key, plaintext, expected):
        trace = build_trace(plaintext, key, key_bits, AesMode.ENCRYPT)
        assert trace.output == expected


class TestStepCounts:
    """步数必须精确，播放器边界依赖它。"""

    @pytest.mark.parametrize(
        "key_bits,expected_steps,expected_rounds",
        [
            (AesKeyBits.BITS_128, 40, 10),
            (AesKeyBits.BITS_192, 48, 12),
            (AesKeyBits.BITS_256, 56, 14),
        ],
    )
    def test_encrypt_step_count(self, key_bits, expected_steps, expected_rounds):
        key = "00" * (key_bits.value // 8)
        trace = build_trace("00" * 16, key, key_bits, AesMode.ENCRYPT)
        assert trace.rounds == expected_rounds
        assert len(trace.steps) == expected_steps
        # index 必须等于数组下标
        assert [s.index for s in trace.steps] == list(range(expected_steps))

    @pytest.mark.parametrize(
        "key_bits,expected_steps",
        [(AesKeyBits.BITS_128, 40), (AesKeyBits.BITS_192, 48), (AesKeyBits.BITS_256, 56)],
    )
    def test_decrypt_step_count(self, key_bits, expected_steps):
        key = "00" * (key_bits.value // 8)
        trace = build_trace("00" * 16, key, key_bits, AesMode.DECRYPT)
        assert len(trace.steps) == expected_steps


class TestColumnMajor:
    """列主序映射，最常见的实现错误来源。"""

    def test_state_fills_by_column(self):
        data = bytes.fromhex("00112233445566778899aabbccddeeff")
        state = state_from_bytes(data)
        assert state[0][0] == 0x00
        assert state[1][0] == 0x11
        assert state[2][0] == 0x22
        assert state[3][0] == 0x33
        assert state[0][1] == 0x44

    def test_roundtrip(self):
        data = bytes(range(16))
        assert state_to_bytes(state_from_bytes(data)) == data


class TestTraceInvariants:
    """Trace 契约的核心不变量。"""

    @pytest.mark.parametrize("key_bits,key,plaintext,expected", FIPS197_VECTORS)
    def test_first_and_last_state(self, key_bits, key, plaintext, expected):
        trace = build_trace(plaintext, key, key_bits, AesMode.ENCRYPT)
        assert trace.steps[0].state_before == plaintext
        assert trace.steps[-1].state_after == expected

    @pytest.mark.parametrize("key_bits,key,plaintext,expected", FIPS197_VECTORS)
    def test_states_chain_continuously(self, key_bits, key, plaintext, expected):
        """相邻步骤必须首尾相接，否则动画会跳变。"""
        trace = build_trace(plaintext, key, key_bits, AesMode.ENCRYPT)
        for prev, nxt in zip(trace.steps, trace.steps[1:]):
            assert prev.state_after == nxt.state_before

    @pytest.mark.parametrize("key_bits,key,plaintext,expected", FIPS197_VECTORS)
    def test_decrypt_chain_continuously(self, key_bits, key, plaintext, expected):
        trace = build_trace(expected, key, key_bits, AesMode.DECRYPT)
        assert trace.steps[0].state_before == expected
        assert trace.steps[-1].state_after == plaintext
        for prev, nxt in zip(trace.steps, trace.steps[1:]):
            assert prev.state_after == nxt.state_before

    def test_key_schedule_length(self):
        # 密钥扩展的 detail 只在 i % nk == 0（或 AES-256 的 i % nk == 4）时产生。
        # 由于每轮轮密钥占 4 个字、而 nk 分别为 4/6/8，轮边界与 nk 并不总是对齐，
        # 因此并非每一轮都有 detail。以下为实测确认的正确分布。
        expectations = [
            (AesKeyBits.BITS_128, 10, 1, list(range(1, 11))),
            (AesKeyBits.BITS_192, 12, 1, [1, 3, 4, 6, 7, 9, 10, 12]),
            (AesKeyBits.BITS_256, 14, 2, list(range(2, 15))),
        ]
        for key_bits, expected_rounds, first_detail_round, detail_rounds in expectations:
            key = "ab" * (key_bits.value // 8)
            trace = build_trace("00" * 16, key, key_bits, AesMode.ENCRYPT)
            assert len(trace.key_schedule) == expected_rounds + 1
            assert trace.key_schedule[0].detail is None
            assert trace.key_schedule[first_detail_round].detail is not None
            actual = sorted(r.round for r in trace.key_schedule if r.detail is not None)
            assert actual == detail_rounds

    def test_final_round_has_no_mix_columns(self):
        key = "2b7e151628aed2a6abf7158809cf4f3c"
        trace = build_trace("3243f6a8885a308d313198a2e0370734", key, AesKeyBits.BITS_128, AesMode.ENCRYPT)
        last_round_ops = [s.op.value for s in trace.steps if s.round == trace.rounds]
        assert "MixColumns" not in last_round_ops
        assert last_round_ops == ["SubBytes", "ShiftRows", "AddRoundKey"]

    def test_each_round_has_four_ops(self):
        key = "2b7e151628aed2a6abf7158809cf4f3c"
        trace = build_trace("3243f6a8885a308d313198a2e0370734", key, AesKeyBits.BITS_128, AesMode.ENCRYPT)
        for r in range(1, trace.rounds):
            ops = [s.op.value for s in trace.steps if s.round == r]
            assert ops == ["SubBytes", "ShiftRows", "MixColumns", "AddRoundKey"]

    def test_cells_cover_all_16_byte_positions(self):
        """每步的 cells 必须覆盖 16 个字节位置。"""
        key = "2b7e151628aed2a6abf7158809cf4f3c"
        trace = build_trace("3243f6a8885a308d313198a2e0370734", key, AesKeyBits.BITS_128, AesMode.ENCRYPT)
        for step in trace.steps:
            assert len(step.cells) == 16
            positions = {(c.row, c.col) for c in step.cells}
            assert len(positions) == 16

    def test_round_key_only_on_add_round_key(self):
        key = "2b7e151628aed2a6abf7158809cf4f3c"
        trace = build_trace("3243f6a8885a308d313198a2e0370734", key, AesKeyBits.BITS_128, AesMode.ENCRYPT)
        for step in trace.steps:
            if step.op.value == "AddRoundKey":
                assert step.round_key is not None
                assert len(step.round_key) == 32
            else:
                assert step.round_key is None


class TestRoundTrip:
    """加解密互逆性。"""

    def test_random_roundtrip(self):
        rng = random.Random(20261102)
        for _ in range(100):
            key_bits = rng.choice(list(AesKeyBits))
            key = bytes(rng.getrandbits(8) for _ in range(key_bits.value // 8)).hex()
            plaintext = bytes(rng.getrandbits(8) for _ in range(16)).hex()
            ciphertext = encrypt_block(plaintext, key, key_bits).hex()
            recovered = decrypt_block(ciphertext, key, key_bits).hex()
            assert recovered == plaintext


class TestAvalanche:
    """雪崩效应：改明文一位，密文应大幅改变。"""

    def test_average_diffusion(self):
        rng = random.Random(7)
        key = "2b7e151628aed2a6abf7158809cf4f3c"
        total_diff = 0
        trials = 100
        for _ in range(trials):
            plaintext = bytearray(rng.getrandbits(8) for _ in range(16))
            flipped = bytearray(plaintext)
            flipped[0] ^= 0x01
            c1 = encrypt_block(plaintext.hex(), key, AesKeyBits.BITS_128)
            c2 = encrypt_block(flipped.hex(), key, AesKeyBits.BITS_128)
            total_diff += sum(bin(a ^ b).count("1") for a, b in zip(c1, c2))
        average = total_diff / trials
        # 理论期望 64 位，实测允许波动
        assert average >= 56, f"雪崩平均值 {average:.1f} 位偏低"


class TestSbox:
    """S 盒正确性：锚点值 + 独立推导复核。"""

    def test_anchor_values(self):
        assert SBOX[0x00] == 0x63
        assert SBOX[0x01] == 0x7C
        assert SBOX[0x53] == 0xED
        assert SBOX[0x19] == 0xD4
        assert INV_SBOX[0xD4] == 0x19

    def test_sbox_matches_derivation(self):
        """用独立的仿射变换重新推导全表，与硬编码值逐一比对。"""

        def rotl8(x: int, n: int) -> int:
            return ((x << n) | (x >> (8 - n))) & 0xFF

        for a in range(256):
            b = ginv(a)
            derived = (
                b
                ^ rotl8(b, 1)
                ^ rotl8(b, 2)
                ^ rotl8(b, 3)
                ^ rotl8(b, 4)
                ^ 0x63
            )
            assert derived == SBOX[a], f"SBOX[{a:#04x}] 推导值 {derived:#04x} 不符"

    def test_inverse_consistency(self):
        for a in range(256):
            assert INV_SBOX[SBOX[a]] == a


class TestGaloisField:
    """GF(2^8) 运算。"""

    def test_xtime(self):
        assert xtime(0x57) == 0xAE
        assert xtime(0xAE) == 0x47
        assert xtime(0x80) == 0x1B

    def test_gmul_known_values(self):
        assert gmul(0x57, 0x83) == 0xC1
        assert gmul(0x57, 0x13) == 0xFE
        assert gmul(0x00, 0xAB) == 0x00
        assert gmul(0x01, 0xAB) == 0xAB

    def test_gmul_commutative(self):
        for a in (0x00, 0x01, 0x57, 0xFF, 0x80):
            for b in (0x00, 0x13, 0x83, 0xAB):
                assert gmul(a, b) == gmul(b, a)


class TestMixColumns:
    """列混合手算验证。"""

    def test_known_column(self):
        """FIPS-197 第 5.1.3 节示例：列 db 13 53 45 -> 8e 4d a1 bc。"""
        from app.core.aes.rounds import mix_columns

        state = [
            [0xDB, 0, 0, 0],
            [0x13, 0, 0, 0],
            [0x53, 0, 0, 0],
            [0x45, 0, 0, 0],
        ]
        new, _ = mix_columns(state)
        assert [new[r][0] for r in range(4)] == [0x8E, 0x4D, 0xA1, 0xBC]

    def test_inverse_roundtrip(self):
        from app.core.aes.rounds import inv_mix_columns, mix_columns

        state = [[(r * 4 + c) * 0x11 & 0xFF for c in range(4)] for r in range(4)]
        mixed, _ = mix_columns(state)
        restored, _ = inv_mix_columns(mixed)
        assert restored == state


class TestShiftRows:
    """行移位方向验证。"""

    def test_shift_rows_moves_left(self):
        from app.core.aes.rounds import shift_rows

        # 用 (r,c) 编码便于追踪来源；rows 模块要求字节值，此处只验证位移逻辑，
        # 故用可区分的 0..255 数值代替元组
        state = [[(r * 4 + c) for c in range(4)] for r in range(4)]
        new, _ = shift_rows(state)
        # 第 0 行不动
        assert new[0] == [0, 1, 2, 3]
        # 第 1 行左移 1：新 c0 来自旧 c1
        assert new[1][0] == state[1][1]
        # 第 2 行左移 2
        assert new[2][0] == state[2][2]
        # 第 3 行左移 3
        assert new[3][0] == state[3][3]
        # 完整第 1 行：[5,6,7,4]
        assert new[1] == [5, 6, 7, 4]

    def test_inverse_restores(self):
        from app.core.aes.rounds import inv_shift_rows, shift_rows

        state = [[(r * 4 + c) for c in range(4)] for r in range(4)]
        shifted, _ = shift_rows(state)
        restored, _ = inv_shift_rows(shifted)
        assert restored == state


class TestKeyExpansion:
    """密钥扩展对照 FIPS-197 附录 A。"""

    def test_aes128_expansion(self):
        """FIPS-197 附录 A.1：第一轮 4 个字应为已知值。"""
        from app.core.aes.key_expansion import expand_key

        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        expanded = expand_key(key, nk=4, nr=10)
        assert [bytes(w).hex() for w in expanded.words[4:8]] == [
            "a0fafe17",
            "88542cb1",
            "23a33939",
            "2a6c7605",
        ]
        assert len(expanded.words) == 44

    def test_detail_present_from_round_one(self):
        from app.core.aes.key_expansion import expand_key

        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        expanded = expand_key(key, nk=4, nr=10)
        assert 0 not in expanded.details
        assert 1 in expanded.details
        # 第 1 轮详细过程（FIPS-197 附录 A.1）：
        # RotWord(09cf4f3c) = cf4f3c09 -> SubWord = 8a84eb01
        # -> 异或 Rcon 01000000 得 8b84eb01（即 detail.xor 字段）
        # -> 再与 W[0]=2b7e1516 异或得 W[4]=a0fafe17
        assert expanded.details[1].rot_word == "cf4f3c09"
        assert expanded.details[1].sub_word == "8a84eb01"
        assert expanded.details[1].rcon == "01000000"
        assert expanded.details[1].xor == "8b84eb01"
        # 最终轮密钥字
        assert bytes(expanded.words[4]).hex() == "a0fafe17"