"""基于「模块 × 操作」的细粒度权限目录（RBAC）。

权限以**映射**形式表达，便于逐用户独立配置、并支持后续扩展新模块/新操作：

- 模块（MODULES）—— 声明式单一数据源：room / rack / device / link / account。
- 操作（OPERATIONS）—— view（查看）/ edit（编辑＝新增＋删除），二者可独立配置。

权限映射（数据库 ``User.permissions`` 的存储形态）::

    {
        "room":   {"view": True,  "edit": False},
        "device": {"view": True,  "edit": True},
        ...
    }

- 管理员（admin）：恒为超级用户，拥有全部模块的全部操作；其 ``permissions`` 字段为
  ``NULL``（不冗余存储，避免漂移）。
- 普通用户（user）：权限来自 ``User.permissions`` 映射，缺省回退为「全模块只读」。

解析时机：每次受保护请求**实时**从数据库读取该用户记录并展开其权限映射，因此管理员
在界面上修改某用户权限后会**立即生效**（无需重新登录）。
"""

from __future__ import annotations

from typing import Iterable, Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.exceptions import AppError
from app.models.user import User
from app.repositories.user_repo import UserRepository

# —— 权限目录（单一数据源；新增模块/操作只需扩展此处）——
MODULES = ("room", "rack", "device", "link", "account", "consumable")
OPERATIONS = ("view", "edit")

ALL_PERMISSIONS: list[str] = [f"{m}:{o}" for m in MODULES for o in OPERATIONS]

# 角色展示名（前后端共用，前端亦在 constants.js 镜像）。
ROLE_LABELS = {
    "admin": "管理员",
    "user": "普通用户",
}

# 模块 / 操作中文名（便于前端渲染与展示）。
MODULE_LABELS = {
    "room": "机房",
    "rack": "机柜",
    "device": "设备",
    "link": "链路",
    "account": "账号",
    "consumable": "耗材",
}

OPERATION_LABELS = {
    "view": "查看",
    "edit": "编辑",
}


def normalize_permissions(permissions: Optional[dict]) -> dict:
    """将任意输入清洗为合法权限映射。

    - 丢弃未知模块 / 未知操作；
    - 每个操作值归一成 ``bool``；
    - 未知或缺失的模块回退为全 False。
    返回：``{module: {"view": bool, "edit": bool}, ...}``（仅含已知模块）。
    """
    clean: dict[str, dict[str, bool]] = {}
    src = permissions or {}
    for module in MODULES:
        entry = src.get(module)
        if not isinstance(entry, dict):
            clean[module] = {op: False for op in OPERATIONS}
            continue
        clean[module] = {op: bool(entry.get(op, False)) for op in OPERATIONS}
    return clean


def default_permissions() -> dict:
    """普通用户缺省权限：全模块只读（view=True, edit=False）。"""
    return {m: {op: op == "view" for op in OPERATIONS} for m in MODULES}


def is_admin(role: str) -> bool:
    return role == "admin"


def user_permission_map(user: User) -> dict:
    """返回用户的有效权限映射（admin 恒为全 True）。"""
    if is_admin(user.role):
        return {m: {op: True for op in OPERATIONS} for m in MODULES}
    return normalize_permissions(getattr(user, "permissions", None)) or default_permissions()


def effective_permissions(user: User) -> set[str]:
    """展开为扁平 ``<module>:<action>`` 键集合（admin 为全集）。"""
    perms: set[str] = set()
    for module, ops in user_permission_map(user).items():
        for op, granted in ops.items():
            if granted:
                perms.add(f"{module}:{op}")
    return perms


async def _resolve_effective(request: Request, session: AsyncSession) -> set[str]:
    """实时解析当前请求用户的有效权限集合（带 request 级缓存）。"""
    cached = getattr(request.state, "effective_permissions", None)
    if cached is not None:
        return cached

    payload = getattr(request.state, "user", None)
    if not payload:
        raise HTTPException(status_code=401, detail="未认证")

    if is_admin(payload.get("role", "user")):
        eff = set(ALL_PERMISSIONS)
    else:
        user = await UserRepository(session).get(payload.get("sub"))
        if user is None:
            raise HTTPException(status_code=401, detail="用户不存在或已被删除")
        eff = effective_permissions(user)

    request.state.effective_permissions = eff
    return eff


async def get_current_user(request: Request) -> dict:
    """依赖：返回当前认证用户（JWT payload 字典），未认证则 401。

    用于需要「当前操作人」身份的接口（如上下架记录的操作人），由 AuthMiddleware
    在受保护请求上注入 ``request.state.user``。
    """

    payload = getattr(request.state, "user", None)
    if not payload:
        raise HTTPException(status_code=401, detail="未认证")
    return payload


def require_permission(permission: str):
    """依赖工厂：当前用户须具备 ``permission``，否则 403。

    普通用户的权限在每次请求实时从数据库解析，因此权限变更立即生效。
    """

    async def _dep(request: Request, session: AsyncSession = Depends(get_db)) -> dict:
        eff = await _resolve_effective(request, session)
        if permission not in eff:
            raise AppError(status_code=403, code=403, message=f"权限不足：需要「{permission}」权限")
        return request.state.user

    return _dep


def require_any_permission(permissions: Iterable[str]):
    """依赖工厂：具备其中任一权限即可，否则 403。"""

    required = set(permissions)

    async def _dep(request: Request, session: AsyncSession = Depends(get_db)) -> dict:
        eff = await _resolve_effective(request, session)
        if not (required & eff):
            needed = "、".join(sorted(required))
            raise AppError(status_code=403, code=403, message=f"权限不足：需要以下任一权限：{needed}")
        return request.state.user

    return _dep
