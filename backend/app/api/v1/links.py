"""链路路由：列表/创建/更新/删除。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.rbac import require_permission
from app.schemas.common import ok, paginated
from app.schemas.link import (
    LinkCreate,
    LinkDetailOut,
    LinkOut,
    LinkUpdate,
)
from app.services.link_service import LinkService

router = APIRouter(prefix="/links", tags=["links"])


@router.get("", dependencies=[Depends(require_permission("link:view"))])
async def list_links(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=1000),
    room_id: Optional[str] = None,
    rack_id: Optional[str] = None,
    keyword: Optional[str] = Query(None, alias="keyword"),
):
    svc = LinkService(db)
    # 返回联表详情（含本端/对端设备名与端口名），便于列表直接展示。
    items, total = await svc.list_links_detailed(
        room_id=room_id,
        rack_id=rack_id,
        keyword=keyword,
        page=page,
        size=size,
    )
    return paginated([LinkDetailOut.model_validate(i) for i in items], total, page, size)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("link:edit"))],
)
async def create_link(payload: LinkCreate, db: AsyncSession = Depends(get_db)):
    svc = LinkService(db)
    link = await svc.create_link(payload)
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
    link_id: str, payload: LinkUpdate, db: AsyncSession = Depends(get_db)
):
    svc = LinkService(db)
    link = await svc.update_link(link_id, payload)
    return ok(LinkOut.model_validate(link))


@router.delete("/{link_id}", dependencies=[Depends(require_permission("link:edit"))])
async def delete_link(link_id: str, db: AsyncSession = Depends(get_db)):
    svc = LinkService(db)
    await svc.delete_link(link_id)
    return ok()
