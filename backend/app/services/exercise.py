"""练习模式：出题与判分。

安全要点：
- 题目与标准答案全部由服务端依据真实 Trace 生成并落库；
- 判分只读数据库里的 expected，绝不信任前端传来的答案或标准答案；
- 干扰项只从实际出现过的操作集合中取，避免出现明显荒谬的选项。
"""

from __future__ import annotations

import json
import random

from sqlmodel import Session

from app.core.aes.engine import build_trace
from app.core.errors import InputFormatError, NotFoundError
from app.models import Exercise, ExerciseAttempt
from app.schemas.trace import AesKeyBits, AesMode, AesOp

EXERCISE_TYPES = ("step_identify", "cell_result", "key_param")

# 出题所用的固定参数池，保证题目稳定可复现
_KEYS = {
    AesKeyBits.BITS_128: "2b7e151628aed2a6abf7158809cf4f3c",
}
_PLAINTEXTS = [
    "3243f6a8885a308d313198a2e0370734",
    "00112233445566778899aabbccddeeff",
    "0123456789abcdeffedcba9876543210",
]


def _random_trace(rng: random.Random):
    """随机生成一条加密 Trace。"""
    key_bits = AesKeyBits.BITS_128
    plaintext = rng.choice(_PLAINTEXTS)
    return build_trace(plaintext, _KEYS[key_bits], key_bits, AesMode.ENCRYPT)


def _make_step_identify(rng: random.Random) -> dict:
    """题型一：给出前后状态，判断是哪一步操作。"""
    trace = _random_trace(rng)
    step = rng.choice(trace.steps)
    options = ["SubBytes", "ShiftRows", "MixColumns", "AddRoundKey"]
    rng.shuffle(options)
    snapshot = {
        "question": "观察下面两个状态矩阵，判断这是 AES 中的哪一步操作。",
        "stateBefore": step.state_before,
        "stateAfter": step.state_after,
        "round": step.round,
        "options": options,
    }
    analysis = (
        f"正确答案是 {step.op.value}。"
        f"{step.explain}。"
        f"该步属于第 {step.round} 轮，第 {step.index + 1} 步。"
    )
    return {
        "type": "step_identify",
        "snapshot": snapshot,
        "expected": step.op.value,
        "analysis": analysis,
        "step_index": step.index,
    }


def _make_cell_result(rng: random.Random) -> dict:
    """题型二：给定某一步，问指定单元格变换后的字节值。"""
    trace = _random_trace(rng)
    # 只选真正会改变字节的操作，避免出现"不变"导致的歧义题
    candidates = [
        s
        for s in trace.steps
        if s.op in (AesOp.SUB_BYTES, AesOp.MIX_COLUMNS, AesOp.ADD_ROUND_KEY)
    ]
    step = rng.choice(candidates)
    cell = rng.choice(step.cells)
    snapshot = {
        "question": (
            f"这是第 {step.round} 轮的 {step.op.value}。"
            f"请填写状态矩阵第 {cell.row} 行第 {cell.col} 列变换后的字节值（两位十六进制）。"
        ),
        "op": step.op.value,
        "round": step.round,
        "stateBefore": step.state_before,
        "row": cell.row,
        "col": cell.col,
        "aux": cell.aux,
    }
    analysis = (
        f"第 {cell.row} 行第 {cell.col} 列由 {cell.before} 变为 {cell.after}。"
        + (f"计算依据：{cell.aux}。" if cell.aux else "")
        + f"{step.explain}。"
    )
    return {
        "type": "cell_result",
        "snapshot": snapshot,
        "expected": cell.after,
        "analysis": analysis,
        "step_index": step.index,
    }


def _make_key_param(rng: random.Random) -> dict:
    """题型三：换一个密钥，问指定轮某一字节的值。"""
    rng_key = bytes(rng.getrandbits(8) for _ in range(16)).hex()
    plaintext = rng.choice(_PLAINTEXTS)
    trace = build_trace(plaintext, rng_key, AesKeyBits.BITS_128, AesMode.ENCRYPT)

    round_no = rng.randint(1, 9)
    step = next(
        s
        for s in trace.steps
        if s.round == round_no and s.op == AesOp.ADD_ROUND_KEY
    )
    cell = rng.choice(step.cells)
    snapshot = {
        "question": (
            f"明文为 {plaintext}，密钥为 {rng_key}。"
            f"请填写第 {round_no} 轮轮密钥加之后，"
            f"第 {cell.row} 行第 {cell.col} 列的字节值（两位十六进制）。"
        ),
        "plaintext": plaintext,
        "key": rng_key,
        "round": round_no,
        "row": cell.row,
        "col": cell.col,
    }
    analysis = (
        f"在给定的明文与密钥下，第 {round_no} 轮轮密钥加后，"
        f"第 {cell.row} 行第 {cell.col} 列为 {cell.after}。"
        f"该列输入为 {cell.before}，轮密钥字节为 {cell.aux}，异或即得结果。"
    )
    return {
        "type": "key_param",
        "snapshot": snapshot,
        "expected": cell.after,
        "analysis": analysis,
        "step_index": step.index,
    }


_BUILDERS = {
    "step_identify": _make_step_identify,
    "cell_result": _make_cell_result,
    "key_param": _make_key_param,
}


def generate(session: Session, exercise_type: str, difficulty: str) -> dict:
    """生成并保存一道练习题。

    Raises:
        InputFormatError: 题型不受支持。
    """
    if exercise_type not in _BUILDERS:
        raise InputFormatError(
            f"不支持的题型 {exercise_type}，可选：{', '.join(EXERCISE_TYPES)}"
        )

    builder = _BUILDERS[exercise_type]
    rng = random.Random()
    data = builder(rng)

    row = Exercise(
        type=data["type"],
        difficulty=difficulty,
        snapshot_json=json.dumps(data["snapshot"], ensure_ascii=False),
        expected=data["expected"],
        analysis=data["analysis"],
        step_index=data["step_index"],
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    return {
        "exerciseId": row.id,
        "type": row.type,
        "difficulty": row.difficulty,
        "prompt": data["snapshot"]["question"],
        "snapshot": data["snapshot"],
    }


def submit(session: Session, user_id: int, exercise_id: int, answer: str) -> dict:
    """判分并记录作答。

    Raises:
        NotFoundError: 题目不存在。
    """
    row = session.get(Exercise, exercise_id)
    if row is None:
        raise NotFoundError("题目不存在")

    # 统一小写去空白后比较；操作名与十六进制均适用
    normalized = answer.strip().lower()
    expected_normalized = row.expected.strip().lower()
    is_correct = normalized == expected_normalized

    session.add(
        ExerciseAttempt(
            user_id=user_id,
            exercise_id=exercise_id,
            answer=answer[:64],
            is_correct=is_correct,
        )
    )
    session.commit()

    return {
        "isCorrect": is_correct,
        "expected": row.expected,
        "analysis": row.analysis,
        "stepIndex": row.step_index,
        "type": row.type,
    }