"""机房业务逻辑。

面向政企 / IDC 租用场景：机房以「编号」全局唯一标识，记录别名、区域、楼宇、楼层、
地址等。移除原机房等级(category) 与网格(rows/cols)/平面图(floor-plan) 耦合逻辑。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.cache import Cache
from app.core.enums import RoomStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.room import Room
from app.repositories.mount_record_repo import MountRecordRepository
from app.repositories.rack_repo import RackRepository
from app.repositories.room_repo import RoomRepository
from app.schemas.room import RoomCreate, RoomStats, RoomUpdate


class RoomService:
    """机房相关业务逻辑：CRUD / 容量统计。"""

    def __init__(self, session: AsyncSession, cache: Optional[Cache] = None) -> None:
        self.session = session
        self.cache = cache or Cache()
        self.room_repo = RoomRepository(session)
        self.rack_repo = RackRepository(session)
        self.mount_repo = MountRecordRepository(session)

    async def create_room(self, data: RoomCreate) -> Room:
        try:
            room = await self.room_repo.create(data)
            await self.session.commit()
            await self.session.refresh(room)
            return room
        except IntegrityError:
            await self.session.rollback()
            raise ConflictError(f"机房编号 {data.code} 已存在")

    async def get_room(self, room_id: str) -> Room:
        room = await self.room_repo.get(room_id)
        if room is None:
            raise NotFoundError("机房不存在")
        return room

    async def list_rooms(
        self,
        *,
        page: int = 1,
        size: int = 20,
        name: Optional[str] = None,
        area: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ):
        return await self.room_repo.list(
            page=page, size=size, name=name, area=area, status=status, keyword=keyword
        )

    async def update_room(self, room_id: str, data: RoomUpdate) -> Room:
        room = await self.get_room(room_id)
        if data.status is not None:
            try:
                RoomStatus(data.status)
            except ValueError:
                raise ValidationError(f"无效的机房状态：{data.status}（应为 active / disabled）")
        try:
            room = await self.room_repo.update(room, data)
            await self.session.commit()
            await self.session.refresh(room)
            return room
        except IntegrityError:
            await self.session.rollback()
            raise ConflictError(f"机房编号 {data.code} 已存在")

    async def delete_room(self, room_id: str) -> None:
        """物理删除机房。

        删除前校验：若机房内仍有「有效上架设备」（经机柜关联），禁止删除，
        需先将这些设备下架。空机柜（无上架设备）允许存在、并随机房一并删除。
        删除顺序：先清上架记录、再清机柜、最后删机房，避免外键孤儿数据
        （设备位置经 mount_records 关联，无设备表直连字段；SQLite 未启用 FK 级联，
        PostgreSQL 会强制外键，故必须显式按 room_id 清理子表）。
        """
        room = await self.get_room(room_id)
        device_ids = await self.mount_repo.list_device_ids_by_room(room_id)
        if device_ids:
            raise ConflictError(
                f"机房内还有 {len(device_ids)} 台已上架设备，无法删除。请先将这些设备下架后再删除机房。"
            )
        # 清理顺序：上架记录 → 机柜 → 机房（均按 room_id 显式 bulk 删除，
        # 避免 session.delete(room) 触发 Room→Rack 级联而重复删机柜产生告警）。
        await self.mount_repo.delete_by_room(room_id)
        await self.rack_repo.delete_by_room(room_id)
        await self.room_repo.delete_by_id(room_id)
        await self.session.commit()
        await self.cache.delete_prefix(f"room_stats:{room_id}")
        await self.cache.delete_prefix(f"dashboard:{room_id}")

    async def get_stats(self, room_id: str) -> RoomStats:
        """机房容量统计（带缓存）。"""
        await self.get_room(room_id)  # 校验存在
        cache_key = f"room_stats:{room_id}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return RoomStats(**cached)
        racks = await self.rack_repo.list_by_room(room_id)
        rack_count = len(racks)
        total_u = sum(r.total_u for r in racks)
        used_u = sum(r.used_u for r in racks)
        utilization = round(used_u / total_u * 100, 1) if total_u > 0 else 0.0
        stats = RoomStats(
            rack_count=rack_count, total_u=total_u, used_u=used_u, utilization=utilization
        )
        await self.cache.set(cache_key, stats.model_dump(), ttl=30)
        return stats
