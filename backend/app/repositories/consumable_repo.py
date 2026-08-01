"""耗材管理仓储（纯 DB 读写，按层级分 4 个类）。

层级：ConsumableType → ConsumableCategory → ConsumableItem → ConsumableRecord。
Out 对象的冗余展示字段（counts / type_name / category_name）由 service 层填充，
repo 仅负责查询与聚合计数。
"""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consumable import (
    ConsumableCategory,
    ConsumableItem,
    ConsumableRecord,
    ConsumableType,
)
from app.schemas.consumable import (
    ConsumableCategoryCreate,
    ConsumableCategoryUpdate,
    ConsumableItemCreate,
    ConsumableItemUpdate,
    ConsumableTypeCreate,
    ConsumableTypeUpdate,
)


# ============ 类型 ============
class ConsumableTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: ConsumableTypeCreate) -> ConsumableType:
        obj = ConsumableType(**data.model_dump())
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get(self, type_id: str) -> Optional[ConsumableType]:
        return (
            await self.session.execute(
                select(ConsumableType).where(ConsumableType.id == type_id)
            )
        ).scalar_one_or_none()

    async def list(self) -> list[ConsumableType]:
        return list(
            (
                await self.session.execute(
                    # 按创建时间倒序：新增的类型置顶（需求#3「新增的就在最上」）。
                select(ConsumableType).order_by(ConsumableType.created_at.desc())
                )
            ).scalars().all()
        )

    async def update(self, obj: ConsumableType, data: ConsumableTypeUpdate) -> ConsumableType:
        # R-03：exclude_unset 已区分「未提供」与「显式设 None」，必须无条件 setattr，
        # 否则清空可选字段（description 等）无法持久化。
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: ConsumableType) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def count_categories(self, type_id: str) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(ConsumableCategory)
                .where(ConsumableCategory.type_id == type_id)
            )
        ).scalar() or 0

    async def count_items(self, type_id: str) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(ConsumableItem)
                .where(ConsumableItem.type_id == type_id)
            )
        ).scalar() or 0

    async def count_categories_by_types(self, type_ids: list[str]) -> dict[str, int]:
        """按类型批量统计分类数（P-05：一次 GROUP BY 取代逐类型 N+1）。"""
        if not type_ids:
            return {}
        rows = (
            await self.session.execute(
                select(ConsumableCategory.type_id, func.count())
                .where(ConsumableCategory.type_id.in_(type_ids))
                .group_by(ConsumableCategory.type_id)
            )
        ).all()
        return {t: c for t, c in rows}

    async def count_items_by_types(self, type_ids: list[str]) -> dict[str, int]:
        """按类型批量统计耗材条目数（P-05）。"""
        if not type_ids:
            return {}
        rows = (
            await self.session.execute(
                select(ConsumableItem.type_id, func.count())
                .where(ConsumableItem.type_id.in_(type_ids))
                .group_by(ConsumableItem.type_id)
            )
        ).all()
        return {t: c for t, c in rows}


# ============ 分类 ============
class ConsumableCategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, type_id: str, data: ConsumableCategoryCreate) -> ConsumableCategory:
        obj = ConsumableCategory(type_id=type_id, **data.model_dump())
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get(self, category_id: str) -> Optional[ConsumableCategory]:
        return (
            await self.session.execute(
                select(ConsumableCategory).where(ConsumableCategory.id == category_id)
            )
        ).scalar_one_or_none()

    async def list_by_type(self, type_id: str) -> list[ConsumableCategory]:
        return list(
            (
                await self.session.execute(
                # 按创建时间倒序：新增的分类置顶（与类型一致，需求#3）。
                select(ConsumableCategory)
                .where(ConsumableCategory.type_id == type_id)
                .order_by(ConsumableCategory.created_at.desc())
                )
            ).scalars().all()
        )

    async def update(
        self, obj: ConsumableCategory, data: ConsumableCategoryUpdate
    ) -> ConsumableCategory:
        # R-03：无条件 setattr（exclude_unset 已区分未提供 vs 显式 None）。
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: ConsumableCategory) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def count_items(self, category_id: str) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(ConsumableItem)
                .where(ConsumableItem.category_id == category_id)
            )
        ).scalar() or 0

    async def count_items_by_categories(self, category_ids: list[str]) -> dict[str, int]:
        """按分类批量统计耗材条目数（P-05：一次 GROUP BY 取代逐分类 N+1）。"""
        if not category_ids:
            return {}
        rows = (
            await self.session.execute(
                select(ConsumableItem.category_id, func.count())
                .where(ConsumableItem.category_id.in_(category_ids))
                .group_by(ConsumableItem.category_id)
            )
        ).all()
        return {c: n for c, n in rows}


