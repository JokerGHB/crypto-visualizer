"""Trace 数据契约：一次 AES 加/解密产生的完整步骤序列。

本模块是前后端共用的唯一权威定义。前端镜像见 frontend/src/types/trace.ts，
两份必须逐字段一致。

Python 侧使用 snake_case 变量名，序列化为 JSON 时统一转成 camelCase
（通过 alias_generator），因此线上契约字段名为 stateBefore / keyBits / keySchedule 等。
字段一旦发布只允许新增可选字段，不得改名或改类型。
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """统一 JSON 输出为 camelCase 的基类。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class AesKeyBits(int, Enum):
    """AES 密钥长度。"""

    BITS_128 = 128
    BITS_192 = 192
    BITS_256 = 256


class AesMode(str, Enum):
    """运算方向。"""

    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"


class AesOp(str, Enum):
    """可展示的算法操作类型。"""

    ADD_ROUND_KEY = "AddRoundKey"
    SUB_BYTES = "SubBytes"
    SHIFT_ROWS = "ShiftRows"
    MIX_COLUMNS = "MixColumns"
    INV_SUB_BYTES = "InvSubBytes"
    INV_SHIFT_ROWS = "InvShiftRows"
    INV_MIX_COLUMNS = "InvMixColumns"


class CellChange(CamelModel):
    """状态矩阵中单个字节的变化明细。"""

    row: int = Field(ge=0, le=3, description="行号 0..3")
    col: int = Field(ge=0, le=3, description="列号 0..3")
    before: str = Field(pattern=r"^[0-9a-f]{2}$", description="变化前字节")
    after: str = Field(pattern=r"^[0-9a-f]{2}$", description="变化后字节")
    aux: str | None = Field(
        default=None,
        description="辅助信息：轮密钥字节 / sbox 坐标 / xtime 中间量",
    )


class Step(CamelModel):
    """可视化的最小单位：一次操作及其前后状态。"""

    index: int = Field(ge=0, description="步骤序号，等于其在 steps 数组中的下标")
    round: int = Field(ge=0, description="轮次 0..Nr")
    op: AesOp
    state_before: str = Field(
        pattern=r"^[0-9a-f]{32}$", description="操作前状态，列主序展平"
    )
    state_after: str = Field(
        pattern=r"^[0-9a-f]{32}$", description="操作后状态，列主序展平"
    )
    round_key: str | None = Field(
        default=None, description="仅 AddRoundKey 步存在，32 位十六进制"
    )
    cells: list[CellChange] = Field(
        default_factory=list, description="逐格明细，至少包含发生变化的格"
    )
    explain: str = Field(description="一句话中文说明，AI 不可用时的本地讲解")


class KeyScheduleDetail(CamelModel):
    """密钥扩展中 RotWord / SubWord / Rcon / XOR 四步明细。"""

    rot_word: str = Field(pattern=r"^[0-9a-f]{8}$")
    sub_word: str = Field(pattern=r"^[0-9a-f]{8}$")
    rcon: str = Field(pattern=r"^[0-9a-f]{8}$")
    xor: str = Field(pattern=r"^[0-9a-f]{8}$")


class KeyScheduleRound(CamelModel):
    """密钥扩展中一轮的结果。"""

    round: int = Field(ge=0)
    words: list[str] = Field(
        min_length=4, max_length=4, description="该轮 4 个 8 位十六进制字"
    )
    detail: KeyScheduleDetail | None = Field(
        default=None, description="从第 1 轮轮密钥起存在"
    )


class Trace(CamelModel):
    """一次 AES 运算的完整轨迹。"""

    algorithm: str = Field(default="AES")
    key_bits: AesKeyBits
    mode: AesMode
    rounds: int = Field(ge=10, le=14, description="10 / 12 / 14")
    input: str = Field(pattern=r"^[0-9a-f]{32}$")
    key: str = Field(pattern=r"^[0-9a-f]{32,64}$")
    output: str = Field(pattern=r"^[0-9a-f]{32}$")
    key_schedule: list[KeyScheduleRound]
    steps: list[Step]


class AesRequest(CamelModel):
    """POST /api/crypto/aes 的请求体。

    input / key 的字符集与长度在入口即校验，非法内容不会进入算法层。
    允许大写，引擎内部统一转小写后再运算。
    """

    input: str = Field(
        pattern=r"^[0-9a-fA-F]{32}$",
        description="明文或密文，32 位十六进制",
    )
    key: str = Field(
        pattern=r"^[0-9a-fA-F]{32,64}$",
        description="密钥，32 / 48 / 64 位十六进制",
    )
    key_bits: AesKeyBits
    mode: AesMode = AesMode.ENCRYPT