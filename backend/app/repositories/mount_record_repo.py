"""上架记录仓储（纯 DB 读写）。

集中管理设备 ↔ 机柜位置关联的查询，是「设备表不含位置字段」设计的核心支撑：
- 设备当前位置 = 本表 ``record_status='有效'`` 的最新一条记录。
- 机柜 used_u = 本表有效记录 ``occupied_u`` 之和。
- 候选上架设备 = 无有效上架记录的设备。
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import MountRecordStatus
from app.models.device import Device
from app.models.mount_record import MountRecord
from app.models.rack import Rack
from app.models.room import Room


class MountRecordRepository:
    """上架记录表的读写操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        device_id: str,
        room_id: str,
        rack_id: str,
        start_u: int,
        occupied_u: int,
        mounted_by: Optional[str] = None,
    ) -> MountRecord:
        record = MountRecord(
            device_id=device_id,
            room_id=room_id,
            rack_id=rack_id,
            start_u=start_u,
            occupied_u=occupied_u,
            mounted_by=mounted_by,
            record_status=MountRecordStatus.ACTIVE.value,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_active_by_device(self, device_id: str) -> Optional[MountRecord]:
        """设备当前有效上架记录（最多一条）。"""
        stmt = (
            select(MountRecord)
            .where(
                MountRecord.device_id == device_id,
                MountRecord.record_status == MountRecordStatus.ACTIVE.value,
            )
            .order_by(MountRecord.mounted_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_devices(
        self, device_ids: list[str]
    ) -> dict[str, MountRecord]:
        """批量取设备当前有效上架记录，返回 {device_id: MountRecord}（设备列表批量预填，避免 N+1）。"""
        if not device_ids:
            return {}
        stmt = select(MountRecord).where(
            MountRecord.device_id.in_(device_ids),
            MountRecord.record_status == MountRecordStatus.ACTIVE.value,
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return {r.device_id: r for r in rows}

    async def list_active_in_rack(self, rack_id: str) -> list[tuple[MountRecord, str, str, int]]:
        """机柜内全部有效上架记录，附带设备名称/类型/U 数，按起始 U 排序。

        Returns:
            ``[(record, device_name, device_type, u_height), ...]``
        """
        stmt = (
            select(MountRecord, Device.name, Device.device_type, Device.u_height)
            .join(Device, MountRecord.device_id == Device.id)
            .where(
                MountRecord.rack_id == rack_id,
                MountRecord.record_status == MountRecordStatus.ACTIVE.value,
            )
            .order_by(MountRecord.start_u)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(r[0], r[1], r[2], r[3]) for r in rows]

    async def sum_occupied_u_in_rack(self, rack_id: str) -> int:
        """机柜内有效记录占用 U 位总和（used_u 重算依据）。"""
        stmt = select(func.coalesce(func.sum(MountRecord.occupied_u), 0)).where(
            MountRecord.rack_id == rack_id,
            MountRecord.record_status == MountRecordStatus.ACTIVE.value,
        )
        return int((await self.session.execute(stmt)).scalar() or 0)

    async def list_unmounted_devices(self) -> list[Device]:
        """候选上架设备：无有效上架记录的设备（仓库/已下架/待报废候选池）。"""
        subq = select(MountRecord.device_id).where(
            MountRecord.record_status == MountRecordStatus.ACTIVE.value
        )
        stmt = (
            select(Device)
            .where(Device.id.notin_(subq))
            .order_by(Device.device_type, Device.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_device_ids_by_rack(self, rack_id: str) -> list[str]:
        """有效上架于指定机柜的设备 id 列表（设备列表过滤用）。"""
        stmt = select(MountRecord.device_id).where(
            MountRecord.rack_id == rack_id,
            MountRecord.record_status == MountRecordStatus.ACTIVE.value,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_device_ids_by_room(self, room_id: str) -> list[str]:
        """有效上架于指定机房（经机柜）的设备 id 列表（设备列表过滤用）。"""
        stmt = (
            select(MountRecord.device_id)
            .join(Rack, MountRecord.rack_id == Rack.id)
            .where(
                Rack.room_id == room_id,
                MountRecord.record_status == MountRecordStatus.ACTIVE.value,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_room(self, room_id: str) -> None:
        """物理删除指定机房下全部上架记录（删除机房前清理，避免孤儿数据）。

        上架记录经 ``rack_id`` 关联机柜、再经机柜 ``room_id`` 归属机房；本方法直接
        按 ``rack.room_id == room_id`` 跨表定位并批量删除，覆盖该机房所有机柜的记录。
        """
        stmt = (
            delete(MountRecord)
            .where(
                MountRecord.rack_id.in_(
                    select(Rack.id).where(Rack.room_id == room_id)
                )
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def list_all_active(self) -> list[MountRecord]:
        """全部有效上架记录（拓扑派生设备当前机柜用）。"""
        stmt = select(MountRecord).where(
            MountRecord.record_status == MountRecordStatus.ACTIVE.value
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def set_unmounted(
        self,
        record: MountRecord,
        *,
        unmounted_at: datetime,
        unmounted_by: Optional[str] = None,
    ) -> None:
        """将一条上架记录置为「已下架」并填写下架信息。"""
        record.record_status = MountRecordStatus.UNMOUNTED.value
        record.unmounted_at = unmounted_at
        record.unmounted_by = unmounted_by
        await self.session.flush()

    async def get_by_id(self, record_id: int) -> Optional[MountRecord]:
        """按主键取单条上架记录。"""
        stmt = select(MountRecord).where(MountRecord.id == record_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, record: MountRecord, data) -> MountRecord:
        """更新上架记录（仅非空字段）。"""
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(record, field, value)
        await self.session.flush()
        return record

    async def delete(self, record: MountRecord) -> None:
        """物理删除一条上架记录。"""
        await self.session.delete(record)
        await self.session.flush()

    async def list_by_device(
        self, device_id: str
    ) -> list[tuple[MountRecord, str, str]]:
        """设备全部上架记录（含已下架），按上架时间倒序，附带机柜名 / 机房名。

        用于设备详情「上下架记录」追溯：每条记录可能包含一次上架与（若已下架）一次下架。
        """
        stmt = (
            select(MountRecord, Rack.name, Room.name)
            .join(Rack, MountRecord.rack_id == Rack.id)
            .join(Room, MountRecord.room_id == Room.id)
            .where(MountRecord.device_id == device_id)
            .order_by(MountRecord.mounted_at.desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [(r[0], r[1], r[2]) for r in rows]

    async def list_all_with_device(
        self,
        *,
        device_name: Optional[str] = None,
        device_code: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[tuple[MountRecord, str, str, str, str]]:
        """全局上下架记录（跨设备），附带机柜名 / 机房名 / 设备编号 / 设备名称。

        用于「上下架记录」集中管理页：支持按设备名称（模糊）、设备编号（模糊）、
        上架时间范围过滤。下架时间范围过滤在服务层展开事件后处理（因一条记录可能
        产生上架 / 下架两个事件，时间字段不同）。按上架时间倒序。
        """
        # 前端 datetime-local 提交的是上海本地时间（naive）。约定按上海时区解释，
        # 转成 UTC naive 再与库内 UTC 时间比较，避免「选今天 00:00」被当成 UTC 00:00
        # （即上海 08:00）的 8 小时偏差。
        _shanghai = timezone(timedelta(hours=8))
        _utc = timezone.utc
        if start_time is not None:
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=_shanghai)
            start_time = start_time.astimezone(_utc).replace(tzinfo=None)
        if end_time is not None:
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=_shanghai)
            end_time = end_time.astimezone(_utc).replace(tzinfo=None)

        stmt = (
            select(MountRecord, Rack.name, Room.name, Device.device_code, Device.name)
            .join(Rack, MountRecord.rack_id == Rack.id)
            .join(Room, MountRecord.room_id == Room.id)
            .join(Device, MountRecord.device_id == Device.id)
        )
        if device_name:
            stmt = stmt.where(Device.name.ilike(f"%{device_name}%"))
        if device_code:
            stmt = stmt.where(Device.device_code.ilike(f"%{device_code}%"))
        if start_time:
            stmt = stmt.where(MountRecord.mounted_at >= start_time)
        if end_time:
            stmt = stmt.where(MountRecord.mounted_at <= end_time)
        stmt = stmt.order_by(MountRecord.mounted_at.desc())
        rows = (await self.session.execute(stmt)).all()
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]
