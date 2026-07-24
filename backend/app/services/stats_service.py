"""全局统计概览服务（仪表盘总览页）。

聚合机房 / 机柜 / 设备三张表，实时反映各模块最新状态。
"""

from __future__ import annotations

from sqlalchemy import func, select
from app.core.cache import cache
from app.core.meta import DEVICE_STATUS_META, DEVICE_TYPE_META
from app.models.device import Device
from app.models.rack import Rack
from app.models.room import Room
from app.repositories.device_repo import DeviceRepository
from app.repositories.rack_repo import RackRepository
from app.repositories.room_repo import RoomRepository
from app.repositories.link_repo import LinkRepository
from app.repositories.user_repo import UserRepository
from app.repositories.consumable_repo import (
    ConsumableTypeRepository,
    ConsumableItemRepository,
)
from app.schemas.stats import (
    DeviceStatusCount,
    RoomRackCapacity,
    DeviceTypeCount,
    StatsOverview,
)

# 设备状态展示顺序与中文标签（单一来源见 app.core.meta）。
# 下游聚合逻辑依赖「所有合法状态 → 0」的初值字典，故此处展开为值→标签映射。
DEVICE_STATUS_LABELS = {k: v["label"] for k, v in DEVICE_STATUS_META.items()}

# 设备类型中文标签（单一来源见 app.core.meta）。
DEVICE_TYPE_LABELS = {k: v["label"] for k, v in DEVICE_TYPE_META.items()}


class StatsService:
    """全局统计聚合：规模指标 + 设备状态分布 + 各机房机柜容量。"""

    def __init__(self, session) -> None:
        self.session = session
        self.room_repo = RoomRepository(session)
        self.rack_repo = RackRepository(session)
        self.device_repo = DeviceRepository(session)
        self.link_repo = LinkRepository(session)
        self.user_repo = UserRepository(session)
        self.consumable_type_repo = ConsumableTypeRepository(session)
        self.consumable_item_repo = ConsumableItemRepository(session)

    async def get_overview(self) -> StatsOverview:
        """聚合全局统计。DB 端聚合 + 30s 进程内缓存（P1：避免全表拉取内存计算）。"""
        cache_key = "dashboard:overview"
        cached = await cache.get(cache_key)
        if cached is not None:
            return StatsOverview(**cached)

        session = self.session

        # 规模指标（DB 端 COUNT，按需加 WHERE）。
        room_count = int(
            (await session.execute(
                select(func.count()).select_from(Room).where(Room.status == "active")
            )).scalar() or 0
        )
        rack_count = int(
            (await session.execute(select(func.count()).select_from(Rack))).scalar() or 0
        )
        device_count = int(
            (await session.execute(
                select(func.count()).select_from(Device).where(Device.is_asset.is_(True))
            )).scalar() or 0
        )
        # 设施（非资产）单独计数：占 U 位但不进资产统计。
        facility_count = int(
            (await session.execute(
                select(func.count()).select_from(Device).where(Device.is_asset.is_(False))
            )).scalar() or 0
        )

        # 设备状态分布（GROUP BY status，仅资产；设施不进资产统计）。
        status_rows = (
            await session.execute(
                select(Device.status, func.count())
                .where(Device.is_asset.is_(True))
                .group_by(Device.status)
            )
        ).all()
        status_counts: dict[str, int] = {s: 0 for s in DEVICE_STATUS_LABELS}
        for s, c in status_rows:
            if s in status_counts:
                status_counts[s] = c
            else:
                status_counts[s] = status_counts.get(s, 0) + c
        device_status = [
            DeviceStatusCount(status=s, label=DEVICE_STATUS_LABELS.get(s, s), count=c)
            for s, c in status_counts.items()
        ]

        # 各机房机柜容量（GROUP BY room_id，汇总 total_u / used_u / 机柜数）。
        room_name_map = {r.id: r.name for r in (await self.room_repo.list_all())}
        cap_rows = (
            await session.execute(
                select(
                    Rack.room_id,
                    func.count(Rack.id),
                    func.coalesce(func.sum(Rack.total_u), 0),
                    func.coalesce(func.sum(Rack.used_u), 0),
                ).group_by(Rack.room_id)
            )
        ).all()
        rack_capacity_by_room: list[RoomRackCapacity] = []
        overall_total_u = 0
        overall_used_u = 0
        for room_id, rc, total_u, used_u in cap_rows:
            total_u = int(total_u or 0)
            used_u = int(used_u or 0)
            overall_total_u += total_u
            overall_used_u += used_u
            utilization = round(used_u / total_u * 100, 1) if total_u > 0 else 0.0
            # room_id 为 NULL（未分配机房的机柜）归入「未分配」分组，
            # 避免矩形树图出现无名方块（修复审查报告逻辑#2）。
            room_name = "未分配" if room_id is None else room_name_map.get(room_id, "未分配")
            rack_capacity_by_room.append(
                RoomRackCapacity(
                    room_id=room_id,
                    room_name=room_name,
                    rack_count=rc,
                    total_u=total_u,
                    used_u=used_u,
                    utilization=utilization,
                )
            )
        rack_capacity_by_room.sort(key=lambda x: x.room_name)
        overall_utilization = (
            round(overall_used_u / overall_total_u * 100, 1)
            if overall_total_u > 0
            else 0.0
        )

        # 设备类型分布（GROUP BY device_type，降序，仅资产；设施不进资产统计）。
        type_rows = (
            await session.execute(
                select(Device.device_type, func.count())
                .where(Device.is_asset.is_(True))
                .group_by(Device.device_type)
            )
        ).all()
        type_counts = {t or "other": c for t, c in type_rows}
        device_type_distribution = [
            DeviceTypeCount(type=t, label=DEVICE_TYPE_LABELS.get(t, t), count=c)
            for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
        ]

        # 链路 / 账号 / 耗材规模（只读聚合，低成本）。
        link_count = len(await self.link_repo.list_all())
        account_count = await self.user_repo.count_all()
        consumable_type_count = len(await self.consumable_type_repo.list())
        consumable_item_count, consumable_total_quantity = (
            await self.consumable_item_repo.count_all()
        )

        result = StatsOverview(
            room_count=room_count,
            rack_count=rack_count,
            device_count=device_count,
            facility_count=facility_count,
            device_status=device_status,
            rack_capacity_by_room=rack_capacity_by_room,
            total_u=overall_total_u,
            used_u=overall_used_u,
            overall_utilization=overall_utilization,
            link_count=link_count,
            account_count=account_count,
            consumable_type_count=consumable_type_count,
            consumable_item_count=consumable_item_count,
            consumable_total_quantity=consumable_total_quantity,
            device_type_distribution=device_type_distribution,
        )
        await cache.set(cache_key, result.model_dump())
        return result
