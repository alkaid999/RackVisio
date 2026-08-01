"""机房大屏聚合服务。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.repositories.device_repo import DeviceRepository
from app.repositories.rack_repo import RackRepository
from app.repositories.room_repo import RoomRepository
from app.core.enums import DeviceStatus, MountRecordStatus, RackStatus, calculate_rack_status
from app.models.device import Device
from app.models.mount_record import MountRecord
from app.schemas.room import (
    DashboardKPI,
    DeviceStatusDistribution,
    RackStatusDistribution,
    RoomDashboard,
)


class DashboardService:
    """机房大屏数据聚合：KPI + 状态分布 + 利用率。"""

    def __init__(self, session: AsyncSession, cache: Optional[Cache] = None) -> None:
        self.session = session
        self.cache = cache or Cache()
        self.room_repo = RoomRepository(session)
        self.rack_repo = RackRepository(session)
        self.device_repo = DeviceRepository(session)

    async def get_room_dashboard(self, room_id: str) -> RoomDashboard:
        """聚合机房大屏数据（先查缓存，未命中再聚合）。详见架构文档 §8。"""
        cache_key = f"dashboard:{room_id}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            try:
                return RoomDashboard(**cached)
            except Exception:
                # 缓存结构变更或脏数据：丢弃并回源重算，避免脏缓存导致 500。
                pass

        room = await self.room_repo.get(room_id)
        if room is None:
            raise NotFoundError("机房不存在")

        racks = await self.rack_repo.list_by_room(room_id)
        # P-06：设备状态分布改 DB 端 GROUP BY——经有效上架记录关联该机房设备，
        # 一次聚合替代「全量加载设备到内存逐条统计」（设备密集机房内存占用显著下降）。
        status_rows = (
            await self.session.execute(
                select(Device.status, func.count())
                .select_from(MountRecord)
                .join(Device, Device.id == MountRecord.device_id)
                .where(
                    MountRecord.room_id == room_id,
                    MountRecord.record_status == MountRecordStatus.ACTIVE.value,
                )
                .group_by(Device.status)
            )
        ).all()
        status_counts: dict[str, int] = {s.value: 0 for s in DeviceStatus}
        for st, c in status_rows:
            if st in status_counts:
                status_counts[st] = c

        rack_count = len(racks)
        total_u = sum(r.total_u for r in racks)
        used_u = sum(r.used_u for r in racks)
        utilization = round(used_u / total_u * 100, 1) if total_u > 0 else 0.0

        rack_status_dist = RackStatusDistribution()
        for r in racks:
            cap = calculate_rack_status(r.used_u, r.total_u)
            if cap == RackStatus.EMPTY:
                rack_status_dist.empty += 1
            elif cap == RackStatus.PARTIAL:
                rack_status_dist.partial += 1
            elif cap == RackStatus.FULL:
                rack_status_dist.full += 1

        device_status_dist = DeviceStatusDistribution(
            in_stock=status_counts.get(DeviceStatus.IN_STOCK.value, 0),
            mounted=status_counts.get(DeviceStatus.MOUNTED.value, 0),
            unmounted=status_counts.get(DeviceStatus.UNMOUNTED.value, 0),
            scrapped=status_counts.get(DeviceStatus.SCRAPPED.value, 0),
            lent=status_counts.get(DeviceStatus.LENT.value, 0),
        )
        device_count = sum(status_counts.values())

        dashboard = RoomDashboard(
            room_id=room.id,
            room_name=room.name,
            kpi=DashboardKPI(
                rack_count=rack_count,
                device_count=device_count,
                utilization=utilization,
            ),
            rack_status_distribution=rack_status_dist,
            device_status_distribution=device_status_dist,
            utilization=utilization,
        )
        await self.cache.set(cache_key, dashboard.model_dump(mode="json"), ttl=settings.CACHE_TTL)
        return dashboard
