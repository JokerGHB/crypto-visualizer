"""AI 降级测试。

必须覆盖三种场景：无密钥、超时、HTTP 非 200。
三种情况下接口都应返回 200 且内容非空，保证演示不因外部依赖中断。

注意：patch 目标必须是 app.routers.ai 模块中的 get_provider 名字，
因为 ai.py 用 from ... import get_provider 做了本地绑定。
patch provider 模块本身不会生效。
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app
from app.routers import ai as ai_router

STEP_CONTEXT = {
    "index": 1,
    "round": 1,
    "op": "SubBytes",
    "stateBefore": "193de3bea0f4e22b9ac68d2ae9f84808",
    "stateAfter": "d42711aee0bf98f1b8b45de51e415230",
    "cells": [
        {
            "row": 0,
            "col": 0,
            "before": "19",
            "after": "d4",
            "aux": "sbox[19]",
        }
    ],
    "explain": "第 1 轮 SubBytes：字节替换",
    "keyBits": 128,
    "mode": "encrypt",
}


@pytest.fixture(name="client")
def client_fixture():
    """内存数据库测试客户端（含已登录用户）。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        client.post(
            "/api/auth/register",
            json={"username": "aistudent", "password": "pass1234"},
        )
        token = client.post(
            "/api/auth/login",
            json={"username": "aistudent", "password": "pass1234"},
        ).json()["data"]["accessToken"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client
    app.dependency_overrides.clear()


def _collect_sse(client, payload) -> str:
    """发起对话并拼接全部增量文本。"""
    with client.stream("POST", "/api/ai/tutor/chat", json=payload) as response:
        assert response.status_code == 200
        chunks = []
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            obj = json.loads(data)
            if "delta" in obj:
                chunks.append(obj["delta"])
        return "".join(chunks)


class TestFallback:
    def test_no_api_key_uses_local_explanation(self, client, monkeypatch):
        """场景一：未配置密钥（provider 为 None），应直接返回本地讲解。"""
        monkeypatch.setattr(ai_router, "get_provider", lambda: None)
        text = _collect_sse(
            client,
            {"stepContext": STEP_CONTEXT, "question": "这一步在做什么？"},
        )
        assert text, "降级内容不得为空"
        assert "离线讲解" in text

    def test_timeout_falls_back(self, client, monkeypatch):
        """场景二：调用超时，应降级到本地讲解。"""

        class TimeoutProvider:
            async def stream(self, messages):
                raise httpx.TimeoutException("timeout")
                yield ""  # pragma: no cover

        monkeypatch.setattr(
            ai_router, "get_provider", lambda: TimeoutProvider()
        )
        text = _collect_sse(
            client,
            {"stepContext": STEP_CONTEXT, "question": "为什么 19 变成 d4？"},
        )
        assert text
        assert "离线讲解" in text

    def test_http_error_falls_back(self, client, monkeypatch):
        """场景三：服务返回非 200，应降级到本地讲解。"""

        class ErrorProvider:
            async def stream(self, messages):
                request = httpx.Request("POST", "http://example.invalid")
                raise httpx.HTTPStatusError(
                    "500",
                    request=request,
                    response=httpx.Response(500, request=request),
                )
                yield ""  # pragma: no cover

        monkeypatch.setattr(
            ai_router, "get_provider", lambda: ErrorProvider()
        )
        text = _collect_sse(
            client,
            {"stepContext": STEP_CONTEXT, "question": "S 盒是什么？"},
        )
        assert text
        assert "离线讲解" in text

    def test_normal_path_streams(self, client, monkeypatch):
        """AI 可用时正常流式返回，且不出现离线标记。"""

        class GoodProvider:
            async def stream(self, messages):
                for piece in ("S 盒是一个", " 256 项的查表。", ""):
                    if piece:
                        yield piece

        monkeypatch.setattr(
            ai_router, "get_provider", lambda: GoodProvider()
        )
        text = _collect_sse(
            client,
            {"stepContext": STEP_CONTEXT, "question": "S 盒是什么？"},
        )
        assert "查表" in text
        assert "离线讲解" not in text

    def test_unauthenticated_rejected(self, client):
        """未登录不得调用 AI 接口。"""
        client.headers.pop("Authorization", None)
        r = client.post(
            "/api/ai/tutor/chat",
            json={"stepContext": STEP_CONTEXT, "question": "test"},
        )
        assert r.status_code == 401


class TestPromptAssembly:
    """提示词组装的结构正确性。"""

    def test_context_block_contains_step_info(self):
        from app.services.ai.prompt import build_context_block

        block = build_context_block(STEP_CONTEXT, 40)
        assert "第 1 轮" in block
        assert "字节替代" in block
        assert "sbox[19]" in block

    def test_history_truncated_to_six(self):
        from app.services.ai.prompt import build_messages

        history = [{"role": "user", "content": f"问题{i}"} for i in range(20)]
        messages = build_messages(STEP_CONTEXT, "新问题", history, 40)
        # 2 条 system + 最多 6 条历史 + 1 条当前问题
        assert len(messages) == 2 + 6 + 1
        assert messages[-1]["content"] == "新问题"

    def test_empty_question_rejected(self):
        from app.core.errors import InputFormatError
        from app.services.ai.prompt import build_messages

        with pytest.raises(InputFormatError):
            build_messages(STEP_CONTEXT, "   ", [], 40)

    def test_invalid_state_rejected(self):
        from app.core.errors import InputFormatError
        from app.services.ai.prompt import validate_step_context

        bad = dict(STEP_CONTEXT)
        bad["stateBefore"] = "not-hex"
        with pytest.raises(InputFormatError):
            validate_step_context(bad)

    def test_unknown_op_rejected(self):
        from app.core.errors import InputFormatError
        from app.services.ai.prompt import validate_step_context

        bad = dict(STEP_CONTEXT)
        bad["op"] = "DropTable"
        with pytest.raises(InputFormatError):
            validate_step_context(bad)