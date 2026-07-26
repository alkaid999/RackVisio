"""操作审计日志 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    """审计日志对外结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    module: str
    action: str
    object_type: str | None = None
    object_id: str | None = None
    object_name: str | None = None
    operator_id: str | None = None
    operator_name: str | None = None
    detail: str | None = None
    ip: str | None = None
    created_at: datetime | None = None
