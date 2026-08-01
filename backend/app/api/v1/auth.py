"""认证路由：登录签发令牌、获取当前用户。

- ``POST /auth/login``：用户名 + 密码 → 令牌与用户信息（**免鉴权**，由 AuthMiddleware 放行）。
- ``GET /auth/me``：返回当前登录用户及其权限集（需登录，由 AuthMiddleware 注入
  ``request.state.user``）。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.rbac import ROLE_LABELS, user_permission_map
from app.core.database import async_session_factory
from app.core.log_middleware import client_ip
from app.core.security import (
    TokenError,
    create_token,
    hash_password,
    revoke_token,
    verify_password,
)
from app.core.deps import get_db
from app.models.login_log import LoginLog
from app.repositories.user_repo import UserRepository
from app.schemas.common import ok
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# —— 登录限流（P2：防暴力破解 / 账号枚举）——
# 滑动窗口：同一「IP + 用户名」在窗口内失败次数超阈值即临时锁定。
# 限流状态迁至 Redis 共享缓存（多实例一致）；无 Redis 时降级为进程内字典。
# 限流状态查询失败时 **fail-close**（保守视为已达阈值），绝不放开暴力破解防护。
# Q-03：窗口/阈值收敛到 Settings（LOGIN_RATE_WINDOW / LOGIN_MAX_FAILS，可 .env 覆盖）。

from app.core.cache import cache  # noqa: E402


def _login_rate_key(username: str, request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{username.strip().lower()}"


async def _login_failures_get(key: str) -> list[float]:
    # 严格读取：缓存故障（ok=False）时保守返回满次数，触发限流而非放行
    # （fail-open 会让 Redis 抖动期间的暴力破解防护完全失效）。
    value, ok = await cache.get_strict(f"ratelimit:login:{key}")
    if not ok:
        logger.error("登录限流状态查询失败（保守触发限流）", exc_info=True)
        return [time.time()] * settings.LOGIN_MAX_FAILS
    return value if isinstance(value, list) else []


async def _login_allowed(key: str) -> bool:
    now = time.time()
    tries = [
        t for t in await _login_failures_get(key)
        if now - t < settings.LOGIN_RATE_WINDOW
    ]
    return len(tries) < settings.LOGIN_MAX_FAILS


async def _record_login_failure(key: str) -> None:
    tries = [
        t for t in await _login_failures_get(key)
        if time.time() - t < settings.LOGIN_RATE_WINDOW
    ]
    tries.append(time.time())
    try:
        await cache.set(f"ratelimit:login:{key}", tries, ttl=settings.LOGIN_RATE_WINDOW)
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


class ChangePasswordRequest(BaseModel):
    """修改当前登录用户密码（验证旧密码防越权/防 CSRF 链）。"""

    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class UserInfo(BaseModel):
    id: str
    username: str
    display_name: str | None
    role: str
    role_label: str
    permissions: dict
    # 强制改密标记（S-02）：初始管理员首次登录后为 True，前端据此强制跳转改密页。
    must_change_password: bool = False


def _user_info(user) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "permissions": user_permission_map(user),
        "must_change_password": bool(user.must_change_password),
    }


@router.post("/login")
async def login(body: LoginRequest, request: Request, session: AsyncSession = Depends(get_db)):
    repo = UserRepository(session)
    key = _login_rate_key(body.username, request)
    # 滑动窗口限流：超阈值直接拒绝，避免账号枚举 / 暴力破解。
    if not await _login_allowed(key):
        raise AppError(
            status_code=429,
            message="登录尝试过于频繁，请稍后再试",
        )
    user = await repo.get_by_username(body.username.strip())
    # 统一错误信息，避免暴露账号是否存在（用户枚举防护）。
    if not user or not await asyncio.to_thread(
        verify_password, body.password, user.password_hash, user.salt
    ):
        await _record_login_failure(key)
        await _write_login_log(request, username=body.username.strip(), action="login", status="failed")
        raise AppError(status_code=401, message="用户名或密码错误")
    if user.disabled:
        raise AppError(status_code=403, message="该账号已被禁用")
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


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest, request: Request, session: AsyncSession = Depends(get_db)
):
    """当前登录用户修改自己的密码（S-02 强制改密落地）。

    - 验证旧密码（防越权：他人拿到令牌也无法在不知旧密码时改密）。
    - 成功后清除 ``must_change_password`` 标记并吊销旧令牌、签发新令牌，
      登录态无缝延续（初始管理员首次登录强制改密后直接进入系统）。
    - 记一条 login_logs（action=change_password），改密属敏感操作，须留痕
      （/auth/* 被操作日志中间件豁免，故走登录日志表）。
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未认证")
    repo = UserRepository(session)
    db_user = await repo.get(user["sub"])
    if not db_user or db_user.disabled:
        raise HTTPException(status_code=401, detail="账号不存在或已禁用")
    if not await asyncio.to_thread(
        verify_password, body.old_password, db_user.password_hash, db_user.salt
    ):
        await _write_login_log(
            request,
            username=db_user.username,
            action="change_password",
            status="failed",
            user_id=db_user.id,
        )
        raise AppError(status_code=400, message="原密码错误")
    if body.old_password == body.new_password:
        raise AppError(status_code=400, message="新密码不能与原密码相同")
    db_user.password_hash, db_user.salt = await asyncio.to_thread(
        hash_password, body.new_password
    )
    db_user.must_change_password = False
    await session.commit()
    # 旧令牌作废，签发新令牌（无状态会话轮换），前端用新令牌继续。
    await revoke_token(dict(user))
    token = create_token(sub=db_user.id, username=db_user.username, role=db_user.role)
    await _write_login_log(
        request,
        username=db_user.username,
        action="change_password",
        status="success",
        user_id=db_user.id,
    )
    return ok({"token": token, "user": _user_info(db_user)})


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
async def default_credentials_active(request: Request, session: AsyncSession = Depends(get_db)):
    """公开探针：默认管理员(admin)是否仍使用初始密码。

    供登录页智能隐藏「默认账号 admin / admin123」提示——一旦修改密码即不再展示。
    仅返回一个布尔，不泄露任何账号明细。

    安全加固（S-07）：探针与 admin 的登录限流联动——若该来源 IP 对 admin 的
    登录尝试已被限流锁定（5 次失败 / 300s），探针同样返回 429。防止探针成为
    绕过登录限流的「默认凭据预言机」（攻击者可无限探测 admin 是否仍用初始密码，
    而正常登录路径受滑动窗口保护）。
    """
    key = _login_rate_key("admin", request)
    if not await _login_allowed(key):
        raise AppError(
            status_code=429,
            message="请求过于频繁，请稍后再试",
        )
    repo = UserRepository(session)
    admin = await repo.get_by_username("admin")
    active = bool(admin) and await asyncio.to_thread(
        verify_password,
        settings.INITIAL_ADMIN_PASSWORD,
        admin.password_hash,
        admin.salt,
    )
    return ok({"active": active})
