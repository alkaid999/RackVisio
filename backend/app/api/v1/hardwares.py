"""硬件管理路由：类型 / 分类 / 硬件 CRUD + 设备硬件联动（分配/回收）+ 变动历史。

权限：所有写操作（增删改/分配/回收）要求 ``hardware:edit``；读操作要求 ``hardware:view``。
操作人（operator）由后端从 JWT payload 注入，前端无需（也不应）传操作员身份。

设备硬件联动（需求#1/#4，独立个体模型）：
- GET /devices/{device_id}/hardwares：设备已安装硬件列表。
- POST /devices/{device_id}/hardwares：从硬件管理选「在库」的具体硬件分配到设备（一对一）。
- DELETE /devices/{device_id}/hardwares/{hardware_item_id}：回收（硬件回库，可重新分配）。

端点一览：
- 类型：GET/POST /hardwares/types；GET/PUT/DELETE /hardwares/types/{id}
- 分类：GET/POST /hardwares/types/{type_id}/categories；
        GET/PUT/DELETE /hardwares/categories/{id}
- 硬件：GET/POST /hardwares/items；GET/PUT/DELETE /hardwares/items/{id}
- 设备联动：GET/POST /hardwares/devices/{device_id}/hardwares；
            DELETE /hardwares/devices/{device_id}/hardwares/{hardware_item_id}
- 历史：GET /hardwares/items/{id}/records；GET /hardwares/records（全局）
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.rbac import get_current_user, require_permission
from app.schemas.common import ImportResult, ok, paginated
from app.schemas.hardware import (
    DeviceHardwareAssignRequest,
    HardwareCategoryCreate,
    HardwareCategoryOut,
    HardwareCategoryUpdate,
    HardwareImportRowsRequest,
    HardwareItemCreate,
    HardwareItemOut,
    HardwareItemUpdate,
    HardwareRecordOut,
    HardwareTypeCreate,
    HardwareTypeOut,
    HardwareTypeUpdate,
    ReorderRequest,
)
from app.services.hardware_service import HardwareService
from app.api.v1.streaming import _batched, export_json_stream


def _operator(payload: dict) -> Optional[str]:
    """从 JWT payload 取操作人（优先 user_name，回退 sub）。"""
    return payload.get("user_name") or payload.get("sub")


router = APIRouter(prefix="/hardwares", tags=["hardwares"])


# ============ 硬件类型 ============
@router.get("/types", dependencies=[Depends(require_permission("hardware:view"))])
async def list_types(db: AsyncSession = Depends(get_db)):
    svc = HardwareService(db)
    return ok(await svc.list_types())


@router.post("/types", dependencies=[Depends(require_permission("hardware:edit"))])
async def create_type(payload: HardwareTypeCreate, db: AsyncSession = Depends(get_db)):
    svc = HardwareService(db)
    obj = await svc.create_type(payload)
    return ok(obj)


@router.get("/types/{type_id}", dependencies=[Depends(require_permission("hardware:view"))])
async def get_type(type_id: str, db: AsyncSession = Depends(get_db)):
    svc = HardwareService(db)
    return ok(await svc.get_type(type_id))


@router.put("/types/{type_id}", dependencies=[Depends(require_permission("hardware:edit"))])
async def update_type(
    type_id: str, payload: HardwareTypeUpdate, db: AsyncSession = Depends(get_db)
):
    svc = HardwareService(db)
    obj = await svc.update_type(type_id, payload)
    return ok(obj)


@router.delete("/types/{type_id}", dependencies=[Depends(require_permission("hardware:edit"))])
async def delete_type(type_id: str, db: AsyncSession = Depends(get_db)):
    svc = HardwareService(db)
    await svc.delete_type(type_id)
    return ok()


# 类型手动排序（须在 /types/{type_id} 路由之前声明，避免路径段被当 id 匹配）。
@router.post("/types/reorder", dependencies=[Depends(require_permission("hardware:edit"))])
async def reorder_types(payload: ReorderRequest, db: AsyncSession = Depends(get_db)):
    svc = HardwareService(db)
    return ok(await svc.reorder_types(payload.ids))


# ============ 硬件分类 ============
@router.get(
    "/types/{type_id}/categories",
    dependencies=[Depends(require_permission("hardware:view"))],
)
async def list_categories(type_id: str, db: AsyncSession = Depends(get_db)):
    svc = HardwareService(db)
    return ok(await svc.list_categories(type_id))


@router.post(
    "/types/{type_id}/categories",
    dependencies=[Depends(require_permission("hardware:edit"))],
)
async def create_category(
    type_id: str, payload: HardwareCategoryCreate, db: AsyncSession = Depends(get_db)
):
    svc = HardwareService(db)
    obj = await svc.create_category(type_id, payload)
    return ok(obj)


@router.get(
    "/categories/{category_id}",
    dependencies=[Depends(require_permission("hardware:view"))],
)
async def get_category(category_id: str, db: AsyncSession = Depends(get_db)):
    svc = HardwareService(db)
    return ok(await svc.get_category(category_id))


@router.put(
    "/categories/{category_id}",
    dependencies=[Depends(require_permission("hardware:edit"))],
)
async def update_category(
    category_id: str, payload: HardwareCategoryUpdate, db: AsyncSession = Depends(get_db)
):
    svc = HardwareService(db)
    obj = await svc.update_category(category_id, payload)
    return ok(obj)


@router.delete(
    "/categories/{category_id}",
    dependencies=[Depends(require_permission("hardware:edit"))],
)
async def delete_category(category_id: str, db: AsyncSession = Depends(get_db)):
    svc = HardwareService(db)
    await svc.delete_category(category_id)
    return ok()


# 分类手动排序（同类型内）。
@router.post(
    "/types/{type_id}/categories/reorder",
    dependencies=[Depends(require_permission("hardware:edit"))],
)
async def reorder_categories(
    type_id: str, payload: ReorderRequest, db: AsyncSession = Depends(get_db)
):
    svc = HardwareService(db)
    return ok(await svc.reorder_categories(type_id, payload.ids))


# ============ 具体硬件（独立个体）============
@router.get("/items", dependencies=[Depends(require_permission("hardware:view"))])
async def list_items(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    type_id: Optional[str] = None,
    category_id: Optional[str] = None,
    status: Optional[str] = Query(None, description="在库 / 已安装"),
    keyword: Optional[str] = None,
):
    svc = HardwareService(db)
    items, total = await svc.list_items(
        page=page, size=size, type_id=type_id, category_id=category_id,
        status=status, keyword=keyword,
    )
    return paginated(items, total, page, size)


@router.get("/export", dependencies=[Depends(require_permission("hardware:view"))])
async def export_hardwares(
    db: AsyncSession = Depends(get_db),
    type_id: Optional[str] = None,
    category_id: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
):
    """按当前筛选条件导出全部硬件（不分页，与机柜/机房导出一致）。

    分批查询 + 流式 JSON 传输（响应体格式与 ok() 一致，前端零改动）。
    """
    svc = HardwareService(db)

    async def fetch(page: int, size: int):
        items, total = await svc.list_items(
            page=page, size=size, type_id=type_id, category_id=category_id,
            status=status, keyword=keyword,
        )
        return [r.model_dump() for r in items], total

    return export_json_stream(_batched(fetch))


@router.post("/import", dependencies=[Depends(require_permission("hardware:edit"))])
async def import_hardwares(
    payload: HardwareImportRowsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """批量导入硬件：前端解析文件为 JSON 行后提交，后端逐行校验并创建。

    须注册在 ``/items`` 相关通配路由之前不冲突（路径独立），
    类型/分类按名称定位；单行失败仅计入 failures、不波及其余行。
    """
    svc = HardwareService(db)
    result = await svc.import_hardwares(payload.items, operator=_operator(current_user))
    return ok(ImportResult.model_validate(result))


@router.post("/items", dependencies=[Depends(require_permission("hardware:edit"))])
async def create_item(
    payload: HardwareItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    svc = HardwareService(db)
    obj = await svc.create_item(payload, operator=_operator(current_user))
    return ok(obj)


@router.get("/items/{item_id}", dependencies=[Depends(require_permission("hardware:view"))])
async def get_item(item_id: str, db: AsyncSession = Depends(get_db)):
    svc = HardwareService(db)
    return ok(await svc.get_item(item_id))


@router.put("/items/{item_id}", dependencies=[Depends(require_permission("hardware:edit"))])
async def update_item(
    item_id: str, payload: HardwareItemUpdate, db: AsyncSession = Depends(get_db)
):
    svc = HardwareService(db)
    obj = await svc.update_item(item_id, payload)
    return ok(obj)


@router.delete("/items/{item_id}", dependencies=[Depends(require_permission("hardware:edit"))])
async def delete_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    svc = HardwareService(db)
    await svc.delete_item(item_id, operator=_operator(current_user))
    return ok()


# ============ 设备硬件联动（一对一）============
@router.get(
    "/devices/{device_id}/hardwares",
    dependencies=[Depends(require_permission("hardware:view"))],
)
async def device_hardwares(device_id: str, db: AsyncSession = Depends(get_db)):
    """设备已安装硬件列表（设备详情页「设备硬件」卡片）。"""
    svc = HardwareService(db)
    return ok(await svc.list_device_hardwares(device_id))


@router.post(
    "/devices/{device_id}/hardwares",
    dependencies=[Depends(require_permission("hardware:edit"))],
)
async def assign_hardware(
    device_id: str,
    payload: DeviceHardwareAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """从硬件管理选「在库」的具体硬件分配到设备（与机柜上架选设备同理）。"""
    svc = HardwareService(db)
    obj = await svc.assign_to_device(device_id, payload, operator=_operator(current_user))
    return ok(obj)


@router.delete(
    "/devices/{device_id}/hardwares/{hardware_item_id}",
    dependencies=[Depends(require_permission("hardware:edit"))],
)
async def unassign_hardware(
    device_id: str,
    hardware_item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """回收：解除设备与硬件的关联，硬件回到「在库」（硬件管理重新可见、可分配）。"""
    svc = HardwareService(db)
    obj = await svc.unassign_from_device(device_id, hardware_item_id, operator=_operator(current_user))
    return ok(obj)


# ============ 硬件变动历史 ============
@router.get(
    "/items/{item_id}/records",
    dependencies=[Depends(require_permission("hardware:view"))],
)
async def item_records(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    svc = HardwareService(db)
    records, total = await svc.list_records_by_item(item_id, page=page, size=size)
    return paginated(records, total, page, size)


@router.get("/records", dependencies=[Depends(require_permission("hardware:view"))])
async def all_records(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    type_id: Optional[str] = None,
    category_id: Optional[str] = None,
    item_id: Optional[str] = None,
    operation_type: Optional[str] = None,
):
    svc = HardwareService(db)
    records, total = await svc.list_records(
        page=page, size=size, type_id=type_id, category_id=category_id,
        item_id=item_id, operation_type=operation_type,
    )
    return paginated(records, total, page, size)
