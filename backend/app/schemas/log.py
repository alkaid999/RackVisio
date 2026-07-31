"""操作日志 / 登录日志出参模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OperationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    operator_id: str | None
    operator_name: str | None
    method: str
    path: str
    # 资源类型（归一化键）：room/rack/device/interface/link/account/consumable/mount-record。
    # 前端据此做「按资源类型筛选」。
    resource: str | None = None
    # 操作动作归一化键：create(新增) / update(更新) / delete(删除)；前端「操作」列据此
    # 仅展示三大类。method 仍保留（原始 HTTP 方法），便于排查。
    action: str | None = None
    # 操作对象可读名称（设备名 / 机柜名 / 链路两端等），对应「操作对象」列。
    target: str | None = None
    status_code: int
    ip: str | None
    # 操作详情：{ data: 请求体, names: 外键解析出的可读名称 }。
    detail: Optional[dict] = None
    created_at: datetime


class LoginLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None
    username: str
    action: str
    status: str
    ip: str | None
    created_at: datetime


class LogCleanupIn(BaseModel):
    """手动触发日志清理的可选入参。

    - ``days``：保留天数覆盖；省略时回退到配置 ``LOG_RETENTION_DAYS``。
    - 仅接受 ``days >= 1``，避免误传 0 / 负数把全量日志清空。
    """

    days: int | None = Field(default=None, ge=1, description="保留天数覆盖；省略则用 LOG_RETENTION_DAYS")
