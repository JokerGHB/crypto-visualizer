"""应用配置：统一从环境变量读取。

所有可配置项集中在此，禁止在业务代码里散落 os.getenv 调用。
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/app/config.py → 上溯两级得到项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _env_files() -> tuple[Path, ...]:
    """按优先级返回候选 .env 路径。

    项目约定配置文件放在仓库根目录，但后端常从 backend/ 启动，
    相对路径 ".env" 会失效。这里显式列出绝对路径，两处都能读到。
    同时也接受在 backend/ 下放一份覆盖用的 .env。
    """
    candidates = (
        Path.cwd() / ".env",  # 当前工作目录（兼容从任意目录启动）
        _PROJECT_ROOT / ".env",  # 项目根（推荐位置）
        Path(__file__).resolve().parent.parent / ".env",  # backend/.env（覆盖用）
    )
    seen: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.append(path)
    return tuple(seen)


class Settings(BaseSettings):
    """应用配置。

    优先级：真实环境变量 > .env 文件 > 代码默认值。
    因此密钥可只放环境变量，不必写入任何文件。
    """

    model_config = SettingsConfigDict(
        env_file=_env_files(),
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
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # AI 服务
    ai_enabled: bool = True
    ai_base_url: str = ""
    # 密钥来源按优先级依次尝试多个环境变量名，便于与不同习惯的配置共存。
    # GPT_API_KEY 为当前约定的主名称，AI_API_KEY 保留向后兼容。
    ai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GPT_API_KEY",
            "AI_API_KEY",
            "OPENAI_API_KEY",
        ),
    )
    ai_model: str = ""
    # 实测该服务端点首字节延迟 10~45 秒波动，10 秒会导致稳定超时降级。
    # 流式输出下用户会先看到文字逐字出现，因此放宽到 90 秒可接受。
    ai_timeout: float = 90.0

    # 限流：AI 接口每用户每分钟次数
    ai_rate_limit_per_minute: int = 20

    # 密钥来源标记，便于排查「到底从哪读到的」
    ai_api_key_source: str = ""

    def masked(self) -> dict[str, object]:
        """返回可安全写入日志的配置摘要。

        密钥类字段一律脱敏：即使日志被收集或提交，也不会泄露。
        连通性排查看「是否已配置」和「末尾 4 位」就够了。
        """
        key = self.ai_api_key
        return {
            "debug": self.debug,
            "database_url": self.database_url.split("@")[-1]
            if "@" in self.database_url
            else self.database_url,
            "jwt_secret_configured": self.jwt_secret
            != "dev-secret-change-me-in-production",
            "ai_enabled": self.ai_enabled,
            "ai_base_url": self.ai_base_url or "(未配置)",
            "ai_model": self.ai_model or "(未配置)",
            "ai_api_key": f"***{key[-4:]}" if len(key) > 4 else ("(未配置)" if not key else "***"),
            "ai_available": bool(self.ai_enabled and self.ai_base_url and self.ai_api_key),
        }

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

    def resolve_key_source(self) -> str:
        """检测 AI 密钥来自哪个环境变量名，仅用于日志排查。

        只返回变量名，不返回值本身，避免密钥进入日志。
        """
        for name in ("GPT_API_KEY", "AI_API_KEY", "OPENAI_API_KEY"):
            if os.environ.get(name, "").strip():
                return name
        # 环境变量没有，则可能来自 .env 文件
        return ".env 文件" if self.ai_api_key else "(未配置)"

    def startup_report(self) -> str:
        """启动自检摘要：说明关键配置是否就绪，缺失时给出可操作提示。"""
        lines = ["配置自检:"]
        info = self.masked()
        lines.append(f"  DEBUG            = {info['debug']}")
        lines.append(f"  DATABASE_URL     = {info['database_url']}")
        lines.append(f"  JWT_SECRET       = {'已自定义' if info['jwt_secret_configured'] else '使用开发默认值（生产必须替换）'}")
        lines.append(f"  AI_ENABLED       = {info['ai_enabled']}")
        lines.append(f"  AI_BASE_URL      = {info['ai_base_url']}")
        lines.append(f"  AI_MODEL         = {info['ai_model']}")
        lines.append(f"  AI_API_KEY       = {info['ai_api_key']}")
        lines.append(f"  密钥来源         = {self.resolve_key_source()}")
        if info["ai_available"]:
            lines.append("  AI 状态          = 已就绪")
        else:
            lines.append("  AI 状态          = 未就绪，将降级为本地讲解")
            if not self.ai_api_key:
                lines.append("     → 请设置环境变量 GPT_API_KEY，或在 .env 中填写 AI_API_KEY")
            if not self.ai_base_url:
                lines.append("     → 请设置 AI_BASE_URL")
        return "\n".join(lines)


@lru_cache
def get_settings() -> Settings:
    """获取配置单例（带缓存，测试中可 clear 后重载）。"""
    return Settings()