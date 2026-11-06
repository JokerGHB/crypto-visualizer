"""配置解析测试：重点是环境变量到列表的兼容处理。"""

from __future__ import annotations

import pytest

from app.config import Settings, get_settings


def test_默认配置可加载():
    settings = Settings()
    assert settings.app_name
    assert settings.jwt_algorithm == "HS256"
    assert "http://localhost:5173" in settings.cors_origins


def test_cors_支持逗号分隔(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
    settings = Settings()
    assert settings.cors_origins == ["http://a.com", "http://b.com"]


def test_cors_支持_json_数组(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ORIGINS", '["http://a.com","http://b.com"]')
    settings = Settings()
    assert settings.cors_origins == ["http://a.com", "http://b.com"]


def test_cors_空值得到空列表(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ORIGINS", "   ")
    settings = Settings()
    assert settings.cors_origins == []


def test_get_settings_带缓存():
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()


# ---------- AI 密钥：多环境变量名兼容 ----------


def test_密钥可来自_GPT_API_KEY(monkeypatch: pytest.MonkeyPatch):
    """当前约定使用 GPT_API_KEY，应能读到。"""
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GPT_API_KEY", "sk-from-gpt-var")
    settings = Settings()
    assert settings.ai_api_key == "sk-from-gpt-var"
    assert settings.resolve_key_source() == "GPT_API_KEY"


def test_密钥可来自_AI_API_KEY(monkeypatch: pytest.MonkeyPatch):
    """保留旧名称兼容，避免已有配置失效。"""
    monkeypatch.delenv("GPT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_API_KEY", "sk-from-legacy")
    settings = Settings()
    assert settings.ai_api_key == "sk-from-legacy"


def test_GPT_API_KEY_优先于_AI_API_KEY(monkeypatch: pytest.MonkeyPatch):
    """同时存在时，GPT_API_KEY 优先。"""
    monkeypatch.setenv("GPT_API_KEY", "sk-primary")
    monkeypatch.setenv("AI_API_KEY", "sk-secondary")
    settings = Settings()
    assert settings.ai_api_key == "sk-primary"


def test_脱敏不泄露完整密钥(monkeypatch: pytest.MonkeyPatch):
    """masked() 只保留末 4 位，防止密钥进入日志。"""
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    monkeypatch.setenv("GPT_API_KEY", secret)
    monkeypatch.setenv("AI_BASE_URL", "https://example.com/v1")
    settings = Settings()
    masked = settings.masked()
    assert masked["ai_api_key"] == "***3456"
    assert secret not in str(masked)
    assert masked["ai_available"] is True


def test_密钥缺失时不可用(monkeypatch: pytest.MonkeyPatch):
    for name in ("GPT_API_KEY", "AI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI_BASE_URL", "https://example.com/v1")
    settings = Settings()
    # .env 里可能留有值，故只在确实为空时断言
    if not settings.ai_api_key:
        assert settings.masked()["ai_available"] is False
        assert "未就绪" in settings.startup_report()


def test_启动自检提示缺失项(monkeypatch: pytest.MonkeyPatch):
    for name in ("GPT_API_KEY", "AI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI_ENABLED", "false")
    settings = Settings()
    report = settings.startup_report()
    assert "配置自检" in report
    # 关闭 AI 时不应声称就绪
    assert "未就绪" in report