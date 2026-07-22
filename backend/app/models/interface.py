"""设备接口模型 (IDC_DeviceInterface)。

接口即设备前面板上的物理端口（电口 / 光口 / 管理口）。与旧「端口」命名统一为「接口」：
表名 ``device_interfaces``、序号列 ``interface_no``。

接口状态（up / down）**仅由链路事务维护**，运维不可手动切换：
- 新增接口默认 ``down``（未接线）；
- 建链（DeviceLink 创建）在同一事务里把本端 + 对端接口置为 ``up``；
- 删链则两端一起回落 ``down``。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from app.models.device import Device
    from app.models.link import DeviceLink


class DeviceInterface(Base):
    """设备接口。同一设备内 ``name`` 与 ``(device_id, interface_no)`` 均唯一。"""

    __tablename__ = "device_interfaces"
    __table_args__ = (
        UniqueConstraint("device_id", "interface_no", name="uq_device_interface_no"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    device_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 前面板序号（1 基，设备内唯一），用于排序与面板定位；自由递增，无固定模板。
    interface_no: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, index=True
    )
    # electrical / optical
    interface_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="electrical"
    )
    # data（数据口，默认）/ mgmt（管理口）
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="data")
    # 1G / 10G / 40G / 100G
    speed: Mapped[str] = mapped_column(String(8), nullable=False, default="1G")
    # up / down（仅由建链 / 删链事务维护，运维不可手动切换）
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="down")
    # 端口级 IP 地址（区别于 devices.ip_address 设备级地址）；可空，运维可手填。
    # 注意：此字段与已删除的 IPAM（IP 地址分配管理）无关，仅作接口自有属性。
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    device: Mapped["Device"] = relationship(back_populates="interfaces")
    # 接口作为链路源端（source_interface_id 唯一约束）。
    link_as_source: Mapped[Optional["DeviceLink"]] = relationship(
        "DeviceLink",
        back_populates="source_interface",
        foreign_keys="DeviceLink.source_interface_id",
        uselist=False,
        cascade="all, delete-orphan",
    )
    # 接口作为链路目标端（target_interface_id 唯一约束；半链路时为 NULL）。
    link_as_target: Mapped[Optional["DeviceLink"]] = relationship(
        "DeviceLink",
        back_populates="target_interface",
        foreign_keys="DeviceLink.target_interface_id",
        uselist=False,
        cascade="all, delete-orphan",
    )
