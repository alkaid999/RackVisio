"""设备路由：列表/创建/详情/更新/删除。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.enums import DeviceStatus, DeviceType
from app.core.rbac import require_permission
from app.schemas.common import ok, paginated
from app.schemas.device import DeviceCreate, DeviceOut, DeviceUpdate
from app.services.device_service import DeviceService

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", dependencies=[Depends(require_permission("device:view"))])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=1000),
    room_id: Optional[str] = None,
    rack_id: Optional[str] = None,
    device_type: Optional[DeviceType] = None,
    status_filter: Optional[DeviceStatus] = Query(None, alias="status"),
    keyword: Optional[str] = Query(None, alias="keyword"),
    is_asset: Optional[bool] = Query(None, alias="is_asset"),
):
    svc = DeviceService(db)
    items, total = await svc.list_devices(
        page=page,
        size=size,
        room_id=room_id,
        rack_id=rack_id,
        device_type=device_type.value if device_type else None,
        status=status_filter.value if status_filter else None,
        keyword=keyword,
        is_asset=is_asset,
    )
    return paginated(items, total, page, size)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("device:edit"))],
)
async def create_device(payload: DeviceCreate, db: AsyncSession = Depends(get_db)):
    svc = DeviceService(db)
    device = await svc.create_device(payload)
    return ok(device)


@router.get("/{device_id}", dependencies=[Depends(require_permission("device:view"))])
async def get_device(device_id: str, db: AsyncSession = Depends(get_db)):
    svc = DeviceService(db)
    device = await svc.get_device(device_id)
    return ok(device)


@router.put("/{device_id}", dependencies=[Depends(require_permission("device:edit"))])
async def update_device(
    device_id: str, payload: DeviceUpdate, db: AsyncSession = Depends(get_db)
):
    svc = DeviceService(db)
    device = await svc.update_device(device_id, payload)
    return ok(device)


@router.delete("/{device_id}", dependencies=[Depends(require_permission("device:edit"))])
async def delete_device(device_id: str, db: AsyncSession = Depends(get_db)):
    svc = DeviceService(db)
    await svc.delete_device(device_id)
    return ok()


@router.get("/{device_id}/mount-history", dependencies=[Depends(require_permission("device:view"))])
async def device_mount_history(device_id: str, db: AsyncSession = Depends(get_db)):
    """设备上下架操作流水（上架 / 下架事件，按时间倒序）。"""
    svc = DeviceService(db)
    events = await svc.get_mount_history(device_id)
    return ok(events)
