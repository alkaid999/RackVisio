"""RackVisio 机柜 3D 可视化平台后端入口。

- 启动时建表（create_all）并写入默认管理员账号（不写入演示业务数据，生产库初始为空）。
- 所有 v1 路由挂载在 ``settings.API_PREFIX``（默认 /api/v1）之下。
- 启用 CORS 便于前端（Vite dev server）跨端口调用。
- ``AuthMiddleware`` 对除登录/健康检查/文档外的所有 ``/api/v1`` 请求强制鉴权。
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import (
    accounts,
    audit,
    auth,
    consumables,
    devices,
    interfaces,
    links,
    meta,
    mount_records,
    racks,
    rooms,
    stats,
)
from app.core.config import settings
from app.core.database import async_session_factory, init_models
from app.core.exceptions import AppError
from app.core.security import TokenError, verify_token
from app.db.init_db import migrate, seed_data
from app.repositories.user_repo import UserRepository

# 重新导出，便于测试导入。
__all__ = ["app"]


# 禁用账号令牌即时失效：仅缓存「已禁用」结果（禁用态不变化），启用态每次实时查库，
# 确保管理员禁用账号后令牌立即失效（P1）。
_user_disabled_cache: dict[str, tuple[float, bool]] = {}
_DISABLED_CACHE_TTL = 60.0


async def _is_user_disabled(sub: str) -> bool:
    """查询用户是否已禁用。

    - 已禁用：缓存 60s（禁用态短期不变），避免重复查库。
    - 启用中：不缓存，每次实时查库，确保禁用操作即时生效。
    - 查询异常 fail-open，避免 DB 抖动导致全站 401。
    """
    cached = _user_disabled_cache.get(sub)
    if cached and cached[0] > time.time():
        return cached[1]
    disabled = False
    try:
        async with async_session_factory() as session:
            user = await UserRepository(session).get(sub)
            disabled = bool(user and user.disabled)
    except Exception:
        # 查询异常时 fail-open，避免 DB 抖动导致全站 401。
        disabled = False
    if disabled:
        _user_disabled_cache[sub] = (time.time() + _DISABLED_CACHE_TTL, True)
    return disabled


class AuthMiddleware(BaseHTTPMiddleware):
    """统一鉴权中间件：校验 ``Authorization: Bearer <token>``，写入 ``request.state.user``。

    放行清单（无需 token）：
    - ``OPTIONS`` 预检（CORS）
    - ``/health``、``/docs``、``/redoc``、``/openapi.json``
    - ``/api/v1/auth/login``（登录签发令牌本身）
    - ``/api/v1/auth/default-credentials-active``（登录页公开探针：默认管理员是否仍用初始密码）
    其余 ``/api/v1`` 请求必须携带有效令牌，否则返回 401 信封。
    """

    _PUBLIC_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json")
    _PUBLIC_AUTH_PATHS = (
        f"{settings.API_PREFIX}/auth/login",
        f"{settings.API_PREFIX}/auth/default-credentials-active",
    )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS":
            return await call_next(request)
        if path in self._PUBLIC_PREFIXES or path in self._PUBLIC_AUTH_PATHS:
            return await call_next(request)

        if path.startswith(settings.API_PREFIX):
            auth_header = request.headers.get("Authorization", "")
            token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
            if not token:
                return JSONResponse(
                    status_code=401,
                    content={"code": 401, "message": "未登录或登录已过期", "data": None},
                )
            try:
                payload = verify_token(token)
            except TokenError as exc:
                return JSONResponse(
                    status_code=401,
                    content={"code": 401, "message": str(exc) or "登录已过期", "data": None},
                )
            # 禁用账号令牌即时失效（P1：原先仅靠登录拦截，已签发令牌仍可用）。
            if await _is_user_disabled(payload.get("sub")):
                return JSONResponse(
                    status_code=401,
                    content={"code": 401, "message": "账号已被禁用", "data": None},
                )
            request.state.user = payload

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：建表 → 迁移 → 种子数据。"""
    # 缓存后端启动自检：真正 ping 一次 Redis，避免连不上时静默降级无人察觉。
    import logging
    _cache_log = logging.getLogger("cache")
    if settings.REDIS_ENABLED:
        try:
            import redis.asyncio as aioredis
            # 与 RedisCache 保持一致用 RESP2（protocol=2）：Windows 原生
            # Redis 5.x 无 HELLO 命令，默认协议握手会失败。
            _probe = aioredis.from_url(settings.REDIS_URL, decode_responses=False, protocol=2)
            await _probe.ping()
            _cache_log.info("Cache backend: Redis 已连接 (%s)", settings.REDIS_URL)
        except Exception as e:
            _cache_log.warning(
                "Cache backend: 内存模式 (REDIS_ENABLED=true 但 Redis 连接失败: %s)", e
            )
    else:
        _cache_log.info("Cache backend: 内存模式 (REDIS_ENABLED=false)")
    await init_models()
    async with async_session_factory() as session:
        await migrate(session)
        await seed_data(session)
    yield


app = FastAPI(
    title="RackVisio 机柜 3D 可视化",
    version="1.0.0",
    lifespan=lifespan,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """统一注入安全响应头（CSP / X-Frame-Options / nosniff 等）。

    说明：script-src 保留 'unsafe-inline' 以兼容 Vite 开发期注入脚本；
    真正的 XSS 风险已在各视图层通过转义彻底消除（见 Room3DView/Rack3DView）。

    对 FastAPI 自带的 API 文档路由（/docs、/redoc、/openapi.json）针对性放宽 CSP，
    放行其从 jsdelivr CDN 加载 Swagger UI / ReDoc 的脚本与样式，避免文档页白屏；
    其余业务接口仍使用严格 CSP。
    """

    _CSP = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
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


# 允许的前端跨域源（显式白名单，禁止 "*" + allow_credentials 的危险组合）。
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(AuthMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# 挂载全部 v1 路由（前缀统一为 /api/v1）。
for module in (rooms, racks, devices, interfaces, links, stats, mount_records, auth, accounts, consumables, meta, audit):
    app.include_router(module.router, prefix=settings.API_PREFIX)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """统一业务异常 → 信封 ``{"code":<int>, "message":..., "data": null}``。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Pydantic 入参校验失败 → 422 信封。"""
    return JSONResponse(
        status_code=422,
        content={"code": 422, "message": "参数校验失败", "data": None},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
