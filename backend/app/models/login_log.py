"""登录日志模型（与操作日志分离，独立二级菜单展示）。

在认证端点写入：登录成功 / 登录失败 / 注销。
登录失败时无法确认账号身份，user_id 为空、仅记录尝试的用户名。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow


class LoginLog(Base):
    """登录 / 注销日志实体。"""

    __tablename__ = "login_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 账号 ID（登录失败时为 None）。
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 动作：login / logout。
    action: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # 结果：success / failed（注销恒为 success）。
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
