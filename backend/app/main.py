"""RackVisio 机柜 3D 可视化平台后端入口。

- 启动时建表（create_all）并写入默认管理员账号（不写入演示业务数据，生产库初始为空）。
- 所有 v1 路由挂载在 ``settings.API_PREFIX``（默认 /api/v1）之下。
- 启用 CORS 便于前端（Vite dev server）跨端口调用。
- 中间件自 ``app/core/`` 独立文件引入（A-01 拆分）：
  ``AuthMiddleware``（鉴权）、``SecurityHeadersMiddleware``（安全头）、
  ``RequestTimingMiddleware``（计时/慢请求）、``GlobalRateLimitMiddleware``（全局限流）、
  ``OperationLogMiddleware``（请求级操作日志）。
"""

from __future__ import annotations

import logging
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app")

from app.api.v1 import (
    accounts,
    auth,
    consumables,
    devices,
    hardwares,
    interfaces,
    links,
    logs,
    meta,
    mount_records,
    racks,
    rooms,
    stats,
)
from app.core.auth_middleware import AuthMiddleware
from app.core.cache import cache
from app.core.config import settings
from app.core.database import async_session_factory, engine, init_models
from app.core.log_middleware import OperationLogMiddleware
from app.core.exceptions import AppError
from app.core.rate_limit import GlobalRateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.timing_middleware import RequestTimingMiddleware
from app.db.init_db import migrate, seed_data
from sqlalchemy import text

# 重新导出，便于测试导入。
__all__ = ["app"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：建表 → 迁移 → 种子数据，并启动后台日志清理任务。"""
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
    # 优雅关闭：释放 DB 连接池与 Redis 连接，避免连接泄漏 / 句柄耗尽。
    try:
        await engine.dispose()
    except Exception:
        logger.warning("engine.dispose 失败", exc_info=True)
    try:
        await cache.close()
    except Exception:
        logger.warning("cache.close 失败", exc_info=True)


app = FastAPI(
    title="RackVisio 机柜 3D 可视化",
    version="1.0.0",
    lifespan=lifespan,
)


# 允许的前端跨域源（显式白名单，禁止 "*" + allow_credentials 的危险组合）。
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
# 中间件执行顺序（外层→内层）= 注册顺序的反序。将 CORS 注册为最后一项使其处于最外层，
# 确保鉴权中间件提前返回 401/403 时响应仍经过 CORS 中间件、带上跨域头，避免开发期跨域 401 白屏。
# 操作日志中间件注册为第一项 → 处于最内层（AuthMiddleware 之内），
# 能拿到 request.state.user，对所有写请求自动落 operation_logs（原生请求级日志）。
app.add_middleware(OperationLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
# 计时中间件注册为最后一项 → 处于最外层，包裹完整中间件链（含 CORS/鉴权），
# 度量端到端耗时并注入 X-Request-ID。
app.add_middleware(RequestTimingMiddleware)
# 全站限流置于计时之内、业务路由之前，异常 fail-open，多实例经 Redis 共享计数。
app.add_middleware(GlobalRateLimitMiddleware)

# 挂载全部 v1 路由（前缀统一为 /api/v1）。
# 操作日志由 OperationLogMiddleware 请求级自动记录，端点零侵入；
# 登录日志由认证端点写入 login_logs，两者在前端分别以二级菜单展示。
for module in (rooms, racks, devices, interfaces, links, stats, mount_records, auth, accounts, consumables, hardwares, meta, logs):
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


@app.exception_handler(StarletteHTTPException)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """任意 ``HTTPException``（含路由未匹配 404 与各端点直接抛出的 4xx/5xx）→ 统一信封。

    注意：本环境安装的 FastAPI 中 ``fastapi.HTTPException`` 与 ``starlette.exceptions.
    HTTPException`` 并非同一类（路由未匹配的 404 抛的是后者），故两者都注册以确保
    统一信封覆盖全部 4xx/5xx（含 404）。原先默认 ``{"detail": ...}`` 与统一信封
    ``{"code","message","data"}`` 不一致，此处归一到相同结构（code 取状态码）。
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail if isinstance(exc.detail, str) else "请求错误",
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底 → 500 统一信封。

    避免将堆栈/内部实现细节直接透传给前端；同时记录完整堆栈便于排查。
    """
    logger.error("未捕获异常: %s\n%s", exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": None},
    )


@app.get("/health")
async def health():
    # 依赖探活：DB(SELECT 1) + Redis(ping)，统一信封。
    # 任一关键依赖不可用时返回 503，便于 k8s/编排探针判定「不健康」。
    db_ok, db_detail = True, "up"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:  # 探测失败 fail-close：标记为不可用，避免误报健康
        db_ok, db_detail = False, str(e)[:200]
    redis_ok, redis_detail = True, "up"
    if settings.REDIS_ENABLED:
        try:
            redis_ok = await cache.ping()
            redis_detail = "up" if redis_ok else "ping 失败"
        except Exception as e:
            redis_ok, redis_detail = False, str(e)[:200]
    else:
        redis_detail = "disabled"
    healthy = db_ok and redis_ok
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "code": 0 if healthy else 503,
            "message": "ok" if healthy else "degraded",
            "data": {
                "status": "ok" if healthy else "degraded",
                "db": {"ok": db_ok, "detail": db_detail},
                "redis": {"ok": redis_ok, "detail": redis_detail},
            },
        },
    )
