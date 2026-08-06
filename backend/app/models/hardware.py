"""硬件管理模型（4 张表）。

数据层级：硬件类型（HardwareType，用户自定义，如主板/CPU/内存/硬盘/阵列卡/网卡/电源）
→ 分类（HardwareCategory，某种类型下的细分，如内存下的「DDR4 ECC」「DDR5」）
→ 具体硬件（HardwareItem，**独立个体台账**：每件硬件一行记录，含唯一 SN/编号）
→ 硬件变动记录（HardwareRecord，每次新增/报废/分配/回收落一条，用于追溯）。

核心设计（与耗材的差异，需求#4 补充说明）：
- 耗材成本低，按「批量数量」记录（current_quantity）；
- **硬件每件都是独立管理单元**：一行 HardwareItem = 一件实物，通过 SN/编号单独追踪，
  没有批量库存字段。设备添加硬件 = 从硬件管理选「某一件」具体硬件（与机柜上架
  从设备列表选择同理），而不是选条目+数量。

状态与设备关联（一对一）：
- HardwareItem.status：在库（in_stock）↔ 已安装（installed）。
- ``assigned_device_id``：非空即表示该硬件当前安装于某台设备（一对一，一硬件至多一台设备）；
  为空则「在库」可分配。
- 设备添加硬件：status→已安装、写 assigned_device_id，落「分配」记录。
- 设备删除硬件：清空 assigned_device_id、status→在库，落「回收」记录（硬件回库，记录不删）。

字段说明（需求#3）：
- ``brand``：品牌（如 Intel / H3C / 希捷）。
- ``sn``：SN 号 / 独立编号（需求#4：每个硬件都有独立编号，唯一索引，可空但建议填写）。

删除语义（避免孤史/误删）：
- 删除类型：仅当该类型下无任何分类与硬件时允许。
- 删除分类：仅当该分类下无任何硬件时允许。
- 删除硬件：仅当该硬件「在库」（未被设备占用）时允许；已安装须先回收。删除即报废出库，
  级联删除其变动记录。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from app.models.hardware import (
        HardwareCategory,
        HardwareItem,
        HardwareRecord,
    )


class HardwareType(Base):
    """硬件类型（用户自定义，如主板 / CPU / 内存 / 硬盘 / 阵列卡 / 网卡 / 电源）。"""

    __tablename__ = "hardware_types"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 手动排序：类型管理页上移/下移持久化（越小越靠前，新建追加到末尾）。
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    categories: Mapped[list["HardwareCategory"]] = relationship(
        back_populates="type",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class HardwareCategory(Base):
    """硬件分类（隶属某个类型，如「内存」下的「DDR4 ECC」「DDR5」）。"""

    __tablename__ = "hardware_categories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hardware_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 手动排序（同类型内上移/下移持久化，越小越靠前）。
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    # lazy="selectin"：分类被查询时即把所属类型一并加载，避免在异步会话中
    # 访问 obj.type 触发惰性加载（懒加载在非 await 上下文会抛 MissingGreenlet → 500）。
    type: Mapped["HardwareType"] = relationship(back_populates="categories", lazy="selectin")
    items: Mapped[list["HardwareItem"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class HardwareItem(Base):
    """具体硬件（**独立个体台账**：一行 = 一件实物，SN 唯一，状态追踪在库/已安装）。"""

    __tablename__ = "hardware_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hardware_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hardware_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 品牌（需求#3：如 Intel / H3C / 希捷）。
    brand: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # SN 号 / 独立编号（需求#3/#4：每个硬件独立编号，唯一索引，可空但建议填写）。
    sn: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    # 规格 / 型号（如 32GB DDR4-3200 ECC、2.4T SAS 10K）。
    spec: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 在位状态：在库 / 已安装（见 HardwareStatus）。
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="在库", index=True)
    # 一对一设备关联：非空 = 已安装于该设备；空 = 在库可分配。
    assigned_device_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # 安装到设备的时间（分配时写入，回收时置空）。
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    type: Mapped["HardwareType"] = relationship(lazy="selectin")
    category: Mapped["HardwareCategory"] = relationship(lazy="selectin")
    records: Mapped[list["HardwareRecord"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="HardwareRecord.operation_time.desc()",
    )


class HardwareRecord(Base):
    """硬件变动记录（append-only：新增/报废/分配/回收各落一条，用于追溯每件硬件的生命周期）。"""

    __tablename__ = "hardware_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hardware_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 操作时间（业务时间，默认变动发生的此刻）。
    operation_time: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    # 操作类型：新增 / 报废 / 分配 / 回收（见 HardwareOpType）。
    operation_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # 关联设备（分配/回收时记录目标设备名，便于追溯「装到哪台/从哪台回收」；新增/报废为空）。
    device_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 操作原因 / 备注（选填）。
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 操作人（后端注入当前登录用户，不依赖前端传入）。
    operator: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped["HardwareItem"] = relationship(lazy="selectin")
