"""认证路由：登录签发令牌、获取当前用户。

- ``POST /auth/login``：用户名 + 密码 → 令牌与用户信息（**免鉴权**，由 AuthMiddleware 放行）。
- ``GET /auth/me``：返回当前登录用户及其权限集（需登录，由 AuthMiddleware 注入
  ``request.state.user``）。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.rbac import ROLE_LABELS, user_permission_map
from app.core.database import async_session_factory
from app.core.log_middleware import client_ip
from app.core.security import TokenError, create_token, revoke_token, verify_password
from app.core.deps import get_db
from app.models.login_log import LoginLog
from app.repositories.user_repo import UserRepository
from app.schemas.common import ok
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])

# —— 登录限流（P2：防暴力破解 / 账号枚举）——
# 滑动窗口：同一「IP + 用户名」在窗口内失败次数超阈值即临时锁定。
# 限流状态迁至 Redis 共享缓存（多实例一致）；无 Redis 时降级为进程内字典，
# 查询/写入异常均 fail-open，不阻塞正常登录。
_LOGIN_WINDOW = 300  # 统计窗口（秒）
_LOGIN_MAX_FAILS = 5  # 窗口内最大失败次数

from app.core.cache import cache  # noqa: E402


def _login_rate_key(username: str, request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{username.strip().lower()}"


async def _login_failures_get(key: str) -> list[float]:
    try:
        v = await cache.get(f"ratelimit:login:{key}")
        return v if isinstance(v, list) else []
    except Exception:
        return []


async def _login_allowed(key: str) -> bool:
    now = time.time()
    tries = [t for t in await _login_failures_get(key) if now - t < _LOGIN_WINDOW]
    return len(tries) < _LOGIN_MAX_FAILS


async def _record_login_failure(key: str) -> None:
    tries = [t for t in await _login_failures_get(key) if time.time() - t < _LOGIN_WINDOW]
    tries.append(time.time())
    try:
        await cache.set(f"ratelimit:login:{key}", tries, ttl=_LOGIN_WINDOW)
    except Exception:
        pass


async def _clear_login_failures(key: str) -> None:
    try:
        await cache.delete(f"ratelimit:login:{key}")
    except Exception:
        pass


async def _write_login_log(
    request: Request,
    *,
    username: str,
    action: str,
    status: str,
    user_id: str | None = None,
) -> None:
    """写一条登录日志（独立会话，失败静默——绝不影响认证流程）。"""
    try:
        async with async_session_factory() as session:
            session.add(
                LoginLog(
                    user_id=user_id,
                    username=username[:64],
                    action=action,
                    status=status,
                    ip=client_ip(request),
                )
            )
            await session.commit()
    except Exception:
        pass


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    username: str
    display_name: str | None
    role: str
    role_label: str
    permissions: dict


def _user_info(user) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "permissions": user_permission_map(user),
    }


@router.post("/login")
async def login(body: LoginRequest, request: Request, session: AsyncSession = Depends(get_db)):
    repo = UserRepository(session)
    key = _login_rate_key(body.username, request)
    # 滑动窗口限流：超阈值直接拒绝，避免账号枚举 / 暴力破解。
    if not await _login_allowed(key):
        raise AppError(
            status_code=429,
            code=429,
            message="登录尝试过于频繁，请稍后再试",
        )
    user = await repo.get_by_username(body.username.strip())
    # 统一错误信息，避免暴露账号是否存在（用户枚举防护）。
    if not user or not await asyncio.to_thread(
        verify_password, body.password, user.password_hash, user.salt
    ):
        await _record_login_failure(key)
        await _write_login_log(request, username=body.username.strip(), action="login", status="failed")
        raise AppError(status_code=401, code=401, message="用户名或密码错误")
    if user.disabled:
        raise AppError(status_code=403, code=403, message="该账号已被禁用")
    # 登录成功：清空失败计数。
    await _clear_login_failures(key)
    token = create_token(sub=user.id, username=user.username, role=user.role)
    await _write_login_log(request, username=user.username, action="login", status="success", user_id=user.id)
    return ok({"token": token, "user": _user_info(user)})


@router.get("/me")
async def me(request: Request, session: AsyncSession = Depends(get_db)):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未认证")
    repo = UserRepository(session)
    db_user = await repo.get(user["sub"])
    if not db_user or db_user.disabled:
        raise HTTPException(status_code=401, detail="账号不存在或已禁用")
    return ok(_user_info(db_user))


@router.post("/refresh")
async def refresh(request: Request, session: AsyncSession = Depends(get_db)):
    """令牌刷新（轮换）：用当前有效令牌换取新令牌，并立即吊销旧令牌（单次使用，防重放）。

    需登录（AuthMiddleware 注入 ``request.state.user``）。旧令牌在刷新后即失效，
    实现滑动会话而无需服务端存储会话状态；新令牌有效期自签发时刻重新计算。
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未认证")
    old_payload = dict(user)
    repo = UserRepository(session)
    db_user = await repo.get(user["sub"])
    if not db_user or db_user.disabled:
        raise HTTPException(status_code=401, detail="账号不存在或已禁用")
    # 吊销旧令牌（单次使用）。
    await revoke_token(old_payload)
    token = create_token(sub=db_user.id, username=db_user.username, role=db_user.role)
    # 令牌轮换是登录态的派生事件（高频、无业务语义），不留审计，避免刷屏。
    return ok({"token": token, "user": _user_info(db_user)})


@router.post("/logout")
async def logout(request: Request):
    """注销：将当前令牌加入黑名单，使其立即失效（至原过期时刻）。"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未认证")
    await revoke_token(dict(user))
    await _write_login_log(
        request,
        username=user.get("user_name") or "",
        action="logout",
        status="success",
        user_id=user.get("sub"),
    )
    return ok()


@router.get("/default-credentials-active")
async def default_credentials_active(session: AsyncSession = Depends(get_db)):
    """公开探针：默认管理员(admin)是否仍使用初始密码。

    供登录页智能隐藏「默认账号 admin / admin123」提示——一旦修改密码即不再展示。
    仅返回一个布尔，不泄露任何账号明细。
    """
    repo = UserRepository(session)
    admin = await repo.get_by_username("admin")
    active = bool(admin) and await asyncio.to_thread(
        verify_password,
        settings.INITIAL_ADMIN_PASSWORD,
        admin.password_hash,
        admin.salt,
    )
    return ok({"active": active})
