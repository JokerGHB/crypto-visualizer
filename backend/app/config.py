"""应用配置：统一从环境变量读取。

所有可配置项集中在此，禁止在业务代码里散落 os.getenv 调用。
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用
    app_name: str = "密码学算法可视化教学与 AI 辅导平台"
    debug: bool = True

    # 数据库：开发默认 SQLite，生产切 MySQL
    database_url: str = "sqlite:///./crypto_visualizer.db"

    # 认证
    jwt_secret: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # 跨域：前端开发地址。NoDecode 让原始字符串直接交给下面的验证器处理，
    # 否则 pydantic-settings 会先按 JSON 解析而拒绝逗号分隔写法。
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5200",
        "http://127.0.0.1:5200",
    ]

    # AI 服务
    ai_enabled: bool = True
    ai_base_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""
    ai_timeout: float = 10.0

    # 限流：AI 接口每用户每分钟次数
    ai_rate_limit_per_minute: int = 20

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """兼容三种写法：JSON 数组、逗号分隔、空值。

        pydantic-settings 默认按 JSON 解析复杂类型，直接写
        ``CORS_ORIGINS=http://a,http://b`` 会报解析错误，因此用 NoDecode
        关闭自动解析，在这里统一处理。
        """
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return []
                return parsed if isinstance(parsed, list) else []
            return [item.strip() for item in text.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """获取配置单例（带缓存，测试中可 clear 后重载）。"""
    return Settings()