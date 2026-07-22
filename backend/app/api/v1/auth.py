"""认证路由：登录签发令牌、获取当前用户。

- ``POST /auth/login``：用户名 + 密码 → 令牌与用户信息（**免鉴权**，由 AuthMiddleware 放行）。
- ``GET /auth/me``：返回当前登录用户及其权限集（需登录，由 AuthMiddleware 注入
  ``request.state.user``）。
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.exceptions import AppError
from app.core.rbac import ROLE_LABELS, user_permission_map
from app.core.security import TokenError, create_token, verify_password
from app.core.deps import get_db
from app.repositories.user_repo import UserRepository
from app.schemas.common import ok
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])

# —— 登录限流（P2：防暴力破解 / 账号枚举）——
# 滑动窗口：同一「IP + 用户名」在窗口内失败次数超阈值即临时锁定。
_LOGIN_WINDOW = 300  # 统计窗口（秒）
_LOGIN_MAX_FAILS = 5  # 窗口内最大失败次数
_login_failures: dict[str, list[float]] = defaultdict(list)


def _login_rate_key(username: str, request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{username.strip().lower()}"


def _login_allowed(key: str) -> bool:
    now = time.time()
    tries = _login_failures[key]
    # 仅保留窗口内的失败记录。
    tries[:] = [t for t in tries if now - t < _LOGIN_WINDOW]
    return len(tries) < _LOGIN_MAX_FAILS


def _record_login_failure(key: str) -> None:
    _login_failures[key].append(time.time())


def _clear_login_failures(key: str) -> None:
    _login_failures.pop(key, None)


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
    if not _login_allowed(key):
        raise AppError(
            status_code=429,
            code=429,
            message="登录尝试过于频繁，请稍后再试",
        )
    user = await repo.get_by_username(body.username.strip())
    # 统一错误信息，避免暴露账号是否存在（用户枚举防护）。
    if not user or not verify_password(body.password, user.password_hash, user.salt):
        _record_login_failure(key)
        raise AppError(status_code=401, code=401, message="用户名或密码错误")
    if user.disabled:
        raise AppError(status_code=403, code=403, message="该账号已被禁用")
    # 登录成功：清空失败计数。
    _clear_login_failures(key)
    token = create_token(sub=user.id, username=user.username, role=user.role)
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
