"""设备互联链路模型 (IDC_DeviceLink)。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from app.models.interface import DeviceInterface


class DeviceLink(Base):
    """设备互联链路。``source_interface_id`` 与 ``target_interface_id`` 均设唯一约束，

    保证「一接口仅属于一条 active 链路」。
    """

    __tablename__ = "device_links"
    __table_args__ = (
        UniqueConstraint("source_interface_id", name="uq_link_source_interface"),
        UniqueConstraint("target_interface_id", name="uq_link_target_interface"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 源接口（唯一）。左侧 / 本端。
    source_interface_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("device_interfaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # 目标接口（唯一）。右侧 / 对端。半链路（对端不在本系统）时留空，
    # 改用 ``target_external`` 自由文本记录对端位置（如「运营商 ODF-3」）。
    target_interface_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("device_interfaces.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
    # 对端外部位置（半链路）：自由文本。与 target_interface_id 二选一。
    target_external: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    # 备注（自由文本，替代原「链路类型」字段）。
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 连接介质（细分）：smf / mmf / tp（历史 copper/fiber 由迁移脚本转换）。
    medium: Mapped[str] = mapped_column(String(16), nullable=False, default="tp")
    # 连接器类型（链路两端接头，按介质联动，可空）：光纤 lc-lc/lc-fc/sc-sc/sc-fc/st-st；
    # 双绞线 cat5e/cat6/cat6a；其他 other。
    connector_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    # 线缆长度（如 "5m" / "10m"），自由文本。
    cable_length: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    source_interface: Mapped["DeviceInterface"] = relationship(
        "DeviceInterface",
        back_populates="link_as_source",
        foreign_keys=[source_interface_id],
    )
    target_interface: Mapped[Optional["DeviceInterface"]] = relationship(
        "DeviceInterface",
        back_populates="link_as_target",
        foreign_keys=[target_interface_id],
    )
