"""安全响应头中间件（A-01：自 main.py 拆分）。

统一注入安全响应头（CSP / X-Frame-Options / nosniff 等）：
- 业务接口使用严格 CSP（无 'unsafe-inline'）；
- API 文档路由（/docs、/redoc、/openapi.json）针对性放宽，放行 jsdelivr CDN
  的 Swagger UI / ReDoc 脚本与样式，避免文档页白屏；
- ``frame-ancestors 'none'`` 禁止 iframe 嵌入（点击劫持防护）。
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """统一注入安全响应头（CSP / X-Frame-Options / nosniff 等）。"""

    # 业务接口（JSON）响应本就不含内联脚本/样式；移除 'unsafe-inline' 收紧 XSS 防护面。
    _CSP = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "style-src 'self'; "
        "script-src 'self'; "
        "frame-ancestors 'none'"
    )

    # API 文档路由依赖公网 CDN（cdn.jsdelivr.net）的脚本与样式，
    # 严格 CSP 会拦截其跨域脚本执行导致页面白屏，故仅对此类路径放宽。
    _CSP_DOCS = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "frame-ancestors 'none'"
    )

    _DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        csp = self._CSP_DOCS if request.url.path in self._DOCS_PATHS else self._CSP
        response.headers.setdefault("Content-Security-Policy", csp)
        return response
