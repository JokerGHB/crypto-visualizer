"""接口层测试：认证、加密、历史记录、练习模式、安全。

使用内存 SQLite 与独立 engine，避免污染开发数据库。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app


@pytest.fixture(name="test_engine")
def test_engine_fixture():
    """内存数据库 engine，供测试直接查库验证券商侧数据。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="client")
def client_fixture(test_engine):
    """构造使用内存数据库的测试客户端。"""

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="auth_client")
def auth_client_fixture(client):
    """返回已登录的客户端与令牌。"""
    client.post(
        "/api/auth/register",
        json={"username": "student1", "password": "pass1234"},
    )
    response = client.post(
        "/api/auth/login",
        json={"username": "student1", "password": "pass1234"},
    )
    token = response.json()["data"]["accessToken"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


class TestHealth:
    def test_health(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "healthy"


class TestAuth:
    def test_register_and_login(self, client):
        r = client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "secret123"},
        )
        assert r.status_code == 201
        assert r.json()["data"]["username"] == "alice"
        # 口令不得出现在响应中
        assert "password" not in str(r.json()).lower()

        r = client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "secret123"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["accessToken"]

    def test_duplicate_username(self, client):
        payload = {"username": "bob", "password": "secret123"}
        client.post("/api/auth/register", json=payload)
        r = client.post("/api/auth/register", json=payload)
        assert r.status_code == 409
        assert r.json()["code"] == "E_USER_EXISTS"

    def test_wrong_password(self, client):
        client.post(
            "/api/auth/register",
            json={"username": "carol", "password": "secret123"},
        )
        r = client.post(
            "/api/auth/login",
            json={"username": "carol", "password": "wrong"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "E_AUTH_FAILED"

    def test_nonexistent_user_same_error(self, client):
        """用户不存在与口令错误必须返回相同错误，避免枚举。"""
        r = client.post(
            "/api/auth/login",
            json={"username": "ghost", "password": "whatever"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == "E_AUTH_FAILED"

    def test_me_requires_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_with_token(self, auth_client):
        r = auth_client.get("/api/auth/me")
        assert r.status_code == 200
        assert r.json()["data"]["username"] == "student1"


class TestCryptoApi:
    def test_aes_trace_matches_fips(self, client):
        r = client.post(
            "/api/crypto/aes",
            json={
                "input": "3243f6a8885a308d313198a2e0370734",
                "key": "2b7e151628aed2a6abf7158809cf4f3c",
                "keyBits": 128,
                "mode": "encrypt",
            },
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["output"] == "3925841d02dc09fbdc118597196a0b32"
        assert len(data["steps"]) == 40
        assert data["steps"][0]["stateBefore"] == data["input"]

    def test_key_length_mismatch(self, client):
        r = client.post(
            "/api/crypto/aes",
            json={
                "input": "00" * 16,
                "key": "00" * 16,  # 128 位却声明 256
                "keyBits": 256,
                "mode": "encrypt",
            },
        )
        assert r.status_code == 400
        assert r.json()["code"] == "E_KEY_LENGTH"

    def test_invalid_hex_rejected(self, client):
        r = client.post(
            "/api/crypto/aes",
            json={
                "input": "zz" * 16,
                "key": "2b7e151628aed2a6abf7158809cf4f3c",
                "keyBits": 128,
                "mode": "encrypt",
            },
        )
        assert r.status_code == 422
        assert r.json()["code"] == "E_INPUT_FORMAT"

    def test_uppercase_normalized(self, client):
        r = client.post(
            "/api/crypto/aes",
            json={
                "input": "3243F6A8885A308D313198A2E0370734",
                "key": "2B7E151628AED2A6ABF7158809CF4F3C",
                "keyBits": 128,
                "mode": "encrypt",
            },
        )
        assert r.status_code == 200
        assert r.json()["data"]["output"] == "3925841d02dc09fbdc118597196a0b32"

    def test_sbox_endpoint(self, client):
        r = client.get("/api/crypto/sbox")
        assert r.status_code == 200
        table = r.json()["data"]["table"]
        assert len(table) == 16
        assert len(table[0]) == 16
        assert table[0][0] == 0x63
        assert table[1][9] == 0xD4

    def test_sbox_inverse(self, client):
        r = client.get("/api/crypto/sbox?inverse=true")
        table = r.json()["data"]["table"]
        assert table[0xD4 // 16][0xD4 % 16] == 0x19


class TestHistory:
    def test_saved_and_listed(self, auth_client):
        auth_client.post(
            "/api/crypto/aes",
            json={
                "input": "3243f6a8885a308d313198a2e0370734",
                "key": "2b7e151628aed2a6abf7158809cf4f3c",
                "keyBits": 128,
                "mode": "encrypt",
            },
        )
        r = auth_client.get("/api/history/sessions")
        assert r.status_code == 200
        assert r.json()["data"]["total"] == 1

    def test_anonymous_not_saved(self, client):
        client.post(
            "/api/crypto/aes",
            json={
                "input": "00" * 16,
                "key": "00" * 16,
                "keyBits": 128,
                "mode": "encrypt",
            },
        )
        r = client.get("/api/history/sessions")
        assert r.status_code == 401

    def test_get_detail_and_replay(self, auth_client):
        auth_client.post(
            "/api/crypto/aes",
            json={
                "input": "3243f6a8885a308d313198a2e0370734",
                "key": "2b7e151628aed2a6abf7158809cf4f3c",
                "keyBits": 128,
                "mode": "encrypt",
            },
        )
        session_id = auth_client.get("/api/history/sessions").json()["data"]["items"][0]["id"]
        r = auth_client.get(f"/api/history/sessions/{session_id}")
        assert r.status_code == 200
        assert len(r.json()["data"]["trace"]["steps"]) == 40

    def test_cross_user_access_returns_404(self, client):
        """用户 A 不能访问用户 B 的记录，且必须是 404 而非 403。"""
        for name in ("userA", "userB"):
            client.post(
                "/api/auth/register",
                json={"username": name, "password": "pass1234"},
            )
        token_a = client.post(
            "/api/auth/login", json={"username": "userA", "password": "pass1234"}
        ).json()["data"]["accessToken"]
        token_b = client.post(
            "/api/auth/login", json={"username": "userB", "password": "pass1234"}
        ).json()["data"]["accessToken"]

        client.headers.update({"Authorization": f"Bearer {token_a}"})
        client.post(
            "/api/crypto/aes",
            json={
                "input": "00" * 16,
                "key": "00" * 16,
                "keyBits": 128,
                "mode": "encrypt",
            },
        )
        session_id = client.get("/api/history/sessions").json()["data"]["items"][0]["id"]

        client.headers.update({"Authorization": f"Bearer {token_b}"})
        r = client.get(f"/api/history/sessions/{session_id}")
        assert r.status_code == 404
        r = client.delete(f"/api/history/sessions/{session_id}")
        assert r.status_code == 404

    def test_delete_own(self, auth_client):
        auth_client.post(
            "/api/crypto/aes",
            json={
                "input": "00" * 16,
                "key": "00" * 16,
                "keyBits": 128,
                "mode": "encrypt",
            },
        )
        session_id = auth_client.get("/api/history/sessions").json()["data"]["items"][0]["id"]
        r = auth_client.delete(f"/api/history/sessions/{session_id}")
        assert r.status_code == 204
        assert auth_client.get("/api/history/sessions").json()["data"]["total"] == 0


class TestExercise:
    @pytest.mark.parametrize(
        "etype", ["step_identify", "cell_result", "key_param"]
    )
    def test_generate_each_type(self, auth_client, etype):
        r = auth_client.post(
            "/api/exercise/generate", json={"type": etype, "difficulty": "easy"}
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["type"] == etype
        assert data["exerciseId"] > 0
        assert data["prompt"]
        # 标准答案绝不下发给前端
        assert "expected" not in data

    def test_submit_correct(self, auth_client, test_engine):
        gen = auth_client.post(
            "/api/exercise/generate",
            json={"type": "step_identify", "difficulty": "easy"},
        ).json()["data"]
        # 直接查库拿答案，模拟"知道正确答案"的提交
        from app.models import Exercise

        with Session(test_engine) as s:
            row = s.get(Exercise, gen["exerciseId"])
            expected = row.expected

        r = auth_client.post(
            "/api/exercise/submit",
            json={"exerciseId": gen["exerciseId"], "answer": expected},
        )
        assert r.status_code == 200
        assert r.json()["data"]["isCorrect"] is True

    def test_submit_wrong_returns_analysis(self, auth_client):
        gen = auth_client.post(
            "/api/exercise/generate",
            json={"type": "cell_result", "difficulty": "easy"},
        ).json()["data"]
        r = auth_client.post(
            "/api/exercise/submit",
            json={"exerciseId": gen["exerciseId"], "answer": "ff"},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["analysis"]
        assert data["stepIndex"] is not None

    def test_invalid_type(self, auth_client):
        r = auth_client.post(
            "/api/exercise/generate",
            json={"type": "nonsense", "difficulty": "easy"},
        )
        assert r.status_code == 400

    def test_submit_nonexistent(self, auth_client):
        r = auth_client.post(
            "/api/exercise/submit",
            json={"exerciseId": 99999, "answer": "x"},
        )
        assert r.status_code == 404


class TestSecurity:
    def test_security_headers(self, client):
        r = client.get("/api/health")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in r.headers

    def test_xss_username_stored_verbatim(self, client):
        """用户名含脚本标签时应被拒绝或被原样存储，绝不被当 HTML 执行。"""
        r = client.post(
            "/api/auth/register",
            json={"username": "<script>alert(1)</script>", "password": "pass1234"},
        )
        # 用户名正则不允许尖括号，应被 422 拒绝
        assert r.status_code == 422

    def test_oversized_question_rejected(self, auth_client):
        gen = auth_client.post(
            "/api/crypto/aes",
            json={
                "input": "00" * 16,
                "key": "00" * 16,
                "keyBits": 128,
                "mode": "encrypt",
            },
        ).json()["data"]
        r = auth_client.post(
            "/api/ai/tutor/chat",
            json={
                "stepContext": {
                    "index": 0,
                    "round": 0,
                    "op": "AddRoundKey",
                    "stateBefore": gen["steps"][0]["stateBefore"],
                    "stateAfter": gen["steps"][0]["stateAfter"],
                    "cells": [],
                },
                "question": "x" * 600,
            },
        )
        assert r.status_code == 422

    def test_invalid_step_context_rejected(self, auth_client):
        r = auth_client.post(
            "/api/ai/tutor/chat",
            json={
                "stepContext": {
                    "index": 0,
                    "round": 0,
                    "op": "AddRoundKey",
                    "stateBefore": "short",
                    "stateAfter": "00" * 16,
                },
                "question": "这是哪一步？",
            },
        )
        assert r.status_code == 400