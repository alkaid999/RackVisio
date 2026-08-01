"""机柜 used_u 重算与机房缓存失效共享逻辑。

独立于 ``RackService`` / ``DeviceService``（A-02 解耦）：两个服务都需要「重算机柜
used_u + 失效机房相关缓存」，若互相顶部 import 会形成循环依赖（device_service 曾用
方法内懒加载规避，架构不干净）。抽成**无服务依赖的模块级函数**，任何服务按需调用：

- ``recalculate_rack_usage``：按有效上架记录 occupied_u 求和更新机柜 used_u，
  提交后失效机房相关缓存（与 RackService 原实现同语义）。
- ``invalidate_room_caches``：机房 / 机柜 / 设备相关缓存前缀统一失效（幂等、失败静默）。
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache

logger = logging.getLogger(__name__)

# 机房维度缓存前缀（room_stats / dashboard / racks:layout）。
_ROOM_PREFIXES = ("room_stats:", "dashboard:", "racks:layout:")
# 全局列表缓存前缀（机柜列表 / 设备列表——上架下架与设备变更会同时影响两者）。
_GLOBAL_PREFIXES = ("racks:list:", "devices:list:")


async def invalidate_room_caches(cache: Cache, room_id: str) -> None:
    """失效机房相关全部缓存前缀（幂等、非关键，失败静默不阻塞业务）。"""
    try:
        for prefix in _ROOM_PREFIXES:
            await cache.delete_prefix(f"{prefix}{room_id}")
        for prefix in _GLOBAL_PREFIXES:
            await cache.delete_prefix(prefix)
    except Exception:
        logger.warning("机房缓存失效失败（已忽略）", exc_info=True)


async def recalculate_rack_usage(
    session: AsyncSession,
    mount_repo,
    rack_repo,
    cache: Cache,
    rack_id: str,
) -> None:
    """重算机柜 used_u（按有效上架记录 occupied_u 求和）并失效机房缓存。

    供 RackService（上架/下架后）与 DeviceService（改设备 U 数/删记录后）共用，
    保证两处派生口径完全一致（A-02）。
    """
    rack = await rack_repo.get(rack_id)
    if rack is None:
        return
    total_used = await mount_repo.sum_occupied_u_in_rack(rack_id)
    rack.used_u = total_used
    await session.flush()
    await session.commit()
    if rack.room_id:
        await invalidate_room_caches(cache, rack.room_id)
