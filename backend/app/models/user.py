"""用户账号模型（鉴权与 RBAC）。

- 密码不以明文存储：``password_hash`` 为 pbkdf2_hmac 派生值，``salt`` 为每用户随机盐
  （见 ``app/core/security.py``），数据库落入也无泄露风险。
- 角色（role）仅两档：``admin``（管理员，恒为全权限含账号管理）/ ``user``（普通用户，
  权限由 ``permissions`` 映射逐用户独立配置，缺省全模块只读）。权限解析见
  ``app/core/rbac.py``：管理员无需存储映射（``permissions`` 为 NULL），普通用户实时
  从 ``permissions`` 展开，兼顾「逐用户细粒度」与「管理员零漂移」。
- ``disabled`` 为软禁用开关，禁用后 token 校验直接拒绝。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CHAR, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow


class User(Base):
    """平台账号。"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # 密码派生值（pbkdf2_hmac sha256，hex）。
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    # 每用户随机盐（hex）。
    salt: Mapped[str] = mapped_column(String(64), nullable=False)
    # 角色：admin / user。
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    # 细粒度权限映射（仅普通用户使用）：{"module": {"view": bool, "edit": bool}}。
    # 管理员恒为全权限，此字段为 NULL 以节省存储并避免漂移。
    permissions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 展示名（可选，用于界面显示）。
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 软禁用：禁用后无法登录且已有 token 校验失败。
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 强制改密标记（S-02）：初始管理员首次登录后必须修改密码才能正常使用。
    # seed 创建初始管理员时置 True；登录/改密接口据此驱动前端强制跳转改密页，
    # 改密成功后清除。存量用户回填 False（见 0012 迁移），不受影响。
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # 创建时间（R-01：对齐 login_logs/operation_logs 的 DateTime 类型，naive UTC）。
    # 历史库由 0013 迁移统一：PostgreSQL ALTER TYPE 转换存量文本；SQLite 的
    # DATETIME 列本就以 ISO 文本存储，SQLAlchemy 可直接解析，无需 DDL。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
