"""拓扑路由：/topology 与 /topology/device/{id}。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.rbac import require_any_permission
from app.schemas.common import ok
from app.services.topology_service import TopologyService

router = APIRouter(prefix="/topology", tags=["topology"])


_ANY_VIEW = ["room:view", "rack:view", "device:view", "link:view"]


@router.get("", dependencies=[Depends(require_any_permission(_ANY_VIEW))])
async def get_topology(
    db: AsyncSession = Depends(get_db),
    room_id: Optional[str] = None,
    rack_id: Optional[str] = None,
    device_id: Optional[str] = None,
):
    svc = TopologyService(db)
    data = await svc.get_topology(
        room_id=room_id, rack_id=rack_id, device_id=device_id
    )
    return ok(data)


@router.get("/device/{device_id}", dependencies=[Depends(require_any_permission(_ANY_VIEW))])
async def get_device_topology(device_id: str, db: AsyncSession = Depends(get_db)):
    svc = TopologyService(db)
    data = await svc.get_device_topology(device_id)
    return ok(data)
