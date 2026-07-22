"""机房大屏聚合服务。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.repositories.device_repo import DeviceRepository
from app.repositories.rack_repo import RackRepository
from app.repositories.room_repo import RoomRepository
from app.core.enums import calculate_rack_status
from app.schemas.room import (
    DashboardKPI,
    DeviceStatusDistribution,
    RackStatusDistribution,
    RoomDashboard,
    TopologyOverview,
)
from app.services.topology_service import TopologyService


class DashboardService:
    """机房大屏数据聚合：KPI + 状态分布 + 利用率 + 拓扑概览。"""

    def __init__(self, session: AsyncSession, cache: Optional[Cache] = None) -> None:
        self.session = session
        self.cache = cache or Cache()
        self.room_repo = RoomRepository(session)
        self.rack_repo = RackRepository(session)
        self.device_repo = DeviceRepository(session)
        self.topology_service = TopologyService(session, self.cache)

    async def get_room_dashboard(self, room_id: str) -> RoomDashboard:
        """聚合机房大屏数据（先查缓存，未命中再聚合）。详见架构文档 §8。"""
        cache_key = f"dashboard:{room_id}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return RoomDashboard(**cached)

        room = await self.room_repo.get(room_id)
        if room is None:
            raise NotFoundError("机房不存在")

        racks = await self.rack_repo.list_by_room(room_id)
        devices = await self.device_repo.list_by_room(room_id)

        rack_count = len(racks)
        total_u = sum(r.total_u for r in racks)
        used_u = sum(r.used_u for r in racks)
        utilization = round(used_u / total_u * 100, 1) if total_u > 0 else 0.0

        rack_status_dist = RackStatusDistribution()
        for r in racks:
            cap = calculate_rack_status(r.used_u, r.total_u)
            if cap.value == "empty":
                rack_status_dist.empty += 1
            elif cap.value == "partial":
                rack_status_dist.partial += 1
            elif cap.value == "full":
                rack_status_dist.full += 1

        device_status_dist = DeviceStatusDistribution()
        fault_count = 0
        for d in devices:
            if d.status == "running":
                device_status_dist.running += 1
            elif d.status == "offline":
                device_status_dist.offline += 1
            elif d.status == "fault":
                device_status_dist.fault += 1
                fault_count += 1
            elif d.status == "maintenance":
                device_status_dist.maintenance += 1

        topology = await self.topology_service.get_topology(room_id=room_id)
        topology_overview = TopologyOverview(
            node_count=len(topology.nodes),
            edge_count=len(topology.edges),
            active_link_count=len(topology.edges),
        )

        dashboard = RoomDashboard(
            room_id=room.id,
            room_name=room.name,
            kpi=DashboardKPI(
                rack_count=rack_count,
                device_count=len(devices),
                utilization=utilization,
                fault_count=fault_count,
            ),
            rack_status_distribution=rack_status_dist,
            device_status_distribution=device_status_dist,
            utilization=utilization,
            topology_overview=topology_overview,
        )
        await self.cache.set(cache_key, dashboard.model_dump(), ttl=settings.CACHE_TTL)
        return dashboard
