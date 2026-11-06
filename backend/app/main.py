"""FastAPI 应用入口。

挂载顺序有意为之：安全响应头在 CORS 之后加入，确保预检响应也带安全头。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.database import init_db
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import ai, auth, crypto, exercise, history

settings = get_settings()
logger = logging.getLogger("app.config")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表并打印配置自检。

    自检只打印脱敏信息（密钥仅显示末 4 位），必要时会提示缺失项，
    避免出现「AI 一直降级但不知道为什么」的排查困境。
    """
    init_db()
    logger.info(settings.startup_report())
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "AES 加解密全流程逐步可视化 + 步骤级 AI 辅导 + 练习模式。"
        "所有可视化数据来自后端统一生成的 Trace 契约。"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """业务异常统一包装。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """把 Pydantic 校验错误转成统一结构，并给出可读中文提示。"""
    details = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
        details.append(f"{loc}: {err.get('msg', '')}")
    return JSONResponse(
        status_code=422,
        content={
            "code": ErrorCode.INPUT_FORMAT,
            "message": "请求参数不合法：" + "；".join(details),
            "data": None,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """把框架层 HTTP 错误也包装成统一结构。"""
    code_map = {
        401: ErrorCode.TOKEN_INVALID,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        429: ErrorCode.RATE_LIMITED,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code_map.get(exc.status_code, ErrorCode.INTERNAL),
            "message": str(exc.detail),
            "data": None,
        },
    )


@app.get("/api/health", tags=["运维"])
def health() -> dict:
    """健康检查，供流水线与部署探活使用。"""
    return {"code": 0, "message": "ok", "data": {"status": "healthy"}}


app.include_router(auth.router)
app.include_router(crypto.router)
app.include_router(history.router)
app.include_router(exercise.router)
app.include_router(ai.router)