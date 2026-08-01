"""全局统计概览服务（仪表盘总览页）。

聚合机房 / 机柜 / 设备三张表，实时反映各模块最新状态。
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select
from app.core.cache import cache
from app.core.database import async_session_factory
from app.core.enums import RoomStatus
from app.core.meta import DEVICE_STATUS_META, DEVICE_TYPE_META
from app.models.device import Device
from app.models.rack import Rack
from app.models.room import Room
from app.repositories.device_repo import DeviceRepository
from app.repositories.rack_repo import RackRepository
from app.repositories.room_repo import RoomRepository
from app.repositories.link_repo import LinkRepository
from app.repositories.user_repo import UserRepository
from app.repositories.mount_record_repo import MountRecordRepository
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
        """聚合全局统计。DB 端聚合 + 30s 进程内缓存（P1：避免全表拉取内存计算）。

        P-03：规模指标 4 个 COUNT 合并为单条 SQL；其余无依赖的分布/聚合用
        ``asyncio.gather`` + 独立会话并行执行（SQLAlchemy AsyncSession 不支持
        同一会话并发操作，故每个并行任务开独立会话），串行 ~12 次往返 →
        1 次 + 6 路并行。
        """
        cache_key = "dashboard:overview"
        cached = await cache.get(cache_key)
        if cached is not None:
            return StatsOverview(**cached)

        session = self.session

        # —— 规模指标（4 个 COUNT 合并为单条多列 SQL，1 次往返）——
        # scalar_subquery 生成 (SELECT count(*) ...) 子查询列，SQLite / PG 通吃。
        counts = (
            await session.execute(
                select(
                    select(func.count())
                    .select_from(Room)
                    .where(Room.status == RoomStatus.ACTIVE.value)
                    .scalar_subquery(),
                    select(func.count()).select_from(Rack).scalar_subquery(),
                    select(func.count())
                    .select_from(Device)
                    .where(Device.is_asset.is_(True))
                    .scalar_subquery(),
                    select(func.count())
                    .select_from(Device)
                    .where(Device.is_asset.is_(False))
                    .scalar_subquery(),
                )
            )
        ).one()
        room_count, rack_count, device_count, facility_count = (int(c or 0) for c in counts)

        # —— 并行组：无依赖的分布 / 聚合各自开独立会话执行 ——
        # A-04：聚合查询下沉到各 Repository 统计方法（不再绕过 repo 裸写 SQL），
        # 并行时用新会话实例化 repo；P-03 的并行策略保持不变。
        async def _status_dist(s):
            """设备状态分布（GROUP BY status，仅资产）。"""
            return await DeviceRepository(s).count_by_status(is_asset=True)

        async def _capacity_and_rooms(s):
            """各机房机柜容量（GROUP BY room_id）+ 机房名映射（一次任务带回）。"""
            return (
                await RoomRepository(s).id_name_map(),
                await RackRepository(s).aggregate_capacity(),
            )

        async def _type_dist(s):
            """设备类型分布（GROUP BY device_type，仅资产）。"""
            return await DeviceRepository(s).count_by_type(is_asset=True)

        async def _power(s):
            """功率预算：额定 = Σ 机柜 design_power；已用 = Σ 有效上架设备 rated_power。"""
            return (
                await RackRepository(s).sum_design_power(),
                await MountRecordRepository(s).sum_rated_power_active(),
            )

        async def _consumables(s):
            """耗材规模（类型 COUNT + 条目 count_all，独立会话）。"""
            type_count = await ConsumableTypeRepository(s).count()
            item_count, total_quantity = await ConsumableItemRepository(s).count_all()
            return type_count, item_count, total_quantity

        async def _links_users(s):
            """链路 / 账号规模（repo count_all，独立会话）。"""
            return (
                await LinkRepository(s).count_all(),
                await UserRepository(s).count_all(),
            )

        async def _run(fn):
            async with async_session_factory() as s:
                return await fn(s)

        (
            status_rows,
            (room_name_map, cap_rows),
            type_rows,
            (power_rated, power_used),
            (consumable_type_count, consumable_item_count, consumable_total_quantity),
            (link_count, account_count),
        ) = await asyncio.gather(
            _run(_status_dist),
            _run(_capacity_and_rooms),
            _run(_type_dist),
            _run(_power),
            _run(_consumables),
            _run(_links_users),
        )

        # —— 组装（纯内存计算，无 DB 往返）——
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

        type_counts = {t or "other": c for t, c in type_rows}
        device_type_distribution = [
            DeviceTypeCount(type=t, label=DEVICE_TYPE_LABELS.get(t, t), count=c)
            for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
        ]

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
            power_rated=power_rated,
            power_used=power_used,
        )
        await cache.set(cache_key, result.model_dump())
        return result
