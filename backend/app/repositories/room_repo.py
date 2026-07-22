"""机房仓储（纯 DB 读写）。"""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RoomStatus
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate


class RoomRepository:
    """机房表的读写操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: RoomCreate) -> Room:
        room = Room(**data.model_dump())
        self.session.add(room)
        await self.session.flush()
        return room

    async def get(self, room_id: str) -> Optional[Room]:
        stmt = select(Room).where(Room.id == room_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many(self, ids: list[str]) -> list[Room]:
        """按 id 批量取机房（设备列表批量预填机房名，避免 N+1）。"""
        if not ids:
            return []
        stmt = select(Room).where(Room.id.in_(ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list(
        self,
        *,
        page: int = 1,
        size: int = 20,
        name: Optional[str] = None,
        area: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[list[Room], int]:
        conditions = []
        if name:
            conditions.append(Room.name.ilike(f"%{name}%"))
        if area:
            conditions.append(Room.area == area)
        if status:
            conditions.append(Room.status == status)
        if keyword:
            kw = f"%{keyword}%"
            conditions.append(
                or_(
                    Room.name.ilike(kw),
                    Room.code.ilike(kw),
                    Room.alias.ilike(kw),
                )
            )
        stmt = select(Room)
        count_stmt = select(func.count()).select_from(Room)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = (
            stmt.order_by(Room.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def update(self, room: Room, data: RoomUpdate) -> Room:
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(room, field, value)
        await self.session.flush()
        return room

    async def list_all(self) -> list[Room]:
        """获取全部机房（统计概览用）。"""
        stmt = select(Room).order_by(Room.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def soft_delete(self, room: Room) -> Room:
        """软删除：状态置为 disabled。"""
        room.status = RoomStatus.DISABLED.value
        await self.session.flush()
        return room
