"""上架记录模型 (IDC_MountRecord)。

管理设备与机柜的位置关联，是「设备 ↔ 机柜」的唯一关联表。

设计要点（架构文档 §设备与上架记录解耦）：
- 设备表 (devices) 不存储任何位置字段（不含机房/机柜/起始 U 位）；
  设备当前位置 = 查询本表中 ``record_status='有效'`` 的最新一条记录得到。
- 起始 U 位 (start_u) 在上架时指定，记录在此表；
  占用 U 数 (occupied_u) 在写入时从设备表的 ``u_height`` 带出（设备固有属性）。
- 下架时仅把当前有效记录置为 ``已下架`` 并填写下架信息，设备表 status 同步为
  ``已下架``；设备可被再次上架，产生新的有效记录（历史记录保留用于追溯）。
- 本表主键采用整数自增（与设备 UUID 主键解耦，本表无外键依赖，便于审计追溯）。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from app.models.device import Device


class MountRecord(Base):
    """上架记录实体。"""

    __tablename__ = "mount_records"

    device: Mapped["Device"] = relationship(back_populates="mount_records")

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 关联设备（UUID 主键，保持与设备表一致）。
    device_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 关联机房（冗余存储，便于按机房统计上架设备，无需多表 JOIN）。
    room_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 关联机柜。
    rack_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("racks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 起始 U 位（从第几 U 开始放置，1 基，自底向上）。
    start_u: Mapped[int] = mapped_column(Integer, nullable=False)
    # 占用 U 数（上架时从设备 u_height 带出，此后不变，即使设备型号变更也保留当时记录）。
    occupied_u: Mapped[int] = mapped_column(Integer, nullable=False)
    # 上架时间，默认当前时间。
    mounted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # 上架人（操作人，选填）。
    mounted_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # 下架时间（下架时填写）。
    unmounted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 下架人（选填）。
    unmounted_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # 记录状态：有效 / 已下架。
    record_status: Mapped[str] = mapped_column(String(16), nullable=False, default="有效")
