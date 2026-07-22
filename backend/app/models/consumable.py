"""耗材管理模型（4 张表）。

数据层级：耗材类型（ConsumableType，用户自定义，如网线/光纤/光模块）
→ 分类（ConsumableCategory，某种类型下的细分，如「六类线」「LC-LC 跳线」）
→ 具体耗材（ConsumableItem，带当前剩余数量 current_quantity）
→ 库存变动记录（ConsumableRecord，每次入库/领用/报废/盘点都会落一条，用于追溯）。

设计要点：
- 类型 / 分类 / 耗材均可被用户自由新增（无枚举限制），满足「用户自定义耗材类型」。
- ConsumableItem.current_quantity 为实时结存，所有变动均通过 ``adjust_stock`` 事务维护，
  并同步写入 ConsumableRecord（append-only，不可篡改，保证库存变动历史可完整追溯）。
- operation_type 以 ``String`` 存枚举值（与项目其余枚举一致，不映射到原生 ENUM）。
- operator 由后端从当前登录用户（JWT payload）注入，记录「谁操作的」。

删除语义（避免孤史/误删）：
- 删除类型：仅当该类型下无任何分类与耗材时允许。
- 删除分类：仅当该分类下无任何耗材时允许。
- 删除耗材：级联删除其库存变动记录（耗材实体已不存在，历史一并清理）。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from app.models.consumable import (
        ConsumableCategory,
        ConsumableItem,
        ConsumableRecord,
    )


class ConsumableType(Base):
    """耗材类型（用户自定义，如网线 / 光纤 / 光模块）。"""

    __tablename__ = "consumable_types"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    categories: Mapped[list["ConsumableCategory"]] = relationship(
        back_populates="type",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ConsumableCategory(Base):
    """耗材分类（隶属某个类型，如「网线」下的「六类线」「超五类线」）。"""

    __tablename__ = "consumable_categories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("consumable_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    # lazy="selectin"：分类被查询时即把所属类型一并加载，避免在异步会话中
    # 访问 obj.type 触发惰性加载（懒加载在非 await 上下文会抛 MissingGreenlet → 500）。
    type: Mapped["ConsumableType"] = relationship(back_populates="categories", lazy="selectin")
    items: Mapped[list["ConsumableItem"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ConsumableItem(Base):
    """具体耗材（隶属类型 + 分类，记录当前剩余数量）。"""

    __tablename__ = "consumable_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("consumable_types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("consumable_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 规格 / 型号（如 Cat6、10G-SR、LC-LC），选填。
    spec: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 计量单位（如 根 / 个 / 箱 / 米），选填，默认「个」。
    unit: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, default="个")
    # 当前剩余数量（实时结存）。
    current_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    type: Mapped["ConsumableType"] = relationship(lazy="selectin")
    category: Mapped["ConsumableCategory"] = relationship(lazy="selectin")
    records: Mapped[list["ConsumableRecord"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ConsumableRecord.operation_time.desc()",
    )


class ConsumableRecord(Base):
    """库存变动记录（append-only，每次入库/领用/报废/盘点落一条，用于追溯）。"""

    __tablename__ = "consumable_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("consumable_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 操作时间（业务时间，默认入库/领用/盘点发生的此刻）。
    operation_time: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    # 操作类型：入库 / 领用 / 报废 / 盘点（见 ConsumableOpType）。
    operation_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # 数量（正整数字面量）：领用/报废为消耗数量；盘点为盘点后的实际结存。
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # 操作原因 / 备注（选填）。
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 操作人（后端注入当前登录用户，不依赖前端传入）。
    operator: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # 本笔操作后的结存（冗余存储，便于历史直接展示，无需回算）。
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped["ConsumableItem"] = relationship(lazy="selectin")
