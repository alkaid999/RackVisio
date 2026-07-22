"""账号管理相关 Schema。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["admin", "user"]


class AccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = Field(default=None, max_length=64)
    role: Role = "user"
    # 普通用户的细粒度权限映射（管理员忽略此字段）。
    # 形如 {"room": {"view": True, "edit": False}, ...}。
    permissions: dict | None = None


class AccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    role: Role | None = None
    disabled: bool | None = None
    # 可选改密：仅填写时更新。
    password: str | None = Field(default=None, min_length=6, max_length=128)
    # 普通用户的细粒度权限映射（管理员忽略此字段）。
    permissions: dict | None = None


class AccountOut(BaseModel):
    id: str
    username: str
    display_name: str | None
    role: str
    role_label: str
    permissions: dict
    disabled: bool
    created_at: str
