"""账号管理路由（增删改查）。

全部受 RBAC 保护：
- 列表：需 ``account:view``（仅管理员具备）。
- 创建 / 编辑 / 删除：需 ``account:edit``（仅管理员具备）。

守卫规则：
- 禁止删除自己的账号（避免把自己锁在门外）。
- 禁止删除 / 降级 / 禁用最后一个有效管理员（保证系统始终有可登录的管理员）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.exceptions import AppError
from app.core.rbac import (
    ROLE_LABELS,
    default_permissions,
    normalize_permissions,
    require_permission,
    user_permission_map,
)
from app.core.security import hash_password
from app.repositories.user_repo import UserRepository
from app.schemas.account import AccountCreate, AccountOut, AccountUpdate
from app.schemas.common import ok

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _to_out(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "permissions": user_permission_map(user),
        "disabled": bool(user.disabled),
        "created_at": user.created_at,
    }


@router.get("", dependencies=[Depends(require_permission("account:view"))])
async def list_accounts(
    keyword: str | None = None,
    page: int = 1,
    size: int = 20,
    session: AsyncSession = Depends(get_db),
):
    repo = UserRepository(session)
    rows, total = await repo.list(keyword=keyword, page=page, size=size)
    return ok({
        "items": [_to_out(u) for u in rows],
        "total": total,
        "page": page,
        "size": size,
    })


@router.post(
    "",
    dependencies=[Depends(require_permission("account:edit"))],
)
async def create_account(body: AccountCreate, session: AsyncSession = Depends(get_db)):
    repo = UserRepository(session)
    if await repo.get_by_username(body.username):
        raise AppError(status_code=409, code=409, message="用户名已存在")
    password_hash, salt = hash_password(body.password)
    # 管理员忽略权限字段（恒全权限）；普通用户存储映射，缺省全模块只读。
    if body.role == "admin":
        permissions = None
    else:
        permissions = (
            normalize_permissions(body.permissions)
            if body.permissions
            else default_permissions()
        )
    user = await repo.create(
        username=body.username,
        password_hash=password_hash,
        salt=salt,
        role=body.role,
        display_name=body.display_name,
        permissions=permissions,
    )
    await session.commit()
    return ok(_to_out(user))


@router.put(
    "/{user_id}",
    dependencies=[Depends(require_permission("account:edit"))],
)
async def update_account(
    user_id: str, body: AccountUpdate, session: AsyncSession = Depends(get_db)
):
    repo = UserRepository(session)
    user = await repo.get(user_id)
    if not user:
        raise AppError(status_code=404, code=404, message="账号不存在")

    # 末管理员守卫：若目标为有效管理员，且本次会使其失去管理员/被禁用，且系统中无其他
    # 有效管理员，则拒绝，避免锁死。
    will_lose_admin = (body.role is not None and body.role != "admin") or (
        body.disabled is not None and body.disabled is True
    )
    if user.role == "admin" and not user.disabled and will_lose_admin:
        others = await repo.count_admins()
        if others <= 1:
            raise AppError(
                status_code=409,
                code=409,
                message="至少需保留一名有效管理员，无法降级或禁用该账号",
            )

    if body.display_name is not None:
        user.display_name = body.display_name or None
    if body.role is not None:
        user.role = body.role
    if body.disabled is not None:
        user.disabled = body.disabled
    if body.password:
        user.password_hash, user.salt = hash_password(body.password)
    # 细粒度权限映射：仅普通用户生效，管理员恒全权限（NULL）。
    if user.role == "admin":
        user.permissions = None
    else:
        if body.permissions is not None:
            user.permissions = normalize_permissions(body.permissions)
        elif body.role is not None and user.permissions is None:
            # 由 admin 降级为 user 且未提供权限 -> 默认只读
            user.permissions = default_permissions()
    await session.commit()
    return ok(_to_out(user))


@router.delete(
    "/{user_id}",
    dependencies=[Depends(require_permission("account:edit"))],
)
async def delete_account(
    user_id: str, request: Request, session: AsyncSession = Depends(get_db)
):
    current = getattr(request.state, "user", None)
    if current and current.get("sub") == user_id:
        raise AppError(status_code=409, code=409, message="不能删除当前登录的账号")

    repo = UserRepository(session)
    user = await repo.get(user_id)
    if not user:
        raise AppError(status_code=404, code=404, message="账号不存在")

    if user.role == "admin" and not user.disabled:
        others = await repo.count_admins()
        if others <= 1:
            raise AppError(
                status_code=409,
                code=409,
                message="至少需保留一名有效管理员，无法删除该账号",
            )

    await repo.delete(user)
    await session.commit()
    return ok(None)
