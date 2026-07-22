"""全局统计路由：仪表盘总览页数据接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.rbac import require_any_permission
from app.schemas.common import ok
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get(
    "/overview",
    dependencies=[
        Depends(
            require_any_permission(
                ["room:view", "rack:view", "device:view", "link:view", "account:view"]
            )
        )
    ],
)
async def stats_overview(db: AsyncSession = Depends(get_db)):
    """全局统计概览：机房/机柜/设备规模 + 设备状态分布 + 各机房机柜使用率。"""
    svc = StatsService(db)
    data = await svc.get_overview()
    return ok(data)
