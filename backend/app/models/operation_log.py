"""操作日志模型（请求级，原生）。

由 HTTP 中间件自动记录所有写请求（POST/PUT/PATCH/DELETE）：
谁 / 何时 / 方法 / 路径 / 状态码 / 来源 IP。零业务侵入，任何新模块天然覆盖。
读请求（GET）不记录。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow


class OperationLog(Base):
    """请求级操作日志实体。"""

    __tablename__ = "operation_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 操作人（来自 JWT payload；理论上写请求必已登录）。
    operator_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    operator_name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # HTTP 方法：POST/PUT/PATCH/DELETE。
    method: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    # 请求路径（不含查询串），如 /api/v1/devices/xxx。
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    # 资源类型（归一化键）：room/rack/device/interface/link/account/consumable/mount-record。
    # 由中间件按「资源关键字优先」从路径解析后落库，支撑按资源类型精确筛选
    # （嵌套路径如 /devices/{id}/interfaces 也能正确归为 interface，而非误判 device）。
    resource: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    # 操作动作（归一化键）：create(新增) / update(更新) / delete(删除)。
    # POST→create，PUT/PATCH→update，DELETE→delete；落库后前端「操作」列仅展示
    # 新增 / 更新 / 删除三态，不再区分 PUT/PATCH 等方法（用户诉求：操作只看三大类）。
    action: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    # 操作对象可读名称（设备名 / 机柜名 / 机房名 / 链路两端等），让日志一眼看清
    # 操作了哪个具体实体，无需钻进详情（用户诉求：新增「操作对象」列）。
    target: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # 响应状态码（2xx 成功 / 4xx 拒绝 / 5xx 异常均记录，便于追溯失败操作）。
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 操作详情（JSON 文本）：请求体 data + 外键解析出的可读名称 names。
    # 用于审计「改了什么 / 上架到哪 / 链路两端 / 新增了什么耗材」等具体信息。
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
