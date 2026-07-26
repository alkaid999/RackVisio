"""操作审计日志模型。

记录「谁在什么时间对什么对象做了什么操作」，覆盖增删改与导入 / 导出，
供多人协作场景下追溯变更（谁改了什么）。审计记录不可软删除。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow


class AuditLog(Base):
    """操作审计日志实体。"""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 业务模块：room/rack/device/account/link/consumable/import/export/system
    module: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 操作类型：create/update/delete/restore/purge/import/export/login/...
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 业务对象类型（中文，便于前端展示）：机房/机柜/设备/账号/...
    object_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # 对象名称 / 标识（如机房名、设备编号），便于审计阅读。
    object_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 操作人（来自 JWT payload；未登录场景为 None）。
    operator_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    operator_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 操作摘要（人类可读中文），如「导入 12 条，成功 10 失败 2」。
    detail: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
