"""链路路由：列表/创建/更新/删除。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.audit_diff import build_create_detail, build_update_detail
from app.core.deps import get_db
from app.core.rbac import require_permission
from app.schemas.common import ok, paginated
from app.schemas.link import (
    DeviceLinkView,
    LinkCreate,
    LinkDetailOut,
    LinkOut,
    LinkUpdate,
)
from app.services.link_service import LinkService

router = APIRouter(prefix="/links", tags=["links"])

# 更新审计要记录的字段（中文标签）。
LINK_FIELD_LABELS = {
    "remark": "备注",
    "medium": "介质",
    "connector_type": "连接器类型",
    "cable_length": "线长",
}


@router.get("", dependencies=[Depends(require_permission("link:view"))])
async def list_links(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=1000),
    room_id: Optional[str] = None,
    rack_id: Optional[str] = None,
    keyword: Optional[str] = Query(None, alias="keyword"),
    medium: Optional[str] = Query(None, alias="medium"),
    connector_type: Optional[str] = Query(None, alias="connector_type"),
):
    svc = LinkService(db)
    # 返回联表详情（含本端/对端设备名与端口名），便于列表直接展示。
    items, total = await svc.list_links_detailed(
        room_id=room_id,
        rack_id=rack_id,
        keyword=keyword,
        medium=medium,
        connector_type=connector_type,
        page=page,
        size=size,
    )
    return paginated([LinkDetailOut.model_validate(i) for i in items], total, page, size)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("link:edit"))],
)
async def create_link(payload: LinkCreate, request: Request, db: AsyncSession = Depends(get_db)):
    svc = LinkService(db)
    link = await svc.create_link(payload)
    # 富化详情：解析本端 / 对端可读名称 + 介质 / 连接器 / 线长。
    src_device_id = None
    src_device_name = None
    src = None
    dst = None
    try:
        d = await svc.get_link_by_interface(link.source_interface_id)
        if d:
            src_device_id = d.source_device_id
            src_device_name = d.source_device_name
            src = f"{d.source_device_name} / {d.source_interface_name}"
            if d.target_device_name:
                dst = f"{d.target_device_name}{(' / ' + d.target_interface_name) if d.target_interface_name else ''}"
            else:
                dst = d.target_external or "外部位置"
    except Exception:
        pass
    extras = f"介质 {link.medium}"
    if link.connector_type:
        extras += f"，连接器 {link.connector_type}"
    if link.cable_length:
        extras += f"，线长 {link.cable_length}"
    detail = f"连接 {src} → {dst}（{extras}）" if src else f"新建链路（{extras}）"
    # 审计对象归到设备：对象列展示本端设备名，详情列说明创建的链路，便于跳转设备详情。
    await log_audit(
        request=request,
        module="link",
        action="create",
        object_type="设备",
        object_id=src_device_id,
        object_name=src_device_name,
        detail=detail,
    )
    return ok(LinkOut.model_validate(link))


@router.get("/by-interface/{interface_id}", dependencies=[Depends(require_permission("link:view"))])
async def link_by_interface(
    interface_id: str, db: AsyncSession = Depends(get_db)
):
    """查询某接口当前所在的 active 链路详情（无则 null）。"""
    svc = LinkService(db)
    detail = await svc.get_link_by_interface(interface_id)
    return ok(detail.model_dump() if detail else None)


@router.put("/{link_id}", dependencies=[Depends(require_permission("link:edit"))])
async def update_link(
    link_id: str, payload: LinkUpdate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = LinkService(db)
    before = LinkOut.model_validate(await svc.get_link(link_id))
    link = await svc.update_link(link_id, payload)
    # 解析本端设备，使审计对象可点击跳转至设备详情。
    device_id = None
    device_name = None
    try:
        d = await svc.get_link_by_interface(before.source_interface_id)
        if d:
            device_id = d.source_device_id
            device_name = d.source_device_name
    except Exception:
        pass
    detail = build_update_detail(before, LinkOut.model_validate(link), LINK_FIELD_LABELS)
    await log_audit(
        request=request,
        module="link",
        action="update",
        object_type="设备",
        object_id=device_id,
        object_name=device_name,
        detail=detail,
    )
    return ok(LinkOut.model_validate(link))


@router.get("/by-device/{device_id}", dependencies=[Depends(require_permission("link:view"))])
async def links_by_device(
    device_id: str, db: AsyncSession = Depends(get_db)
):
    """查询某设备作为本端或对端的全部链路（设备视角，含对端信息）。"""
    svc = LinkService(db)
    items = await svc.list_links_by_device(device_id)
    return ok([i.model_dump() for i in items])


@router.delete("/{link_id}", dependencies=[Depends(require_permission("link:edit"))])
async def delete_link(link_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    svc = LinkService(db)
    link = await svc.get_link(link_id)
    name = link.remark or f"链路 {link.id[:8]}"
    # 解析本端设备，使审计对象可点击跳转至设备详情。
    device_id = None
    device_name = None
    try:
        d = await svc.get_link_by_interface(link.source_interface_id)
        if d:
            device_id = d.source_device_id
            device_name = d.source_device_name
    except Exception:
        pass
    await svc.delete_link(link_id)
    await log_audit(request=request, module="link", action="delete", object_type="设备", object_id=device_id, object_name=device_name, detail=f"删除链路「{name}」（介质 {link.medium}）")
    return ok()
