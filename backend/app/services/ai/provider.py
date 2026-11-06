"""AI 服务商适配层。

只依赖 OpenAI 兼容的 /chat/completions 流式协议，不绑定具体厂商。
通过环境变量切换 base_url / model / key 即可换供应商。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Protocol

import httpx

from app.config import get_settings


class ChatProvider(Protocol):
    """对话服务商接口。"""

    def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """流式返回增量文本。"""
        ...


class OpenAICompatProvider:
    """OpenAI 兼容协议的流式实现。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """逐块产出文本增量。

        Raises:
            httpx.HTTPError: 网络异常或非 200 响应。
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST", url, json=payload, headers=headers
            ) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise httpx.HTTPStatusError(
                        f"AI 服务返回 {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content


class DisabledProvider:
    """未配置密钥时的占位实现，调用即失败以触发降级。"""

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """始终抛出异常，交由上层降级处理。"""
        raise httpx.ConnectError("AI 服务未配置")
        yield ""  # pragma: no cover - 保持生成器语义


def get_provider() -> ChatProvider | None:
    """按配置返回可用的服务商；不可用时返回 None。"""
    settings = get_settings()
    if not settings.ai_enabled:
        return None
    if not settings.ai_api_key or not settings.ai_base_url or not settings.ai_model:
        return None
    return OpenAICompatProvider(
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
        timeout=settings.ai_timeout,
    )