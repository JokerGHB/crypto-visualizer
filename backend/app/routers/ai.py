"""AI 辅导接口：流式对话 + 降级。

降级触发条件：未配置密钥、AI_ENABLED=false、超时、HTTP 非 200。
降级时仍以相同 SSE 格式返回本地讲解，前端无需区分两套渲染逻辑。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import select

from app.config import get_settings
from app.core.errors import NotFoundError
from app.deps import CurrentUser, SessionDep
from app.middleware.rate_limit import SlidingWindowLimiter
from app.models import AiConversation, AiMessage
from app.schemas.envelope import ok
from app.services.ai.prompt import (
    build_messages,
    fallback_explanation,
    validate_step_context,
)
from app.services.ai.provider import get_provider

router = APIRouter(prefix="/api/ai", tags=["AI 辅导"])

_settings = get_settings()
_limiter = SlidingWindowLimiter(
    limit=_settings.ai_rate_limit_per_minute, window_seconds=60.0
)


class ChatRequest(BaseModel):
    """AI 对话请求。"""

    conversation_id: int | None = Field(default=None, alias="conversationId")
    step_context: dict = Field(alias="stepContext")
    question: str = Field(min_length=1, max_length=500)
    total_steps: int | None = Field(default=None, alias="totalSteps")

    model_config = {"populate_by_name": True}


def _sse(payload: dict | str) -> str:
    """构造一条 SSE 数据帧。"""
    if isinstance(payload, str):
        return f"data: {payload}\n\n"
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_fallback(text: str) -> AsyncIterator[str]:
    """把本地讲解按小块推送，保持与 AI 流一致的交互体验。"""
    chunk_size = 24
    for i in range(0, len(text), chunk_size):
        yield _sse({"delta": text[i : i + chunk_size]})
    yield _sse("[DONE]")


@router.post("/tutor/chat")
def chat(
    payload: ChatRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> StreamingResponse:
    """AI 辅导对话，返回 SSE 流。

    每条数据形如 data: {"delta": "..."}，以 data: [DONE] 结束。
    """
    # 限流按用户维度
    _limiter.check(f"ai:{user.id}")

    context = validate_step_context(payload.step_context)

    # 取或建会话
    conversation: AiConversation | None = None
    if payload.conversation_id is not None:
        conversation = session.get(AiConversation, payload.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise NotFoundError("会话不存在")
    else:
        conversation = AiConversation(user_id=user.id)
        session.add(conversation)
        session.commit()
        session.refresh(conversation)

    # 取最近历史（按时间倒序取 N 条后反转）
    history_rows = session.exec(
        select(AiMessage)
        .where(AiMessage.conversation_id == conversation.id)
        .order_by(AiMessage.created_at.desc())
        .limit(6)
    ).all()
    history = [
        {"role": r.role, "content": r.content} for r in reversed(history_rows)
    ]

    messages = build_messages(
        context, payload.question, history, payload.total_steps
    )

    # 落库用户消息
    session.add(
        AiMessage(
            conversation_id=conversation.id, role="user", content=payload.question
        )
    )
    session.commit()

    conversation_id = conversation.id
    fallback_text = fallback_explanation(context)
    provider = get_provider()

    async def event_stream() -> AsyncIterator[str]:
        """优先走真实 AI，任何失败都平滑降级。"""
        yield _sse({"conversationId": conversation_id})

        if provider is None:
            async for chunk in _stream_fallback(fallback_text):
                yield chunk
            _persist_assistant(fallback_text)
            return

        collected: list[str] = []
        try:
            async for delta in provider.stream(messages):
                collected.append(delta)
                yield _sse({"delta": delta})
        except (httpx.HTTPError, httpx.TimeoutException, OSError):
            if collected:
                yield _sse({"delta": "\n\n（连接中断，以上为已生成内容）"})
                _persist_assistant("".join(collected))
            else:
                async for chunk in _stream_fallback(fallback_text):
                    yield chunk
                _persist_assistant(fallback_text)
            yield _sse("[DONE]")
            return

        text = "".join(collected) or fallback_text
        _persist_assistant(text)
        yield _sse("[DONE]")

    def _persist_assistant(text: str) -> None:
        """把助手回复写入历史，供下一轮上下文使用。"""
        from app.database import engine
        from sqlmodel import Session as SqlSession

        with SqlSession(engine) as own:
            own.add(
                AiMessage(
                    conversation_id=conversation_id, role="assistant", content=text
                )
            )
            own.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int, session: SessionDep, user: CurrentUser
) -> dict:
    """读取会话历史，供页面刷新后恢复。"""
    conversation = session.get(AiConversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise NotFoundError("会话不存在")

    rows = session.exec(
        select(AiMessage)
        .where(AiMessage.conversation_id == conversation_id)
        .order_by(AiMessage.created_at.asc())
    ).all()
    return ok(
        {
            "id": conversation.id,
            "messages": [
                {
                    "role": r.role,
                    "content": r.content,
                    "createdAt": r.created_at.isoformat(),
                }
                for r in rows
            ],
        }
    )