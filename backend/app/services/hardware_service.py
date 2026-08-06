"""硬件管理业务逻辑（CRUD + 设备分配/回收联动）。

与耗材的关键差异（独立个体模型）：硬件无批量库存，每件单独记录。
- 新增硬件：建档即「在库」，落「新增」记录。
- 删除硬件：仅「在库」可删（已安装须先回收），删除即报废出库，落「报废」记录。
- 设备添加硬件（assign_to_device）：选某一件「在库」硬件 → status=已安装、
  写 assigned_device_id/assigned_at，落「分配」记录（原子事务）。
- 设备删除硬件（unassign_from_device）：清空 assigned_device_id、status=在库，
  落「回收」记录（硬件回库，可在硬件管理重新分配）。
操作人（operator）由调用方（路由层）注入当前登录用户，后端不信任前端传入。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.core.enums import HardwareOpType, HardwareStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.device import Device
from app.models.hardware import HardwareItem
from app.repositories.device_repo import DeviceRepository
from app.repositories.hardware_repo import (
    HardwareCategoryRepository,
    HardwareItemRepository,
    HardwareRecordRepository,
    HardwareTypeRepository,
)
from app.schemas.hardware import (
    DeviceHardwareAssignRequest,
    HardwareCategoryCreate,
    HardwareCategoryOut,
    HardwareCategoryUpdate,
    HardwareItemCreate,
    HardwareItemOut,
    HardwareItemUpdate,
    HardwareRecordOut,
    HardwareTypeCreate,
    HardwareTypeOut,
    HardwareTypeUpdate,
)


class HardwareService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.type_repo = HardwareTypeRepository(session)
        self.category_repo = HardwareCategoryRepository(session)
        self.item_repo = HardwareItemRepository(session)
        self.record_repo = HardwareRecordRepository(session)
        self.device_repo = DeviceRepository(session)

    # ============ 类型 ============
    async def create_type(self, data: HardwareTypeCreate) -> HardwareTypeOut:
        obj = await self.type_repo.create(data)
        await self.session.commit()
        await self.session.refresh(obj)
        return await self._type_out(obj)

    async def get_type(self, type_id: str) -> HardwareTypeOut:
        obj = await self._require_type(type_id)
        return await self._type_out(obj)

    async def list_types(self) -> list[HardwareTypeOut]:
        objs = await self.type_repo.list()
        if not objs:
            return []
        type_ids = [o.id for o in objs]
        cat_counts = await self.type_repo.count_categories_by_types(type_ids)
        item_counts = await self.type_repo.count_items_by_types(type_ids)
        return [
            await self._type_out(o, cat_counts=cat_counts, item_counts=item_counts)
            for o in objs
        ]

    async def update_type(self, type_id: str, data: HardwareTypeUpdate) -> HardwareTypeOut:
        obj = await self._require_type(type_id)
        obj = await self.type_repo.update(obj, data)
        await self.session.commit()
        await self.session.refresh(obj)
        return await self._type_out(obj)

    async def delete_type(self, type_id: str) -> None:
        obj = await self._require_type(type_id)
        if await self.type_repo.count_categories(type_id) > 0:
            raise ConflictError("该硬件类型下仍存在分类，无法删除（请先删除其下分类与硬件）")
        if await self.type_repo.count_items(type_id) > 0:
            raise ConflictError("该硬件类型下仍存在硬件，无法删除（请先删除其下硬件）")
        await self.type_repo.delete(obj)
        await self.session.commit()

    async def reorder_types(self, ids: list[str]) -> list[HardwareTypeOut]:
        """类型手动排序（按传入顺序持久化），返回排序后的全量列表。"""
        if ids:
            await self.type_repo.reorder(ids)
            await self.session.commit()
        return await self.list_types()

    # ============ 分类 ============
    async def create_category(self, type_id: str, data: HardwareCategoryCreate) -> HardwareCategoryOut:
        await self._require_type(type_id)
        obj = await self.category_repo.create(type_id, data)
        await self.session.commit()
        obj = await self.category_repo.get(obj.id)
        return await self._category_out(obj)

    async def get_category(self, category_id: str) -> HardwareCategoryOut:
        obj = await self._require_category(category_id)
        return await self._category_out(obj)

    async def list_categories(self, type_id: str) -> list[HardwareCategoryOut]:
        await self._require_type(type_id)
        objs = await self.category_repo.list_by_type(type_id)
        if not objs:
            return []
        cat_ids = [o.id for o in objs]
        item_counts = await self.category_repo.count_items_by_categories(cat_ids)
        return [await self._category_out(o, counts=item_counts) for o in objs]

    async def update_category(self, category_id: str, data: HardwareCategoryUpdate) -> HardwareCategoryOut:
        obj = await self._require_category(category_id)
        obj = await self.category_repo.update(obj, data)
        await self.session.commit()
        obj = await self.category_repo.get(obj.id)
        return await self._category_out(obj)

    async def delete_category(self, category_id: str) -> None:
        obj = await self._require_category(category_id)
        if await self.category_repo.count_items(category_id) > 0:
            raise ConflictError("该分类下仍存在硬件，无法删除（请先删除其下硬件）")
        await self.category_repo.delete(obj)
        await self.session.commit()

    async def reorder_categories(self, type_id: str, ids: list[str]) -> list[HardwareCategoryOut]:
        """分类手动排序（类型内按传入顺序持久化），返回排序后的全量列表。"""
        await self._require_type(type_id)
        if ids:
            await self.category_repo.reorder(ids)
            await self.session.commit()
        return await self.list_categories(type_id)

    # ============ 硬件（独立个体）============
    async def create_item(self, data: HardwareItemCreate, operator: Optional[str] = None) -> HardwareItemOut:
        await self._require_type(data.type_id)
        await self._require_category(data.category_id)
        # SN 唯一性：非空时不得与已有硬件重复（R-01 模式，捕获 IntegrityError 转 409）。
        if data.sn and await self._sn_exists(data.sn):
            raise ConflictError(f"SN 号「{data.sn}」已存在，请检查（每个硬件独立编号）")
        obj = await self.item_repo.create(data)
        # 建档即「在库」，落「新增」记录留痕（每件硬件的生命周期起点）。
        await self.record_repo.create(
            item_id=obj.id,
            operation_time=utcnow(),
            operation_type=HardwareOpType.NEW.value,
            reason="建档入库",
            operator=operator,
        )
        await self.session.commit()
        obj = await self.item_repo.get(obj.id)
        return await self._item_out(obj)

    async def get_item(self, item_id: str) -> HardwareItemOut:
        obj = await self._require_item(item_id)
        return await self._item_out(obj)

    async def list_items(
        self, *, page: int = 1, size: int = 20, type_id=None, category_id=None,
        status=None, keyword=None,
    ) -> tuple[list[HardwareItemOut], int]:
        objs, total = await self.item_repo.list(
            page=page, size=size, type_id=type_id, category_id=category_id,
            status=status, keyword=keyword,
        )
        return [await self._item_out(o) for o in objs], total

    async def update_item(self, item_id: str, data: HardwareItemUpdate) -> HardwareItemOut:
        obj = await self._require_item(item_id)
        # SN 唯一性（排除自身）。
        if data.sn and data.sn != obj.sn:
            if await self._sn_exists(data.sn, exclude_id=obj.id):
                raise ConflictError(f"SN 号「{data.sn}」已存在，请检查（每个硬件独立编号）")
        obj = await self.item_repo.update(obj, data)
        await self.session.commit()
        obj = await self.item_repo.get(obj.id)
        return await self._item_out(obj)

    async def delete_item(self, item_id: str, operator: Optional[str] = None) -> None:
        obj = await self._require_item(item_id)
        # 防孤史：已安装（被设备占用）的硬件禁删，须先在对应设备上回收。
        if obj.status == HardwareStatus.INSTALLED.value:
            raise ConflictError("该硬件已安装到设备，无法删除（请先在对应设备上回收）")
        # 删除即报废出库，先落「报废」记录再级联删（记录随硬件删除一并清理）。
        await self.record_repo.create(
            item_id=obj.id,
            operation_time=utcnow(),
            operation_type=HardwareOpType.SCRAP.value,
            reason="报废出库",
            operator=operator,
        )
        await self.item_repo.delete(obj)  # 级联删除其全部变动记录
        await self.session.commit()

    # ============ 设备硬件联动（一对一）============
    async def list_device_hardwares(self, device_id: str) -> list[HardwareItemOut]:
        """设备已安装硬件列表（assigned_device_id = 该设备）。"""
        await self._require_device(device_id)
        objs = await self.item_repo.list_by_device(device_id)
        return [await self._item_out(o) for o in objs]

    async def assign_to_device(
        self, device_id: str, payload: DeviceHardwareAssignRequest, operator: Optional[str] = None
    ) -> HardwareItemOut:
        """设备添加硬件：从硬件管理选「在库」的具体硬件 → 一对一分配。

        语义（与机柜上架从设备列表选择同理）：该硬件被装到设备，状态→已安装。
        """
        await self._require_device(device_id)
        item = await self._require_item(payload.hardware_item_id)
        if item.status != HardwareStatus.IN_STOCK.value or item.assigned_device_id is not None:
            raise ConflictError(f"硬件「{item.name}」不在库（当前已安装或不可分配），请选择其他硬件")
        device = await self.device_repo.get(device_id)
        device_name = device.name if device else None
        item.status = HardwareStatus.INSTALLED.value
        item.assigned_device_id = device_id
        item.assigned_at = utcnow()
        await self.session.flush()
        await self.record_repo.create(
            item_id=item.id,
            operation_time=utcnow(),
            operation_type=HardwareOpType.ASSIGN.value,
            device_name=device_name,
            reason=payload.remark or f"分配到设备 {device_name or device_id}",
            operator=operator,
        )
        await self.session.commit()
        item = await self.item_repo.get(item.id)
        return await self._item_out(item)

    async def unassign_from_device(
        self, device_id: str, hardware_item_id: str, operator: Optional[str] = None
    ) -> HardwareItemOut:
        """设备删除硬件：解除一对一关联，硬件回到「在库」（硬件管理重新可见、可分配）。"""
        await self._require_device(device_id)
        item = await self._require_item(hardware_item_id)
        if item.assigned_device_id != device_id:
            raise ConflictError("该硬件未安装在此设备上，无法回收")
        device = await self.device_repo.get(device_id)
        device_name = device.name if device else None
        item.status = HardwareStatus.IN_STOCK.value
        item.assigned_device_id = None
        item.assigned_at = None
        await self.session.flush()
        await self.record_repo.create(
            item_id=item.id,
            operation_time=utcnow(),
            operation_type=HardwareOpType.RECOVER.value,
            device_name=device_name,
            reason=f"从设备 {device_name or device_id} 回收",
            operator=operator,
        )
        await self.session.commit()
        item = await self.item_repo.get(item.id)
        return await self._item_out(item)

    # ============ 变动记录 ============
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
    async def _sn_exists(self, sn: str, exclude_id: Optional[str] = None) -> bool:
        return await self.item_repo.sn_exists(sn, exclude_id=exclude_id)

    async def _require_type(self, type_id: str):
        obj = await self.type_repo.get(type_id)
        if obj is None:
            raise NotFoundError("硬件类型不存在")
        return obj

    async def _require_category(self, category_id: str):
        obj = await self.category_repo.get(category_id)
        if obj is None:
            raise NotFoundError("硬件分类不存在")
        return obj

    async def _require_item(self, item_id: str):
        obj = await self.item_repo.get(item_id)
        if obj is None:
            raise NotFoundError("硬件不存在")
        return obj

    async def _require_device(self, device_id: str):
        obj = await self.device_repo.get(device_id)
        if obj is None:
            raise NotFoundError("设备不存在")
        return obj

    async def _type_out(
        self, obj, cat_counts: Optional[dict] = None, item_counts: Optional[dict] = None
    ) -> HardwareTypeOut:
        out = HardwareTypeOut.model_validate(obj)
        if cat_counts is not None:
            out.category_count = cat_counts.get(obj.id, 0)
        else:
            out.category_count = await self.type_repo.count_categories(obj.id)
        if item_counts is not None:
            out.item_count = item_counts.get(obj.id, 0)
        else:
            out.item_count = await self.type_repo.count_items(obj.id)
        return out

    async def _category_out(
        self, obj, counts: Optional[dict] = None
    ) -> HardwareCategoryOut:
        out = HardwareCategoryOut.model_validate(obj)
        out.type_name = obj.type.name if obj.type else None
        if counts is not None:
            out.item_count = counts.get(obj.id, 0)
        else:
            out.item_count = await self.category_repo.count_items(obj.id)
        return out

    async def _item_out(self, obj: HardwareItem) -> HardwareItemOut:
        out = HardwareItemOut.model_validate(obj)
        out.type_name = obj.type.name if obj.type else None
        out.category_name = obj.category.name if obj.category else None
        # 已安装时补充设备名（冗余展示，避免前端再查一次）。
        if obj.assigned_device_id:
            dev = await self.device_repo.get(obj.assigned_device_id)
            out.assigned_device_name = dev.name if dev else None
        return out

    async def _record_out(self, obj) -> HardwareRecordOut:
        out = HardwareRecordOut.model_validate(obj)
        item = obj.item
        out.item_name = item.name if item else None
        out.item_sn = item.sn if item else None
        if item:
            out.type_name = item.type.name if item.type else None
            out.category_name = item.category.name if item.category else None
        return out
