"""数据库表模型。

使用 SQLModel，同时承担建表与（部分）校验职责。
表名统一 snake_case 复数。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """统一使用带时区的 UTC 时间。"""
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    """用户账号。"""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=32)
    password_hash: str = Field(max_length=128)
    role: str = Field(default="student", max_length=16)
    created_at: datetime = Field(default_factory=_utcnow)


class CryptoSession(SQLModel, table=True):
    """一次加/解密的完整记录。

    trace_json 存完整 Trace 序列化结果，回放时无需重算，
    保证历史记录与当时所见完全一致。
    """

    __tablename__ = "crypto_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    algorithm: str = Field(default="AES", max_length=16)
    mode: str = Field(max_length=16)
    key_bits: int
    input_hex: str = Field(max_length=64)
    key_hex: str = Field(max_length=128)
    output_hex: str = Field(max_length=64)
    rounds: int
    trace_json: str
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class Exercise(SQLModel, table=True):
    """练习题。

    snapshot_json 存出题时的上下文（状态矩阵、选项等），
    expected 存标准答案，均由服务端生成，绝不信任前端。
    """

    __tablename__ = "exercises"

    id: int | None = Field(default=None, primary_key=True)
    type: str = Field(max_length=32, index=True)
    difficulty: str = Field(default="easy", max_length=16)
    snapshot_json: str
    expected: str = Field(max_length=64)
    analysis: str
    step_index: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)


class ExerciseAttempt(SQLModel, table=True):
    """作答记录。"""

    __tablename__ = "exercise_attempts"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    exercise_id: int = Field(foreign_key="exercises.id", index=True)
    answer: str = Field(max_length=64)
    is_correct: bool
    created_at: datetime = Field(default_factory=_utcnow, index=True)


class AiConversation(SQLModel, table=True):
    """AI 对话会话。"""

    __tablename__ = "ai_conversations"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    session_id: int | None = Field(
        default=None, foreign_key="crypto_sessions.id", index=True
    )
    created_at: datetime = Field(default_factory=_utcnow)


class AiMessage(SQLModel, table=True):
    """AI 对话消息。"""

    __tablename__ = "ai_messages"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(
        foreign_key="ai_conversations.id", index=True
    )
    role: str = Field(max_length=16)
    content: str
    created_at: datetime = Field(default_factory=_utcnow, index=True)