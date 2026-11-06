"""配置解析测试：重点是环境变量到列表的兼容处理。"""

from __future__ import annotations

import pytest

from app.config import Settings, get_settings


def test_默认配置可加载():
    settings = Settings()
    assert settings.app_name
    assert settings.jwt_algorithm == "HS256"
    assert "http://localhost:5200" in settings.cors_origins


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