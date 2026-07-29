"""接口路由：设备接口列表/创建/更新/删除/批量生成。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.audit import log_audit
from app.core.audit_diff import build_create_detail, build_update_detail
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
from app.services.device_service import DeviceService
from app.services.interface_service import InterfaceService

router = APIRouter(tags=["interfaces"])

# 接口更新 / 创建审计要记录的字段（中文标签）。
INTERFACE_FIELD_LABELS = {
    "name": "名称",
    "interface_type": "类型",
    "speed": "速率",
    "role": "角色",
    "interface_no": "端口号",
    "ip_address": "IP地址",
}
INTERFACE_CREATE_LABELS = {
    "interface_type": "类型",
    "speed": "速率",
    "role": "角色",
    "interface_no": "端口号",
    "ip_address": "IP地址",
}


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
    device_id: str, payload: InterfaceCreate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = InterfaceService(db)
    iface = await svc.create_interface(device_id, payload)
    device = await DeviceService(db).get_device(device_id)
    detail = build_create_detail(iface, INTERFACE_CREATE_LABELS)
    # 审计对象归到设备：对象列展示设备名，详情列说明创建的接口，便于跳转设备详情。
    await log_audit(request=request, module="interface", action="create", object_type="设备", object_id=device_id, object_name=device.name, detail=detail)
    return ok(InterfaceOut.model_validate(iface))


@router.post(
    "/devices/{device_id}/interfaces/batch",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("device:edit"))],
)
async def batch_create_interfaces(
    device_id: str, payload: InterfaceMultiBatchCreate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = InterfaceService(db)
    device = await DeviceService(db).get_device(device_id)  # 取设备可读名称
    interfaces = await svc.batch_create_interfaces(device_id, payload.groups)
    # 审计对象归到设备，便于跳转设备详情。
    await log_audit(request=request, module="interface", action="create", object_type="设备", object_id=device_id, object_name=device.name, detail=f"批量新增接口 {len(interfaces)} 个")
    return ok([InterfaceOut.model_validate(p) for p in interfaces])


@router.put(
    "/interfaces/{interface_id}",
    dependencies=[Depends(require_permission("device:edit"))],
)
async def update_interface(
    interface_id: str, payload: InterfaceUpdate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = InterfaceService(db)
    before = InterfaceOut.model_validate(await svc.get_interface(interface_id))
    iface = await svc.update_interface(interface_id, payload)
    device = await DeviceService(db).get_device(iface.device_id)
    detail = build_update_detail(before, InterfaceOut.model_validate(iface), INTERFACE_FIELD_LABELS)
    # 审计对象归到设备，便于跳转设备详情。
    await log_audit(request=request, module="interface", action="update", object_type="设备", object_id=iface.device_id, object_name=device.name, detail=detail)
    return ok(InterfaceOut.model_validate(iface))


@router.delete(
    "/interfaces/{interface_id}",
    dependencies=[Depends(require_permission("device:edit"))],
)
async def delete_interface(interface_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    svc = InterfaceService(db)
    iface = await svc.get_interface(interface_id)
    name = iface.name
    device_id = iface.device_id
    device_name = name
    try:
        device = await DeviceService(db).get_device(device_id)
        device_name = device.name
    except Exception:
        pass
    await svc.delete_interface(interface_id)
    # 审计对象归到设备，便于跳转设备详情。
    await log_audit(request=request, module="interface", action="delete", object_type="设备", object_id=device_id, object_name=device_name, detail=f"删除接口「{name}」")
    return ok()
