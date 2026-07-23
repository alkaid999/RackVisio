"""设备模型 (IDC_Device)。

仅存储设备**固有属性**，不存储任何位置关联字段（机房/机柜/起始 U 位）。
设备当前位置由 ``mount_records`` 表中状态为「有效」的最新记录推导得出。

字段说明：
- ``device_code``：设备编号（全局唯一），为空时由服务层自动生成。
- ``u_height``：设备 U 数（物理高度），决定上架时占用 U 位数量，必有且 ≥ 1。
- ``warranty_expire`` / ``remark``：维保到期日 / 备注。
- ``status``：资产状态（在库/已上架/已下架/待报废），默认「在库」。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow
from app.core.enums import DeviceStatus, DevicePowerStatus

if TYPE_CHECKING:  # pragma: no cover
    from app.models.interface import DeviceInterface
    from app.models.mount_record import MountRecord


class Device(Base):
    """设备实体（仅固有属性）。"""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 设备编号（全局唯一）。前端可录入，留空时由服务层生成 DEV-XXXXXXXX。
    device_code: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    # 设备名称（运维人员日常称呼）。
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 设备类型（server/switch/router/security/other）。
    device_type: Mapped[str] = mapped_column(String(16), nullable=False, default="server")
    # 设备 U 数（物理高度，决定上架占用 U 位；必有且 ≥ 1）。
    u_height: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 设备型号（厂商型号）。
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 序列号（SN，厂商出厂序列号）。
    sn: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    # IP 地址（可选，仅登记用）。
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # 维保到期日。
    warranty_expire: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # 备注。
    remark: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # 资产状态：在库 / 已上架 / 已下架 / 待报废，默认「在库」。
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DeviceStatus.IN_STOCK.value
    )
    # 开关机状态（仅对「在架」设备有意义）：开机 / 关机，默认「开机」。
    # 在库设备未通电，不记录此状态；2D 机柜视图据此以红 / 非红底色区分运行与停机。
    power_status: Mapped[str] = mapped_column(
        String(8), nullable=False, default=DevicePowerStatus.ON.value
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    interfaces: Mapped[list["DeviceInterface"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # 上架记录（一对多：同一设备可能多次上下架，历史记录保留）。
    mount_records: Mapped[list["MountRecord"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
