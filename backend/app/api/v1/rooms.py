"""机房路由：CRUD + 容量统计 + 机房下机柜 + 大屏。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.audit_diff import build_create_detail, build_update_detail
from app.core.deps import get_db
from app.core.rbac import require_permission
from app.schemas.common import ImportResult, ok, paginated
from app.schemas.rack import RackCreate, RackOut
from app.schemas.room import RoomCreate, RoomImportRowsRequest, RoomOut, RoomStats, RoomUpdate
from app.services.dashboard_service import DashboardService
from app.services.device_service import DeviceService
from app.services.rack_service import RackService
from app.services.room_service import RoomService

router = APIRouter(prefix="/rooms", tags=["rooms"])

# 更新审计要记录的字段（中文标签）
ROOM_FIELD_LABELS = {
    "name": "名称",
    "code": "编号",
    "alias": "别名",
    "area": "区域",
    "building": "楼宇",
    "floor": "楼层",
    "address": "地址",
    "status": "状态",
}

# 创建审计要罗列的初始关键属性（名称已作为对象名展示，不再重复）。
ROOM_CREATE_LABELS = {
    "code": "编号",
    "area": "区域",
    "building": "楼宇",
    "floor": "楼层",
    "address": "地址",
    "status": "状态",
}


@router.get("", dependencies=[Depends(require_permission("room:view"))])
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    name: Optional[str] = None,
    area: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
):
    svc = RoomService(db)
    items, total = await svc.list_rooms(
        page=page, size=size, name=name, area=area, status=status, keyword=keyword
    )
    return paginated([RoomOut.model_validate(r) for r in items], total, page, size)


@router.get("/export", dependencies=[Depends(require_permission("room:view"))])
async def export_rooms(
    request: Request,
    db: AsyncSession = Depends(get_db),
    area: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
):
    """按当前筛选条件导出全部机房（不分页）。返回行数组，由前端用 ExcelJS 落地为文件。"""
    svc = RoomService(db)
    items, _ = await svc.list_rooms(
        page=1, size=100000, area=area, status=status, keyword=keyword
    )
    await log_audit(
        request=request,
        module="room",
        action="export",
        object_type="机房",
        detail=f"导出机房 {len(items)} 个",
    )
    return ok([RoomOut.model_validate(r).model_dump() for r in items])


@router.post("/import", dependencies=[Depends(require_permission("room:edit"))])
async def import_rooms(
    payload: RoomImportRowsRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """批量导入机房：前端解析文件为 JSON 行后提交，后端逐行校验并创建。

    必须在 ``/{room_id}`` 路由之前注册，避免被其路径模板拦截。
    """
    svc = RoomService(db)
    result = await svc.import_rooms(payload.items)
    await log_audit(
        request=request,
        module="room",
        action="import",
        object_type="机房",
        detail=f"导入机房：成功 {result.created} 个，失败 {result.failed} 个",
    )
    return ok(ImportResult.model_validate(result))


@router.post("", dependencies=[Depends(require_permission("room:edit"))])
async def create_room(payload: RoomCreate, request: Request, db: AsyncSession = Depends(get_db)):
    svc = RoomService(db)
    room = await svc.create_room(payload)
    detail = build_create_detail(room, ROOM_CREATE_LABELS)
    await log_audit(request=request, module="room", action="create", object_type="机房", object_id=room.id, object_name=room.name, detail=detail)
    return ok(RoomOut.model_validate(room))


@router.get("/{room_id}", dependencies=[Depends(require_permission("room:view"))])
async def get_room(room_id: str, db: AsyncSession = Depends(get_db)):
    svc = RoomService(db)
    room = await svc.get_room(room_id)
    return ok(RoomOut.model_validate(room))


@router.put("/{room_id}", dependencies=[Depends(require_permission("room:edit"))])
async def update_room(
    room_id: str, payload: RoomUpdate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = RoomService(db)
    before = RoomOut.model_validate(await svc.get_room(room_id))
    room = await svc.update_room(room_id, payload)
    detail = build_update_detail(before, RoomOut.model_validate(room), ROOM_FIELD_LABELS)
    await log_audit(request=request, module="room", action="update", object_type="机房", object_id=room.id, object_name=room.name, detail=detail)
    return ok(RoomOut.model_validate(room))


@router.delete("/{room_id}", dependencies=[Depends(require_permission("room:edit"))])
async def delete_room(room_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    svc = RoomService(db)
    room = await svc.get_room(room_id)
    name = room.name
    await svc.delete_room(room_id)
    await log_audit(request=request, module="room", action="delete", object_type="机房", object_id=room_id, object_name=name, detail=f"删除机房「{name}」")
    return ok()


@router.get("/{room_id}/stats", dependencies=[Depends(require_permission("room:view"))])
async def room_stats(room_id: str, db: AsyncSession = Depends(get_db)):
    svc = RoomService(db)
    stats: RoomStats = await svc.get_stats(room_id)
    return ok(stats)


@router.get("/{room_id}/racks", dependencies=[Depends(require_permission("room:view"))])
async def room_racks(room_id: str, db: AsyncSession = Depends(get_db)):
    svc = RoomService(db)
    await svc.get_room(room_id)  # 校验存在
    racks = await RackService(db).list_racks(room_id)
    return ok([RackOut.model_validate(r) for r in racks])


@router.get("/{room_id}/devices", dependencies=[Depends(require_permission("room:view"))])
async def room_devices(room_id: str, db: AsyncSession = Depends(get_db)):
    """整机房设备一次性返回（替代前端逐机柜 N+1 请求）。

    返回该机房内所有已上架设备，每条携带 ``current_rack_id`` / ``current_start_u``，
    前端按 ``current_rack_id`` 分组即可定位到具体机柜与 U 位。
    """
    await RoomService(db).get_room(room_id)  # 校验存在
    devices, _ = await DeviceService(db).list_devices(room_id=room_id, size=100000)
    return ok([d.model_dump() for d in devices])


@router.post("/{room_id}/racks", dependencies=[Depends(require_permission("rack:edit"))])
async def create_rack_in_room(
    room_id: str, payload: RackCreate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = RackService(db)
    room = await RoomService(db).get_room(room_id)  # 校验存在并取机房可读名称
    payload.room_id = room_id  # 路径优先
    rack = await svc.create_rack(payload)
    await log_audit(
        request=request,
        module="rack",
        action="create",
        object_type="机柜",
        object_id=rack.id,
        object_name=rack.name or rack.code,
        detail=f"在机房「{room.name}」下新增机柜",
    )
    return ok(RackOut.model_validate(rack))


@router.get("/{room_id}/dashboard", dependencies=[Depends(require_permission("room:view"))])
async def dashboard(room_id: str, db: AsyncSession = Depends(get_db)):
    svc = DashboardService(db)
    data = await svc.get_room_dashboard(room_id)
    return ok(data)
