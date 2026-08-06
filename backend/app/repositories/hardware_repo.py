"""硬件管理仓储（纯 DB 读写，按层级分 4 个类）。

层级：HardwareType → HardwareCategory → HardwareItem（独立个体）→ HardwareRecord。
Out 对象的冗余展示字段（counts / type_name / category_name / device_name）由 service 层填充，
repo 仅负责查询与聚合计数。
"""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.hardware import (
    HardwareCategory,
    HardwareItem,
    HardwareRecord,
    HardwareType,
)
from app.schemas.hardware import (
    HardwareCategoryCreate,
    HardwareCategoryUpdate,
    HardwareItemCreate,
    HardwareItemUpdate,
    HardwareTypeCreate,
    HardwareTypeUpdate,
)


# ============ 类型 ============
class HardwareTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: HardwareTypeCreate) -> HardwareType:
        obj = HardwareType(**data.model_dump())
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get(self, type_id: str) -> Optional[HardwareType]:
        return (
            await self.session.execute(
                select(HardwareType).where(HardwareType.id == type_id)
            )
        ).scalar_one_or_none()

    async def list(self) -> list[HardwareType]:
        return list(
            (
                await self.session.execute(
                    # 手动排序优先（sort_order 升序）；历史数据全 0 时回退 created_at 倒序。
                select(HardwareType).order_by(
                    HardwareType.sort_order.asc(), HardwareType.created_at.desc()
                )
                )
            ).scalars().all()
        )

    async def update(self, obj: HardwareType, data: HardwareTypeUpdate) -> HardwareType:
        # R-03：exclude_unset 已区分「未提供」与「显式设 None」，必须无条件 setattr，
        # 否则清空可选字段（description 等）无法持久化。
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: HardwareType) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def reorder(self, ids: list[str]) -> None:
        """按传入顺序批量更新 sort_order（0..N，越小越靠前）——手动排序持久化。"""
        for i, tid in enumerate(ids):
            await self.session.execute(
                HardwareType.__table__.update()
                .where(HardwareType.id == tid)
                .values(sort_order=i)
            )
        await self.session.flush()

    async def count_categories(self, type_id: str) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(HardwareCategory)
                .where(HardwareCategory.type_id == type_id)
            )
        ).scalar() or 0

    async def count_items(self, type_id: str) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(HardwareItem)
                .where(HardwareItem.type_id == type_id)
            )
        ).scalar() or 0

    async def count_categories_by_types(self, type_ids: list[str]) -> dict[str, int]:
        """按类型批量统计分类数（一次 GROUP BY 取代逐类型 N+1）。"""
        if not type_ids:
            return {}
        rows = (
            await self.session.execute(
                select(HardwareCategory.type_id, func.count())
                .where(HardwareCategory.type_id.in_(type_ids))
                .group_by(HardwareCategory.type_id)
            )
        ).all()
        return {t: c for t, c in rows}

    async def count_items_by_types(self, type_ids: list[str]) -> dict[str, int]:
        """按类型批量统计硬件数。"""
        if not type_ids:
            return {}
        rows = (
            await self.session.execute(
                select(HardwareItem.type_id, func.count())
                .where(HardwareItem.type_id.in_(type_ids))
                .group_by(HardwareItem.type_id)
            )
        ).all()
        return {t: c for t, c in rows}


# ============ 分类 ============
class HardwareCategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, type_id: str, data: HardwareCategoryCreate) -> HardwareCategory:
        obj = HardwareCategory(type_id=type_id, **data.model_dump())
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get(self, category_id: str) -> Optional[HardwareCategory]:
        return (
            await self.session.execute(
                select(HardwareCategory).where(HardwareCategory.id == category_id)
            )
        ).scalar_one_or_none()

    async def list_by_type(self, type_id: str) -> list[HardwareCategory]:
        return list(
            (
                await self.session.execute(
                # 手动排序优先（sort_order 升序）；历史数据全 0 时回退 created_at 倒序。
                select(HardwareCategory)
                .where(HardwareCategory.type_id == type_id)
                .order_by(HardwareCategory.sort_order.asc(), HardwareCategory.created_at.desc())
                )
            ).scalars().all()
        )

    async def update(
        self, obj: HardwareCategory, data: HardwareCategoryUpdate
    ) -> HardwareCategory:
        # R-03：无条件 setattr（exclude_unset 已区分未提供 vs 显式 None）。
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: HardwareCategory) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def reorder(self, ids: list[str]) -> None:
        """按传入顺序批量更新 sort_order（同类型内）——手动排序持久化。"""
        for i, cid in enumerate(ids):
            await self.session.execute(
                HardwareCategory.__table__.update()
                .where(HardwareCategory.id == cid)
                .values(sort_order=i)
            )
        await self.session.flush()

    async def count_items(self, category_id: str) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(HardwareItem)
                .where(HardwareItem.category_id == category_id)
            )
        ).scalar() or 0

    async def count_items_by_categories(self, category_ids: list[str]) -> dict[str, int]:
        """按分类批量统计硬件数。"""
        if not category_ids:
            return {}
        rows = (
            await self.session.execute(
                select(HardwareItem.category_id, func.count())
                .where(HardwareItem.category_id.in_(category_ids))
                .group_by(HardwareItem.category_id)
            )
        ).all()
        return {c: n for c, n in rows}


