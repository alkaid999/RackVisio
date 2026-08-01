"""全站通用限流中间件（A-01：自 main.py 拆分）。

按客户端 IP 固定窗口限流，防接口被恶意刷量 / 爬取：
- 以「当前分钟 + IP」为桶，每分钟上限 ``_MAX_PER_MIN``；超出返回 429 信封。
- 豁免健康检查 / 文档 / 登录 / 默认凭据探针（避免锁定合法登录入口）。
- 限流状态存于共享缓存（Redis），多实例一致；缓存写入/读取异常 fail-open，
  绝不因限流组件故障阻塞正常业务。
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.cache import cache
from app.core.config import settings


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """全站通用限流（按客户端 IP 固定窗口）。

    Q-03：上限/窗口收敛到 Settings（RATE_LIMIT_PER_MIN / RATE_LIMIT_WINDOW）。
    """

    _EXEMPT_PATHS = (
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        f"{settings.API_PREFIX}/auth/login",
        f"{settings.API_PREFIX}/auth/default-credentials-active",
    )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in self._EXEMPT_PATHS:
            return await call_next(request)
        host = request.client.host if request.client else "unknown"
        minute = int(time.time() // settings.RATE_LIMIT_WINDOW)
        key = f"ratelimit:global:{host}:{minute}"
        try:
            count = await cache.get(key) or 0
            if isinstance(count, list):  # 防御：历史脏数据非 int 时重置
                count = 0
            if count >= settings.RATE_LIMIT_PER_MIN:
                return JSONResponse(
                    status_code=429,
                    content={"code": 429, "message": "请求过于频繁，请稍后再试", "data": None},
                )
            await cache.set(key, count + 1, ttl=settings.RATE_LIMIT_WINDOW)
        except Exception:
            # 限流组件异常 fail-open：不阻塞业务。
            pass
        return await call_next(request)
