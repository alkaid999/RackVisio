"""机柜模型 (IDC_Rack)。

面向政企 / IDC 租用场景的机柜资产：以「列编号 + 机柜编号」定位机柜。
- 列编号(column_code)：同一机房内唯一（如 A1、B2）。
- 机柜编号(code)：同一列内唯一（如 01、02）。
- 机柜分组(rack_group)：所属用户 / 公司 / 部门（如某项目组），选填。
- 机柜状态(status)：业务枚举（可用/已占用/维护中/已下架/空调/电源），选填，用户维护。
- used_u 由后端按上架设备重算，status 不随容量自动变化（业务状态人工维护）。

已移除原「行列坐标(row_num/col_num)」与平面图耦合。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from app.models.device import Device
    from app.models.room import Room


class Rack(Base):
    """机柜实体。"""

    __tablename__ = "racks"
    __table_args__ = (
        # 机柜编号在同一列内唯一：列内可有多台机柜（如 01、02），
        # 故唯一键为 (机房, 列编号, 机柜编号)。列编号本身作为分组标签，
        # 不强制机房内唯一（一个列自然包含多台机柜）。
        UniqueConstraint("room_id", "column_code", "code", name="uq_rack_room_column_code"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    room_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 机柜名称（如 A1-01 机柜），必填。
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 机柜编号：同一列内唯一（如 01、02），必填。
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 列编号：同一机房内唯一（如 A1、B2），必填。
    column_code: Mapped[str] = mapped_column(String(32), nullable=False, default="A")
    # 机柜 U 数：可用 U 位高度（如 42），必填。
    total_u: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    # 已用 U 位（后端按上架设备重算）。
    used_u: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 机柜分组：所属用户 / 公司 / 部门（如某项目组），选填。
    rack_group: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 机柜状态：业务枚举，选填，默认「可用」。
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="可用")
    # 平面图网格坐标（2D 平面图 + 3D 联动）。同一机房内每台机柜占据一格，
    # grid_row=行(自上而下)、grid_col=列(自左向右)，缺省时由后端按列编号/编号自动分配。
    grid_row: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None, index=True
    )
    grid_col: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    room: Mapped["Room"] = relationship(back_populates="racks")
