"""统一响应包装。

除 SSE 流式接口外，所有接口返回 {code, message, data}。
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """统一响应结构。"""

    code: int = 0
    message: str = "ok"
    data: T | None = None


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    """构造成功响应。"""
    return {"code": 0, "message": message, "data": data}