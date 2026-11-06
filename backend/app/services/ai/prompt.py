"""提示词组装与上下文管理。

设计原则：AI 辅导是"受控注入"，不是自由聊天。
每轮请求都由后端拼装固定结构，用户只能控制【问题】段，
因此不会被诱导改写角色或规则。
"""

from __future__ import annotations

from app.core.errors import InputFormatError
from app.schemas.trace import AesOp

# 最多保留的历史消息条数（3 轮问答）
MAX_HISTORY_MESSAGES = 6
# 单次问题最大字符数
MAX_QUESTION_LENGTH = 500

SYSTEM_ROLE = (
    "你是密码学助教，面向零基础本科生讲解 AES。要求："
    "结合当前步骤的具体字节讲解，多用类比，单次回答不超过 200 字，"
    "不使用未解释的术语，不直接给出练习题的完整答案。"
)

_OP_NAMES: dict[str, str] = {
    AesOp.ADD_ROUND_KEY.value: "轮密钥加",
    AesOp.SUB_BYTES.value: "字节替代",
    AesOp.SHIFT_ROWS.value: "行移位",
    AesOp.MIX_COLUMNS.value: "列混合",
    AesOp.INV_SUB_BYTES.value: "逆字节替代",
    AesOp.INV_SHIFT_ROWS.value: "逆行移位",
    AesOp.INV_MIX_COLUMNS.value: "逆列混合",
}


def _spaced_hex(hex_str: str, limit: int = 16) -> str:
    """把十六进制串按字节加空格，便于阅读。"""
    pairs = [hex_str[i : i + 2] for i in range(0, len(hex_str), 2)]
    return " ".join(pairs[:limit])


def validate_step_context(context: dict) -> dict:
    """校验前端传来的步骤上下文。

    防止超长内容或非法字段进入提示词。

    Raises:
        InputFormatError: 缺少必需字段或格式非法。
    """
    required = ("index", "round", "op", "stateBefore", "stateAfter")
    for key in required:
        if key not in context:
            raise InputFormatError(f"步骤上下文缺少字段 {key}")

    for key in ("stateBefore", "stateAfter"):
        value = context[key]
        if not isinstance(value, str) or len(value) != 32:
            raise InputFormatError(f"{key} 必须是 32 位十六进制字符串")
        try:
            int(value, 16)
        except ValueError as exc:
            raise InputFormatError(f"{key} 含非十六进制字符") from exc

    op = context["op"]
    if op not in _OP_NAMES:
        raise InputFormatError(f"未知的操作类型 {op}")

    index = context["index"]
    round_no = context["round"]
    if not isinstance(index, int) or index < 0:
        raise InputFormatError("index 必须是非负整数")
    if not isinstance(round_no, int) or round_no < 0:
        raise InputFormatError("round 必须是非负整数")

    cells = context.get("cells") or []
    if not isinstance(cells, list):
        raise InputFormatError("cells 必须是数组")

    return context


def build_context_block(context: dict, total_steps: int | None) -> str:
    """生成【上下文】段落。"""
    cells = context.get("cells") or []
    changed = []
    for cell in cells[:4]:
        aux = cell.get("aux")
        part = f"r{cell['row']}c{cell['col']}: {cell['before']}→{cell['after']}"
        if aux:
            part += f" ({aux})"
        changed.append(part)

    total = f"/{total_steps}" if total_steps else ""
    mode_text = "加密" if context.get("mode", "encrypt") == "encrypt" else "解密"
    key_bits = context.get("keyBits", 128)

    lines = [
        "【上下文】",
        f"算法：AES-{key_bits}｜模式：{mode_text}｜"
        f"当前：第 {context['round']} 轮 {_OP_NAMES[context['op']]}"
        f"（第 {context['index'] + 1}{total} 步）",
        f"输入状态：{_spaced_hex(context['stateBefore'])}",
        f"输出状态：{_spaced_hex(context['stateAfter'])}",
    ]
    if changed:
        lines.append(f"本次变化：{'；'.join(changed)}")
    return "\n".join(lines)


def build_messages(
    context: dict,
    question: str,
    history: list[dict[str, str]],
    total_steps: int | None = None,
) -> list[dict[str, str]]:
    """组装完整的消息列表。

    Args:
        context: 已校验的步骤上下文。
        question: 用户问题。
        history: 历史消息，按时间正序，role 为 user/assistant。
        total_steps: 总步数，用于显示进度。

    Returns:
        可直接发给 OpenAI 兼容接口的 messages 列表。

    Raises:
        InputFormatError: 问题为空或超长。
    """
    text = (question or "").strip()
    if not text:
        raise InputFormatError("问题不能为空")
    if len(text) > MAX_QUESTION_LENGTH:
        raise InputFormatError(f"问题不得超过 {MAX_QUESTION_LENGTH} 字")

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_ROLE},
        {"role": "system", "content": build_context_block(context, total_steps)},
    ]
    for item in history[-MAX_HISTORY_MESSAGES:]:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:1000]})
    messages.append({"role": "user", "content": text})
    return messages


def fallback_explanation(context: dict) -> str:
    """AI 不可用时的本地讲解。

    直接使用该步骤的 explain 字段（由后端在 Trace 中已生成），
    保证无网络时仍有可用内容。
    """
    explain = context.get("explain")
    if explain:
        return f"{explain}\n\n（离线讲解：AI 服务暂不可用）"
    op = _OP_NAMES.get(context.get("op", ""), "该步骤")
    return (
        f"当前处于第 {context.get('round', 0)} 轮的{op}，"
        f"输入状态 {_spaced_hex(context.get('stateBefore', ''))}，"
        f"输出状态 {_spaced_hex(context.get('stateAfter', ''))}。\n\n"
        "（离线讲解：AI 服务暂不可用）"
    )