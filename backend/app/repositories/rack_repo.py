"""机柜仓储（纯 DB 读写）。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rack import Rack
from app.models.room import Room
from app.schemas.rack import RackCreate, RackListItem, RackOut, RackUpdate


class RackRepository:
    """机柜表的读写操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: RackCreate) -> Rack:
        rack = Rack(**data.model_dump())
        self.session.add(rack)
        await self.session.flush()
        return rack

    async def get(self, rack_id: str) -> Optional[Rack]:
        stmt = select(Rack).where(Rack.id == rack_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many(self, ids: list[str]) -> list[Rack]:
        """按 id 批量取机柜（设备列表批量预填机柜名，避免 N+1）。"""
        if not ids:
            return []
        stmt = select(Rack).where(Rack.id.in_(ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_room(self, room_id: str) -> list[Rack]:
        """某机房下全部机柜，按「列编号 → 机柜编号」自然排序。"""
        stmt = (
            select(Rack)
            .where(Rack.room_id == room_id)
            .order_by(Rack.column_code, Rack.code)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[Rack]:
        """获取全部机柜（统计概览用），按「列编号 → 机柜编号」排序。"""
        stmt = select(Rack).order_by(Rack.column_code, Rack.code)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_filtered(
        self,
        *,
        room_id: Optional[str] = None,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 200,
    ) -> tuple[list[RackListItem], int]:
        """机柜管理列表：联表带上机房编号/名称，支持按机房、关键字（名称/编号）、状态过滤，并支持分页。"""
        stmt = select(Rack, Room.code, Room.name).join(Room, Rack.room_id == Room.id)
        count_stmt = select(func.count()).select_from(Rack).join(Room, Rack.room_id == Room.id)
        conditions = []
        if room_id:
            conditions.append(Rack.room_id == room_id)
        if status:
            conditions.append(Rack.status == status)
        if keyword:
            kw = f"%{keyword}%"
            conditions.append(or_(Rack.name.ilike(kw), Rack.code.ilike(kw)))
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(Room.code, Rack.column_code, Rack.code)
        stmt = stmt.offset((page - 1) * size).limit(size)
        rows = (await self.session.execute(stmt)).all()
        items = [
            RackListItem(
                **RackOut.model_validate(r[0]).model_dump(),
                room_code=r[1],
                room_name=r[2],
            )
            for r in rows
        ]
        return items, total

    async def exists_column(
        self, room_id: str, column_code: str, exclude_id: Optional[str] = None
    ) -> bool:
        """同机房内列编号是否已被占用。"""
        stmt = select(Rack.id).where(
            Rack.room_id == room_id, Rack.column_code == column_code
        )
        if exclude_id:
            stmt = stmt.where(Rack.id != exclude_id)
        return (await self.session.execute(stmt)).first() is not None

    async def exists_code(
        self,
        room_id: str,
        column_code: str,
        code: str,
        exclude_id: Optional[str] = None,
    ) -> bool:
        """同机房同列内机柜编号是否已被占用。"""
        stmt = select(Rack.id).where(
            Rack.room_id == room_id,
            Rack.column_code == column_code,
            Rack.code == code,
        )
        if exclude_id:
            stmt = stmt.where(Rack.id != exclude_id)
        return (await self.session.execute(stmt)).first() is not None

    async def update(self, rack: Rack, data: RackUpdate) -> Rack:
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(rack, field, value)
        await self.session.flush()
        return rack

    async def update_positions(self, positions: list[dict]) -> None:
        """批量写入机柜网格坐标（2D 平面图拖拽持久化）。

        positions: [{id, grid_row, grid_col}, ...]
        """
        for p in positions:
            rack = await self.get(p["id"])
            if rack is None:
                continue
            rack.grid_row = p.get("grid_row")
            rack.grid_col = p.get("grid_col")
        await self.session.flush()

    async def delete(self, rack: Rack) -> None:
        await self.session.delete(rack)
        await self.session.flush()

    async def delete_by_room(self, room_id: str) -> None:
        """物理删除指定机房下全部机柜（删除机房前清理，避免孤儿数据）。"""
        await self.session.execute(delete(Rack).where(Rack.room_id == room_id))
        await self.session.flush()
