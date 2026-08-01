"""统一鉴权中间件（A-01：自 main.py 拆分为独立文件，便于维护与单测）。

职责：校验 ``Authorization: Bearer <token>``，写入 ``request.state.user``。

放行清单（无需 token）：
- ``OPTIONS`` 预检（CORS）
- ``/health``、``/docs``、``/redoc``、``/openapi.json``
- ``/api/v1/auth/login``（登录签发令牌本身）
- ``/api/v1/auth/default-credentials-active``（登录页公开探针：默认管理员是否仍用初始密码）
其余 ``/api/v1`` 请求必须携带有效令牌，否则返回 401 信封。

安全语义（S-04/S-05）：令牌吊销查询与用户禁用校验均 **fail-close**——缓存/DB
抖动时宁可误拒请求，也不能放行已注销/被禁用的令牌。
"""

from __future__ import annotations

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.cache import cache
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.security import TokenError, is_token_revoked, verify_token
from app.repositories.user_repo import UserRepository

logger = logging.getLogger("app")

# 禁用账号令牌即时失效：仅缓存「已禁用」结果（禁用态不变化），启用态每次实时查库，
# 确保管理员禁用账号后令牌立即失效（P1）。
# R-07：禁用态存共享缓存门面（Redis，多实例一致）而非模块级 dict——
# 模块级可变字典在多 worker 下各自独立（A worker 禁用、B worker 仍放行），
# 且「读-判-写」非原子；缓存门面天然线程安全、跨进程共享（Redis 不可达降级内存）。
_DISABLED_CACHE_TTL = 60.0


async def _is_user_disabled(sub: str) -> bool:
    """查询用户是否已禁用。

    - 已禁用：缓存 60s（禁用态短期不变），避免重复查库；缓存存共享门面，
      Redis 可用时跨 worker 一致（R-07）。
    - 启用中：不缓存，每次实时查库，确保禁用操作即时生效。
    - 查询异常 **fail-close**（视为禁用、拒绝访问）：禁用校验是安全关键判定，
      DB/缓存抖动时宁可误拒请求，也不能放行已被禁用的账号令牌（fail-open 会削弱
      「管理员禁用账号即时失效」的语义）。异常结果不缓存，避免瞬时故障被长期缓存。
    """
    # 先查共享缓存（严格读取：缓存故障 fail-close，不削弱 S-05 语义）。
    cached, ok = await cache.get_strict(f"user:disabled:{sub}")
    if not ok:
        logger.error("用户禁用态缓存查询失败（保守视为禁用）", exc_info=True)
        return True
    if cached:
        return True
    try:
        async with async_session_factory() as session:
            user = await UserRepository(session).get(sub)
            disabled = bool(user and user.disabled)
    except Exception:
        # 查询异常时 fail-close：保守视为禁用；不缓存，避免瞬时故障被长期缓存。
        logger.error("用户禁用状态查询失败（保守视为禁用）", exc_info=True)
        return True
    if disabled:
        # 缓存写入为非关键操作：失败静默（下次请求实时查库兜底）。
        try:
            await cache.set(f"user:disabled:{sub}", 1, ttl=_DISABLED_CACHE_TTL)
        except Exception:
            logger.warning("用户禁用态缓存写入失败（已忽略）", exc_info=True)
    return disabled


class AuthMiddleware(BaseHTTPMiddleware):
    """统一鉴权中间件：校验 Bearer 令牌 → ``request.state.user``。"""

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
            # 注销吊销（黑名单）：已主动 logout 的令牌即时失效（fail-close）。
            if await is_token_revoked(payload):
                return JSONResponse(
                    status_code=401,
                    content={"code": 401, "message": "令牌已注销，请重新登录", "data": None},
                )
            # 禁用账号令牌即时失效（P1：原先仅靠登录拦截，已签发令牌仍可用）。
            if await _is_user_disabled(payload.get("sub")):
                return JSONResponse(
                    status_code=401,
                    content={"code": 401, "message": "账号已被禁用", "data": None},
                )
            request.state.user = payload

        return await call_next(request)
