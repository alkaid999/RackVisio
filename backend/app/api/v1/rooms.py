"""机房路由：CRUD + 容量统计 + 机房下机柜 + 大屏。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.rbac import require_permission
from app.schemas.common import ImportResult, ok, paginated
from app.schemas.rack import RackCreate, RackOut
from app.schemas.room import RoomCreate, RoomImportRowsRequest, RoomOut, RoomStats, RoomUpdate
from app.services.dashboard_service import DashboardService
from app.services.rack_service import RackService
from app.services.room_service import RoomService

router = APIRouter(prefix="/rooms", tags=["rooms"])


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
    return ok([RoomOut.model_validate(r).model_dump() for r in items])


@router.post("/import", dependencies=[Depends(require_permission("room:edit"))])
async def import_rooms(
    payload: RoomImportRowsRequest, db: AsyncSession = Depends(get_db)
):
    """批量导入机房：前端解析文件为 JSON 行后提交，后端逐行校验并创建。

    必须在 ``/{room_id}`` 路由之前注册，避免被其路径模板拦截。
    """
    svc = RoomService(db)
    result = await svc.import_rooms(payload.items)
    return ok(ImportResult.model_validate(result))


@router.post("", dependencies=[Depends(require_permission("room:edit"))])
async def create_room(payload: RoomCreate, db: AsyncSession = Depends(get_db)):
    svc = RoomService(db)
    room = await svc.create_room(payload)
    return ok(RoomOut.model_validate(room))


@router.get("/{room_id}", dependencies=[Depends(require_permission("room:view"))])
async def get_room(room_id: str, db: AsyncSession = Depends(get_db)):
    svc = RoomService(db)
    room = await svc.get_room(room_id)
    return ok(RoomOut.model_validate(room))


@router.put("/{room_id}", dependencies=[Depends(require_permission("room:edit"))])
async def update_room(
    room_id: str, payload: RoomUpdate, db: AsyncSession = Depends(get_db)
):
    svc = RoomService(db)
    room = await svc.update_room(room_id, payload)
    return ok(RoomOut.model_validate(room))


@router.delete("/{room_id}", dependencies=[Depends(require_permission("room:edit"))])
async def delete_room(room_id: str, db: AsyncSession = Depends(get_db)):
    svc = RoomService(db)
    await svc.delete_room(room_id)
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


@router.post("/{room_id}/racks", dependencies=[Depends(require_permission("rack:edit"))])
async def create_rack_in_room(
    room_id: str, payload: RackCreate, db: AsyncSession = Depends(get_db)
):
    svc = RackService(db)
    payload.room_id = room_id  # 路径优先
    rack = await svc.create_rack(payload)
    return ok(RackOut.model_validate(rack))


@router.get("/{room_id}/dashboard", dependencies=[Depends(require_permission("room:view"))])
async def dashboard(room_id: str, db: AsyncSession = Depends(get_db)):
    svc = DashboardService(db)
    data = await svc.get_room_dashboard(room_id)
    return ok(data)
