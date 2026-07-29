"""设备路由：列表/创建/详情/更新/删除。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.audit_diff import build_create_detail, build_update_detail
from app.core.deps import get_db
from app.core.enums import DeviceStatus, DeviceType
from app.core.rbac import require_permission
from app.schemas.common import ImportResult, ok, paginated
from app.schemas.device import DeviceCreate, DeviceImportRowsRequest, DeviceOut, DeviceUpdate
from app.services.device_service import DeviceService

router = APIRouter(prefix="/devices", tags=["devices"])

# 设备可编辑字段 -> 审计明细中文标签（仅这些字段参与「更新前后」diff）。
DEVICE_FIELD_LABELS: dict[str, str] = {
    "device_code": "设备编号",
    "name": "名称",
    "device_type": "类型",
    "u_height": "U数",
    "model": "型号",
    "sn": "序列号",
    "ip_address": "业务IP地址",
    "oob_ip": "带外管理IP",
    "warranty_expire": "保修到期",
    "remark": "备注",
    "rated_power": "额定功率",
    "status": "状态",
    "power_status": "电源状态",
    "is_asset": "计入资产",
}

# 创建审计要罗列的初始关键属性（中文标签）。名称为对象名已展示，此处不再重复。
DEVICE_CREATE_LABELS = {
    "device_code": "编号",
    "device_type": "类型",
    "model": "型号",
    "ip_address": "业务IP地址",
    "oob_ip": "带外管理IP",
    "u_height": "U数",
    "status": "状态",
}


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
async def create_device(payload: DeviceCreate, request: Request, db: AsyncSession = Depends(get_db)):
    svc = DeviceService(db)
    device = await svc.create_device(payload)
    detail = build_create_detail(device, DEVICE_CREATE_LABELS)
    await log_audit(request=request, module="device", action="create", object_type="设备", object_id=device.id, object_name=device.name or device.device_code, detail=detail)
    return ok(device)


@router.get("/export", dependencies=[Depends(require_permission("device:view"))])
async def export_devices(
    request: Request,
    db: AsyncSession = Depends(get_db),
    room_id: Optional[str] = None,
    rack_id: Optional[str] = None,
    device_type: Optional[DeviceType] = None,
    status_filter: Optional[DeviceStatus] = Query(None, alias="status"),
    keyword: Optional[str] = Query(None, alias="keyword"),
    is_asset: Optional[bool] = Query(None, alias="is_asset"),
):
    """按当前筛选条件导出全部设备（不分页）。返回行数组，由前端落地为文件。"""
    svc = DeviceService(db)
    items, _ = await svc.list_devices(
        page=1,
        size=100000,
        room_id=room_id,
        rack_id=rack_id,
        device_type=device_type.value if device_type else None,
        status=status_filter.value if status_filter else None,
        keyword=keyword,
        is_asset=is_asset,
    )
    await log_audit(request=request, module="device", action="export", object_type="设备", detail=f"导出设备 {len(items)} 条")
    return ok([d.model_dump() for d in items])


@router.post("/import", dependencies=[Depends(require_permission("device:edit"))])
async def import_devices(
    payload: DeviceImportRowsRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """批量导入设备：前端解析文件为 JSON 行后提交，后端逐行校验并创建。

    必须在 ``/{device_id}`` 路由之前注册，避免被其路径模板拦截。
    """
    svc = DeviceService(db)
    result = await svc.import_devices(payload.items)
    await log_audit(request=request, module="device", action="import", object_type="设备", detail=f"导入设备：成功 {result.created} 条，失败 {result.failed} 条")
    return ok(ImportResult.model_validate(result))


@router.get("/{device_id}", dependencies=[Depends(require_permission("device:view"))])
async def get_device(device_id: str, db: AsyncSession = Depends(get_db)):
    svc = DeviceService(db)
    device = await svc.get_device(device_id)
    return ok(device)


@router.put("/{device_id}", dependencies=[Depends(require_permission("device:edit"))])
async def update_device(
    device_id: str, payload: DeviceUpdate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = DeviceService(db)
    before = await svc.get_device(device_id)
    device = await svc.update_device(device_id, payload)
    detail = build_update_detail(before, device, DEVICE_FIELD_LABELS)
    await log_audit(request=request, module="device", action="update", object_type="设备", object_id=device.id, object_name=device.name or device.device_code, detail=detail)
    return ok(device)


@router.delete("/{device_id}", dependencies=[Depends(require_permission("device:edit"))])
async def delete_device(device_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    svc = DeviceService(db)
    device = await svc.get_device(device_id)
    name = device.name or device.device_code
    await svc.delete_device(device_id)
    await log_audit(request=request, module="device", action="delete", object_type="设备", object_id=device_id, object_name=name, detail=f"删除设备「{name}」")
    return ok()


@router.get("/{device_id}/mount-history", dependencies=[Depends(require_permission("device:view"))])
async def device_mount_history(device_id: str, db: AsyncSession = Depends(get_db)):
    """设备上下架操作流水（上架 / 下架事件，按时间倒序）。"""
    svc = DeviceService(db)
    events = await svc.get_mount_history(device_id)
    return ok(events)
