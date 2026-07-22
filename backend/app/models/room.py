"""机房模型 (IDC_Room)。

面向政企单位自建机房 / IDC 租用场景：以「机房编号」作为全局唯一标识，
记录别名、所属区域 / 楼宇 / 楼层 / 详细地址等分组与物理位置信息。
已移除原「机房等级(T1/T2/T3)」与「网格行列(rows/cols)」概念（平面图功能随之移除）。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from app.models.rack import Rack


class Room(Base):
    """机房实体。"""

    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 机房编号：全局唯一，仅允许数字+英文符号（如 DC-01），必填。
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # 机房名称：清晰标识，可重复，必填。
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 机房别名：内部简称（如核心机房A），选填。
    alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 所属区域：用于分组管理（如华南），选填。
    area: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # 所属楼宇：物理位置标识（如 T2），选填。
    building: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 所在楼层：物理位置（如 5F），选填。
    floor: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 机房地址：详细街道地址（如某市某区某路某号），选填。
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # active / disabled（软删除）
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    racks: Mapped[list["Rack"]] = relationship(
        back_populates="room",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