# ============ 硬件（独立个体）============
class HardwareItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: HardwareItemCreate) -> HardwareItem:
        obj = HardwareItem(**data.model_dump())
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get(self, item_id: str) -> Optional[HardwareItem]:
        return (
            await self.session.execute(
                select(HardwareItem).where(HardwareItem.id == item_id)
            )
        ).scalar_one_or_none()

    async def sn_exists(self, sn: str, exclude_id: Optional[str] = None) -> bool:
        """SN 号是否已被占用（独立编号唯一性；exclude_id 用于更新时排除自身）。"""
        stmt = select(func.count()).select_from(HardwareItem).where(HardwareItem.sn == sn)
        if exclude_id:
            stmt = stmt.where(HardwareItem.id != exclude_id)
        return (await self.session.execute(stmt)).scalar() or 0 > 0

    async def list_by_device(self, device_id: str) -> list[HardwareItem]:
        """某设备已安装的硬件（一对一：assigned_device_id = 该设备）。"""
        return list(
            (
                await self.session.execute(
                    select(HardwareItem)
                    .where(HardwareItem.assigned_device_id == device_id)
                    .order_by(HardwareItem.assigned_at.desc(), HardwareItem.created_at.desc())
                )
            ).scalars().all()
        )

    async def list(
        self,
        *,
        page: int = 1,
        size: int = 20,
        type_id: Optional[str] = None,
        category_id: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[list[HardwareItem], int]:
        conditions = []
        if type_id:
            conditions.append(HardwareItem.type_id == type_id)
        if category_id:
            conditions.append(HardwareItem.category_id == category_id)
        if status:
            conditions.append(HardwareItem.status == status)
        if keyword:
            kw = f"%{keyword}%"
            # 关键字覆盖 名称/品牌/SN号/规格/备注。
            conditions.append(
                or_(
                    HardwareItem.name.ilike(kw),
                    HardwareItem.brand.ilike(kw),
                    HardwareItem.sn.ilike(kw),
                    HardwareItem.spec.ilike(kw),
                    HardwareItem.remark.ilike(kw),
                )
            )
        stmt = select(HardwareItem)
        count_stmt = select(func.count()).select_from(HardwareItem)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = (
            stmt.order_by(HardwareItem.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def update(self, obj: HardwareItem, data: HardwareItemUpdate) -> HardwareItem:
        # R-03：无条件 setattr（exclude_unset 已区分未提供 vs 显式 None）。
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: HardwareItem) -> None:
        await self.session.delete(obj)
        await self.session.flush()


# ============ 硬件变动记录 ============
class HardwareRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **kwargs) -> HardwareRecord:
        obj = HardwareRecord(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def list_by_item(
        self, item_id: str, page: int = 1, size: int = 50
    ) -> Tuple[list[HardwareRecord], int]:
        conditions = [HardwareRecord.item_id == item_id]
        stmt = select(HardwareRecord)
        count_stmt = select(func.count()).select_from(HardwareRecord)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = (
            stmt.order_by(HardwareRecord.operation_time.desc(), HardwareRecord.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def list_all(
        self,
        *,
        page: int = 1,
        size: int = 20,
        type_id: Optional[str] = None,
        category_id: Optional[str] = None,
        item_id: Optional[str] = None,
        operation_type: Optional[str] = None,
    ) -> Tuple[list[HardwareRecord], int]:
        conditions = []
        if item_id:
            conditions.append(HardwareRecord.item_id == item_id)
        if operation_type:
            conditions.append(HardwareRecord.operation_type == operation_type)
        # type_id / category_id 作用于关联硬件，需 join。
        stmt = select(HardwareRecord)
        count_stmt = select(func.count()).select_from(HardwareRecord)
        if type_id or category_id:
            stmt = stmt.join(HardwareRecord.item)
            count_stmt = count_stmt.join(HardwareRecord.item)
            if type_id:
                conditions.append(HardwareItem.type_id == type_id)
            if category_id:
                conditions.append(HardwareItem.category_id == category_id)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = (
            stmt.order_by(HardwareRecord.operation_time.desc(), HardwareRecord.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total
