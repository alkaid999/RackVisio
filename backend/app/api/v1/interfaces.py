"""接口路由：设备接口列表/创建/更新/删除/批量生成。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.deps import get_db
from app.core.rbac import require_permission
from app.schemas.common import ok, paginated
from app.schemas.interface import (
    InterfaceBatchCreate,
    InterfaceCreate,
    InterfaceMultiBatchCreate,
    InterfaceOut,
    InterfaceUpdate,
    UnlinkedInterfaceOut,
)
from app.services.interface_service import InterfaceService

router = APIRouter(tags=["interfaces"])


@router.get("/interfaces", dependencies=[Depends(require_permission("device:view"))])
async def list_all_interfaces(
    page: int = 1,
    size: int = 50,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """全局接口面板：分页返回所有设备的接口（含所属设备名）。"""
    svc = InterfaceService(db)
    items, total = await svc.list_interfaces_global(page, size, keyword)
    return paginated(items, total, page, size)


@router.get("/devices/{device_id}/interfaces", dependencies=[Depends(require_permission("device:view"))])
async def list_interfaces(device_id: str, db: AsyncSession = Depends(get_db)):
    svc = InterfaceService(db)
    interfaces = await svc.list_interfaces(device_id)
    return ok([InterfaceOut.model_validate(p) for p in interfaces])


@router.get("/interfaces/unlinked", dependencies=[Depends(require_permission("device:view"))])
async def list_unlinked_interfaces(db: AsyncSession = Depends(get_db)):
    """未连接链路（孤儿口）的接口列表，用于连接总览补全布线全景。"""
    svc = InterfaceService(db)
    items = await svc.list_unlinked_interfaces()
    return ok([i.model_dump() for i in items])


@router.post(
    "/devices/{device_id}/interfaces",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("device:edit"))],
)
async def create_interface(
    device_id: str, payload: InterfaceCreate, db: AsyncSession = Depends(get_db)
):
    svc = InterfaceService(db)
    iface = await svc.create_interface(device_id, payload)
    return ok(InterfaceOut.model_validate(iface))


@router.post(
    "/devices/{device_id}/interfaces/batch",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("device:edit"))],
)
async def batch_create_interfaces(
    device_id: str, payload: InterfaceMultiBatchCreate, db: AsyncSession = Depends(get_db)
):
    svc = InterfaceService(db)
    interfaces = await svc.batch_create_interfaces(device_id, payload.groups)
    return ok([InterfaceOut.model_validate(p) for p in interfaces])


@router.put(
    "/interfaces/{interface_id}",
    dependencies=[Depends(require_permission("device:edit"))],
)
async def update_interface(
    interface_id: str, payload: InterfaceUpdate, db: AsyncSession = Depends(get_db)
):
    svc = InterfaceService(db)
    iface = await svc.update_interface(interface_id, payload)
    return ok(InterfaceOut.model_validate(iface))


@router.delete(
    "/interfaces/{interface_id}",
    dependencies=[Depends(require_permission("device:edit"))],
)
async def delete_interface(interface_id: str, db: AsyncSession = Depends(get_db)):
    svc = InterfaceService(db)
    await svc.delete_interface(interface_id)
    return ok()
