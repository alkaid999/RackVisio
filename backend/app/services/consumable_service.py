"""耗材管理业务逻辑（CRUD + 库存变动事务）。

库存变动（adjust_stock）为原子事务：校验 → 更新 ConsumableItem.current_quantity
→ 写入一条 ConsumableRecord（append-only）→ 提交。所有历史均可通过记录追溯。
操作人（operator）由调用方（路由层）注入当前登录用户，后端不信任前端传入。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.enums import ConsumableOpType
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.consumable import ConsumableItem
from app.repositories.consumable_repo import (
    ConsumableCategoryRepository,
    ConsumableItemRepository,
    ConsumableRecordRepository,
    ConsumableTypeRepository,
)
from app.schemas.consumable import (
    ConsumableCategoryCreate,
    ConsumableCategoryOut,
    ConsumableCategoryUpdate,
    ConsumableItemCreate,
    ConsumableItemOut,
    ConsumableItemUpdate,
    ConsumableRecordOut,
    ConsumableTypeCreate,
    ConsumableTypeOut,
    ConsumableTypeUpdate,
    StockAdjustRequest,
)

_OP_VALUES = {e.value for e in ConsumableOpType}


class ConsumableService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.type_repo = ConsumableTypeRepository(session)
        self.category_repo = ConsumableCategoryRepository(session)
        self.item_repo = ConsumableItemRepository(session)
        self.record_repo = ConsumableRecordRepository(session)

    # ============ 类型 ============
    async def create_type(self, data: ConsumableTypeCreate) -> ConsumableTypeOut:
        obj = await self.type_repo.create(data)
        await self.session.commit()
        await self.session.refresh(obj)
        return await self._type_out(obj)

    async def get_type(self, type_id: str) -> ConsumableTypeOut:
        obj = await self._require_type(type_id)
        return await self._type_out(obj)

    async def list_types(self) -> list[ConsumableTypeOut]:
        objs = await self.type_repo.list()
        out = []
        for o in objs:
            out.append(await self._type_out(o))
        return out

    async def update_type(self, type_id: str, data: ConsumableTypeUpdate) -> ConsumableTypeOut:
        obj = await self._require_type(type_id)
        obj = await self.type_repo.update(obj, data)
        await self.session.commit()
        await self.session.refresh(obj)
        return await self._type_out(obj)

    async def delete_type(self, type_id: str) -> None:
        obj = await self._require_type(type_id)
        if await self.type_repo.count_categories(type_id) > 0:
            raise ConflictError("该耗材类型下仍存在分类，无法删除（请先删除其下分类与耗材）")
        if await self.type_repo.count_items(type_id) > 0:
            raise ConflictError("该耗材类型下仍存在耗材，无法删除（请先删除其下耗材）")
        await self.type_repo.delete(obj)
        await self.session.commit()

    # ============ 分类 ============
    async def create_category(self, type_id: str, data: ConsumableCategoryCreate) -> ConsumableCategoryOut:
        await self._require_type(type_id)
        obj = await self.category_repo.create(type_id, data)
        await self.session.commit()
        obj = await self.category_repo.get(obj.id)
        return await self._category_out(obj)

    async def get_category(self, category_id: str) -> ConsumableCategoryOut:
        obj = await self._require_category(category_id)
        return await self._category_out(obj)

    async def list_categories(self, type_id: str) -> list[ConsumableCategoryOut]:
        # 校验类型存在（不存在则直接 404，避免误把空列表当成正常）。
        await self._require_type(type_id)
        objs = await self.category_repo.list_by_type(type_id)
        return [await self._category_out(o) for o in objs]

    async def update_category(self, category_id: str, data: ConsumableCategoryUpdate) -> ConsumableCategoryOut:
        obj = await self._require_category(category_id)
        obj = await self.category_repo.update(obj, data)
        await self.session.commit()
        obj = await self.category_repo.get(obj.id)
        return await self._category_out(obj)

    async def delete_category(self, category_id: str) -> None:
        obj = await self._require_category(category_id)
        if await self.category_repo.count_items(category_id) > 0:
            raise ConflictError("该分类下仍存在耗材，无法删除（请先删除其下耗材）")
        await self.category_repo.delete(obj)
        await self.session.commit()

    # ============ 耗材 ============
    async def create_item(self, data: ConsumableItemCreate, operator: Optional[str] = None) -> ConsumableItemOut:
        await self._require_type(data.type_id)
        await self._require_category(data.category_id)
        obj = await self.item_repo.create(data)
        # 初始数量 > 0 时，落一条「盘点」记录留痕（初始建账）。
        if data.current_quantity and data.current_quantity > 0:
            await self.record_repo.create(
                item_id=obj.id,
                operation_time=utcnow(),
                operation_type=ConsumableOpType.CHECK.value,
                quantity=data.current_quantity,
                reason="初始建账",
                operator=operator,
                balance_after=data.current_quantity,
            )
        await self.session.commit()
        obj = await self.item_repo.get(obj.id)
        return await self._item_out(obj)

    async def get_item(self, item_id: str) -> ConsumableItemOut:
        obj = await self._require_item(item_id)
        return await self._item_out(obj)

    async def list_items(
        self, *, page: int = 1, size: int = 20, type_id=None, category_id=None, keyword=None
    ) -> tuple[list[ConsumableItemOut], int]:
        objs, total = await self.item_repo.list(
            page=page, size=size, type_id=type_id, category_id=category_id, keyword=keyword
        )
        return [await self._item_out(o) for o in objs], total

    async def update_item(self, item_id: str, data: ConsumableItemUpdate) -> ConsumableItemOut:
        obj = await self._require_item(item_id)
        obj = await self.item_repo.update(obj, data)
        await self.session.commit()
        obj = await self.item_repo.get(obj.id)
        return await self._item_out(obj)

    async def delete_item(self, item_id: str) -> None:
        obj = await self._require_item(item_id)
        await self.item_repo.delete(obj)  # 级联删除其库存变动记录
        await self.session.commit()

    # ============ 库存变动 ============
    async def adjust_stock(
        self, item_id: str, payload: StockAdjustRequest, operator: Optional[str] = None
    ) -> ConsumableItemOut:
        obj = await self._require_item(item_id)
        op = payload.operation_type
        if op not in _OP_VALUES:
            raise ValidationError(
                f"非法的操作类型：{op}（应为 入库 / 领用 / 报废 / 盘点）"
            )
        qty = payload.quantity
        if op == ConsumableOpType.CHECK.value:
            if qty < 0:
                raise ValidationError("盘点数量不能为负数")
            new_balance = qty
        else:
            if qty < 1:
                raise ValidationError("入库 / 领用 / 报废的数量须 >= 1")
            if op == ConsumableOpType.IN.value:
                new_balance = obj.current_quantity + qty
            else:  # 领用 / 报废：扣减，禁止透支
                new_balance = obj.current_quantity - qty
                if new_balance < 0:
                    raise ValidationError(
                        f"库存不足：当前结存 {obj.current_quantity}，无法{op} {qty}"
                    )
        obj = await self.item_repo.set_quantity(obj, new_balance)
        await self.record_repo.create(
            item_id=obj.id,
            operation_time=payload.operation_time or utcnow(),
            operation_type=op,
            quantity=qty,
            reason=payload.reason,
            operator=operator,
            balance_after=new_balance,
        )
        await self.session.commit()
        obj = await self.item_repo.get(obj.id)
        return await self._item_out(obj)

    # ============ 库存变动历史 ============
    async def list_records_by_item(self, item_id: str, page: int = 1, size: int = 50):
        await self._require_item(item_id)
        objs, total = await self.record_repo.list_by_item(item_id, page=page, size=size)
        return [await self._record_out(o) for o in objs], total

    async def list_records(
        self, *, page: int = 1, size: int = 20, type_id=None, category_id=None, item_id=None, operation_type=None
    ):
        objs, total = await self.record_repo.list_all(
            page=page, size=size, type_id=type_id, category_id=category_id,
            item_id=item_id, operation_type=operation_type,
        )
        return [await self._record_out(o) for o in objs], total

    # ============ 内部辅助 ============
    async def _require_type(self, type_id: str):
        obj = await self.type_repo.get(type_id)
        if obj is None:
            raise NotFoundError("耗材类型不存在")
        return obj

    async def _require_category(self, category_id: str):
        obj = await self.category_repo.get(category_id)
        if obj is None:
            raise NotFoundError("耗材分类不存在")
        return obj

    async def _require_item(self, item_id: str):
        obj = await self.item_repo.get(item_id)
        if obj is None:
            raise NotFoundError("耗材不存在")
        return obj

    async def _type_out(self, obj) -> ConsumableTypeOut:
        out = ConsumableTypeOut.model_validate(obj)
        out.category_count = await self.type_repo.count_categories(obj.id)
        out.item_count = await self.type_repo.count_items(obj.id)
        return out

    async def _category_out(self, obj) -> ConsumableCategoryOut:
        out = ConsumableCategoryOut.model_validate(obj)
        out.type_name = obj.type.name if obj.type else None
        out.item_count = await self.category_repo.count_items(obj.id)
        return out

    async def _item_out(self, obj: ConsumableItem) -> ConsumableItemOut:
        out = ConsumableItemOut.model_validate(obj)
        out.type_name = obj.type.name if obj.type else None
        out.category_name = obj.category.name if obj.category else None
        return out

    async def _record_out(self, obj) -> ConsumableRecordOut:
        out = ConsumableRecordOut.model_validate(obj)
        item = obj.item
        out.item_name = item.name if item else None
        if item:
            out.type_name = item.type.name if item.type else None
            out.category_name = item.category.name if item.category else None
        return out
