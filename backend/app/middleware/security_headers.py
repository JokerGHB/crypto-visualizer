"""安全响应头中间件。

落实 Web 安全开发要求：
- XSS 缓解：CSP 限制脚本来源，配合前端不使用 v-html
- 点击劫持：X-Frame-Options
- MIME 嗅探：X-Content-Type-Options
- 信息泄露：Referrer-Policy
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# 前端为 SPA，脚本与样式来自自身；Element Plus 需要 style 内联，
# 因此 style-src 允许 'unsafe-inline'，但 script-src 仍严格限制。
CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """为所有响应添加安全响应头。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        # /docs 与 /redoc 需要内联脚本，故跳过 CSP 以免接口文档无法使用
        path = request.url.path
        if not (path.startswith("/docs") or path.startswith("/redoc") or path == "/openapi.json"):
            headers.setdefault("Content-Security-Policy", CSP_POLICY)
        return response