# ============ 耗材 ============
class ConsumableItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: ConsumableItemCreate) -> ConsumableItem:
        payload = data.model_dump()
        qty = payload.pop("current_quantity", 0)
        obj = ConsumableItem(**payload, current_quantity=qty)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def get(self, item_id: str) -> Optional[ConsumableItem]:
        return (
            await self.session.execute(
                select(ConsumableItem).where(ConsumableItem.id == item_id)
            )
        ).scalar_one_or_none()

    async def list(
        self,
        *,
        page: int = 1,
        size: int = 20,
        type_id: Optional[str] = None,
        category_id: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[list[ConsumableItem], int]:
        conditions = []
        if type_id:
            conditions.append(ConsumableItem.type_id == type_id)
        if category_id:
            conditions.append(ConsumableItem.category_id == category_id)
        if keyword:
            kw = f"%{keyword}%"
            conditions.append(
                or_(
                    ConsumableItem.name.ilike(kw),
                    ConsumableItem.spec.ilike(kw),
                    ConsumableItem.remark.ilike(kw),
                )
            )
        stmt = select(ConsumableItem)
        count_stmt = select(func.count()).select_from(ConsumableItem)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = (
            stmt.order_by(ConsumableItem.name)
            .offset((page - 1) * size)
            .limit(size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def update(self, obj: ConsumableItem, data: ConsumableItemUpdate) -> ConsumableItem:
        # R-03：无条件 setattr（exclude_unset 已区分未提供 vs 显式 None）。
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        await self.session.flush()
        return obj

    async def set_quantity(self, obj: ConsumableItem, qty: int) -> ConsumableItem:
        obj.current_quantity = qty
        await self.session.flush()
        return obj

    async def delete(self, obj: ConsumableItem) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def count_all(self) -> tuple[int, int]:
        """耗材条目总数与实时库存总量（current_quantity 求和）。"""
        res = (
            await self.session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(ConsumableItem.current_quantity), 0),
                ).select_from(ConsumableItem)
            )
        ).one()
        return (res[0] or 0, int(res[1] or 0))


# ============ 库存变动记录 ============
class ConsumableRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **kwargs) -> ConsumableRecord:
        obj = ConsumableRecord(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def list_by_item(
        self, item_id: str, page: int = 1, size: int = 50
    ) -> Tuple[list[ConsumableRecord], int]:
        conditions = [ConsumableRecord.item_id == item_id]
        stmt = select(ConsumableRecord)
        count_stmt = select(func.count()).select_from(ConsumableRecord)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = (
            stmt.order_by(ConsumableRecord.operation_time.desc(), ConsumableRecord.created_at.desc())
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
    ) -> Tuple[list[ConsumableRecord], int]:
        conditions = []
        if item_id:
            conditions.append(ConsumableRecord.item_id == item_id)
        if operation_type:
            conditions.append(ConsumableRecord.operation_type == operation_type)
        # type_id / category_id 作用于关联耗材，需 join。
        stmt = select(ConsumableRecord)
        count_stmt = select(func.count()).select_from(ConsumableRecord)
        if type_id or category_id:
            stmt = stmt.join(ConsumableRecord.item)
            count_stmt = count_stmt.join(ConsumableRecord.item)
            if type_id:
                conditions.append(ConsumableItem.type_id == type_id)
            if category_id:
                conditions.append(ConsumableItem.category_id == category_id)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = (
            stmt.order_by(ConsumableRecord.operation_time.desc(), ConsumableRecord.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total
