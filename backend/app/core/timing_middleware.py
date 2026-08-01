"""请求计时与慢请求日志中间件（A-01：自 main.py 拆分）。

- 正常请求 INFO 级单行日志；超过阈值（默认 1000ms）降为 WARNING 便于告警。
- 注入 ``X-Request-ID`` 响应头，便于链路追踪与日志关联。
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("app")


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """请求计时与慢请求日志：method/path/status/duration_ms/request_id。"""

    _SLOW_MS = 1000.0

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        log_method = logger.warning if duration_ms > self._SLOW_MS else logger.info
        log_method(
            "request %s %s -> %d (%.1fms, rid=%s)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
