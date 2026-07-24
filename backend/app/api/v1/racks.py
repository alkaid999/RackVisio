"""机柜路由：增删改查 / U 位图 / U 位冲突 / 设备上架下架 / 候选设备。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.rbac import get_current_user, require_permission
from app.repositories.mount_record_repo import MountRecordRepository
from app.schemas.common import ImportResult, ok, paginated
from app.schemas.device import DeviceOut
from app.schemas.rack import (
    RackBatchCreate,
    RackBatchResult,
    RackCreate,
    RackImportRowsRequest,
    RackListItem,
    RackMountRequest,
    RackOut,
    RackPositionsUpdate,
    RackUMap,
    RackUMapSlot,
    RackUnmountRequest,
    RackUpdate,
)
from app.services.device_service import DeviceService
from app.services.rack_service import RackService

router = APIRouter(prefix="/racks", tags=["racks"])


@router.get("", dependencies=[Depends(require_permission("rack:view"))])
async def list_racks(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=500),
    room_id: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
):
    """机柜管理列表（可全局，也可按机房 / 关键字 / 状态过滤）。"""
    svc = RackService(db)
    items, total = await svc.list_filtered(
        room_id=room_id, keyword=keyword, status=status, page=page, size=size
    )
    return paginated(items, total, page, size)


@router.post("/positions", dependencies=[Depends(require_permission("rack:edit"))])
async def update_positions(
    payload: RackPositionsUpdate, db: AsyncSession = Depends(get_db)
):
    """批量更新机柜网格坐标（2D 平面图拖拽持久化）。"""
    svc = RackService(db)
    await svc.update_positions([p.model_dump() for p in payload.positions])
    return ok()


@router.post("", dependencies=[Depends(require_permission("rack:edit"))])
async def create_rack(payload: RackCreate, db: AsyncSession = Depends(get_db)):
    """创建机柜（room_id 置于请求体）。"""
    svc = RackService(db)
    rack = await svc.create_rack(payload)
    return ok(RackOut.model_validate(rack))


@router.post("/batch", dependencies=[Depends(require_permission("rack:edit"))])
async def create_racks_batch(payload: RackBatchCreate, db: AsyncSession = Depends(get_db)):
    """批量新增机柜：一次请求一个事务，返回成功 / 失败明细。

    必须在 ``/{rack_id}`` 路由之前注册，避免被其路径模板拦截。
    """
    svc = RackService(db)
    result = await svc.create_racks_batch(payload)
    return ok(RackBatchResult.model_validate(result))


@router.get("/export", dependencies=[Depends(require_permission("rack:view"))])
async def export_racks(
    db: AsyncSession = Depends(get_db),
    room_id: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
):
    """按当前筛选条件导出全部机柜（不分页）。返回行数组，由前端落地为文件。"""
    svc = RackService(db)
    items, _ = await svc.list_filtered(
        page=1, size=100000, room_id=room_id, keyword=keyword, status=status
    )
    return ok([r.model_dump() for r in items])


@router.post("/import", dependencies=[Depends(require_permission("rack:edit"))])
async def import_racks(
    payload: RackImportRowsRequest, db: AsyncSession = Depends(get_db)
):
    """批量导入机柜：前端解析文件为 JSON 行后提交，后端逐行校验并创建。

    必须在 ``/{rack_id}`` 路由之前注册，避免被其路径模板拦截。
    """
    svc = RackService(db)
    result = await svc.import_racks(payload.items)
    return ok(ImportResult.model_validate(result))


@router.get("/{rack_id}", dependencies=[Depends(require_permission("rack:view"))])
async def get_rack(rack_id: str, db: AsyncSession = Depends(get_db)):
    svc = RackService(db)
    rack = await svc.get_rack(rack_id)
    return ok(RackOut.model_validate(rack))


@router.put("/{rack_id}", dependencies=[Depends(require_permission("rack:edit"))])
async def update_rack(
    rack_id: str, payload: RackUpdate, db: AsyncSession = Depends(get_db)
):
    svc = RackService(db)
    rack = await svc.update_rack(rack_id, payload)
    return ok(RackOut.model_validate(rack))


@router.delete("/{rack_id}", dependencies=[Depends(require_permission("rack:edit"))])
async def delete_rack(rack_id: str, db: AsyncSession = Depends(get_db)):
    svc = RackService(db)
    await svc.delete_rack(rack_id)
    return ok()


@router.get("/{rack_id}/devices", dependencies=[Depends(require_permission("rack:view"))])
async def rack_devices(rack_id: str, db: AsyncSession = Depends(get_db)):
    await RackService(db).get_rack(rack_id)  # 校验存在
    svc = DeviceService(db)
    items, _ = await svc.list_devices(rack_id=rack_id)
    return ok(items)


@router.get("/{rack_id}/u-map", dependencies=[Depends(require_permission("rack:view"))])
async def rack_u_map(rack_id: str, db: AsyncSession = Depends(get_db)):
    """机柜 U 位占用图（自底向上，U=1 在最底部）。

    位置信息来自有效上架记录（mount_records），设备表不含位置字段。
    """
    svc = RackService(db)
    rack = await svc.get_rack(rack_id)
    mounts = await MountRecordRepository(db).list_active_in_rack(rack_id)
    slot_map: dict[int, tuple[str, str, str]] = {}
    for record, name, dtype, _ in mounts:
        for u in range(record.start_u, record.start_u + record.occupied_u):
            slot_map[u] = (record.device_id, name, dtype)
    slots = [
        RackUMapSlot(
            u=u,
            device_id=slot_map[u][0] if u in slot_map else None,
            device_name=slot_map[u][1] if u in slot_map else None,
            device_type=slot_map[u][2] if u in slot_map else None,
        )
        for u in range(1, rack.total_u + 1)
    ]
    return ok(
        RackUMap(
            rack_id=rack.id,
            total_u=rack.total_u,
            used_u=rack.used_u,
            status=rack.status,
            slots=slots,
        )
    )


@router.post("/{rack_id}/check-u", dependencies=[Depends(require_permission("rack:view"))])
async def check_u(
    rack_id: str, payload: RackMountRequest, db: AsyncSession = Depends(get_db)
):
    svc = DeviceService(db)
    # 占用 U 数取自设备固有属性 u_height（上架时带出）。
    device = await DeviceService(db).get_device_obj(payload.device_id)
    size_u = device.u_height or 1 if device else 1
    result = await svc.check_u_conflict(
        rack_id, payload.start_u, size_u, exclude_device_id=payload.device_id
    )
    return ok(
        {
            "rack_id": rack_id,
            "start_u": payload.start_u,
            "size_u": size_u,
            "conflict": result.get("conflict", False),
            "conflict_u": result.get("conflict_u", []),
            "conflict_device": result.get("conflict_device"),
            "error": result.get("error"),
        }
    )


@router.post("/{rack_id}/mount", dependencies=[Depends(require_permission("rack:edit"))])
async def mount_device(
    rack_id: str,
    payload: RackMountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """上架设备到指定 U 位（写入上架记录并同步设备状态）。

    操作人（上架人）强制同步为当前登录用户，忽略请求体传入值。
    """
    svc = RackService(db)
    operator = current_user.get("user_name") or current_user.get("sub")
    await svc.mount_device(
        rack_id, payload.device_id, payload.start_u, mounted_by=operator
    )
    return ok()


@router.post("/{rack_id}/unmount", dependencies=[Depends(require_permission("rack:edit"))])
async def unmount_device(
    rack_id: str,
    payload: RackUnmountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """将设备从机柜下架（有效记录置已下架并填下架信息）。

    操作人（下架人）强制同步为当前登录用户，忽略请求体传入值。
    """
    svc = RackService(db)
    operator = current_user.get("user_name") or current_user.get("sub")
    await svc.unmount_device(rack_id, payload.device_id, unmounted_by=operator)
    return ok()


@router.get("/{rack_id}/candidate-devices", dependencies=[Depends(require_permission("rack:view"))])
async def candidate_devices(rack_id: str, db: AsyncSession = Depends(get_db)):
    """候选上架设备：未挂载到任何机柜的设备（仓库 / 空闲 / 下架设备池）。"""
    await RackService(db).get_rack(rack_id)  # 校验机柜存在
    items = await RackService(db).list_candidate_devices()
    return ok([DeviceOut.model_validate(d) for d in items])
