"""接口仓储（纯 DB 读写）。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.interface import DeviceInterface
from app.models.link import DeviceLink
from app.schemas.interface import InterfaceCreate, InterfaceUpdate


class InterfaceRepository:
    """设备接口表的读写操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, device_id: str, data: InterfaceCreate) -> DeviceInterface:
        # 状态由链路事务维护，创建时不接受、强制 down。
        iface = DeviceInterface(
            device_id=device_id,
            status="down",
            **data.model_dump(),
        )
        self.session.add(iface)
        await self.session.flush()
        return iface

    async def get(self, interface_id: str) -> Optional[DeviceInterface]:
        stmt = select(DeviceInterface).where(DeviceInterface.id == interface_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ip_excluding(
        self, ip: str, exclude_id: Optional[str] = None
    ) -> Optional[DeviceInterface]:
        """按 IP 查接口（排除指定 id），用于全局 IP 唯一校验。"""
        stmt = select(DeviceInterface).where(DeviceInterface.ip_address == ip)
        if exclude_id:
            stmt = stmt.where(DeviceInterface.id != exclude_id)
        result = await self.session.execute(stmt)
        # 用 first() 而非 scalar_one_or_none()：历史数据若存在重复 IP，多行命中时
        # scalar_one_or_none() 会抛 MultipleResultsFound -> 500；first() 取首行即可。
        return result.scalars().first()

    async def get_by_ip_other_device(
        self, ip: str, owner_device_id: Optional[str] = None
    ) -> Optional[DeviceInterface]:
        """按 IP 查「其他设备」的接口，用于带外管理IP 校验。

        带外管理IP 允许与本设备自身接口IP 相同（OOB IP 即配置在该设备某接口上），
        因此排除 ``owner_device_id`` 所属设备的接口；仅当其他设备的接口占用该 IP 时才返回。
        ``owner_device_id`` 为空（设备尚未创建）时不排除任何设备，即任意接口命中即视为冲突。
        """
        stmt = select(DeviceInterface).where(DeviceInterface.ip_address == ip)
        if owner_device_id:
            stmt = stmt.where(DeviceInterface.device_id != owner_device_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_device(self, device_id: str) -> list[DeviceInterface]:
        # 按 interface_no 升序（0 排末尾），再按名称，便于前面板与列表对齐。
        stmt = (
            select(DeviceInterface)
            .where(DeviceInterface.device_id == device_id)
            .order_by(
                (DeviceInterface.interface_no == 0).asc(),
                DeviceInterface.interface_no.asc(),
                DeviceInterface.name.asc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_device(self, device_id: str) -> int:
        """设备接口总数（链路资格判定用）。"""
        stmt = select(func.count()).select_from(DeviceInterface).where(
            DeviceInterface.device_id == device_id
        )
        return int((await self.session.execute(stmt)).scalar() or 0)

    async def count_by_device_ids(self, ids: list[str]) -> dict[str, int]:
        """批量统计各设备接口数，返回 ``{device_id: count}``。"""
        if not ids:
            return {}
        stmt = (
            select(DeviceInterface.device_id, func.count())
            .where(DeviceInterface.device_id.in_(ids))
            .group_by(DeviceInterface.device_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {r[0]: int(r[1]) for r in rows}

    async def list_all(self) -> list[DeviceInterface]:
        stmt = select(DeviceInterface).order_by(
            DeviceInterface.device_id, DeviceInterface.name
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_with_device(
        self, page: int, size: int, keyword: Optional[str] = None
    ) -> tuple[list, int]:
        """全局接口列表（含所属设备名），分页 + 关键字模糊匹配接口名/设备名。

        返回 ``(rows, total)``，其中 ``rows`` 为 ``(DeviceInterface, device_name)`` 元组列表。
        """
        conds = []
        if keyword:
            kw = f"%{keyword}%"
            conds.append(or_(DeviceInterface.name.ilike(kw), Device.name.ilike(kw)))
        base_items = (
            select(DeviceInterface, Device.name.label("device_name"))
            .join(Device, Device.id == DeviceInterface.device_id)
        )
        base_count = (
            select(func.count())
            .select_from(DeviceInterface)
            .join(Device, Device.id == DeviceInterface.device_id)
        )
        if conds:
            base_items = base_items.where(*conds)
            base_count = base_count.where(*conds)
        items_stmt = (
            base_items.order_by(
                Device.name.asc(),
                (DeviceInterface.interface_no == 0).asc(),
                DeviceInterface.interface_no.asc(),
                DeviceInterface.name.asc(),
            )
            .limit(size)
            .offset((page - 1) * size)
        )
        rows = (await self.session.execute(items_stmt)).all()
        total = int((await self.session.execute(base_count)).scalar() or 0)
        return rows, total

    async def update(
        self, iface: DeviceInterface, data: InterfaceUpdate
    ) -> DeviceInterface:
        # 状态（status）不在此处更新，由链路事务维护。
        # exclude_unset=True 已保证「局部更新」安全（仅覆盖请求中显式提供的字段）；
        # 此处默认不把字段覆盖为 None，避免误清空；唯独 ip_address 是可选可清空的属性，
        # 允许将其置为 None（前端清空时显式传 null）。
        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "status":
                continue
            if value is None and field != "ip_address":
                continue
            setattr(iface, field, value)
        await self.session.flush()
        return iface

    async def delete(self, iface: DeviceInterface) -> None:
        """删除接口：先解除引用该接口（作为源或目标）的链路，再删除接口。"""
        link_stmt = delete(DeviceLink).where(
            (DeviceLink.source_interface_id == iface.id)
            | (DeviceLink.target_interface_id == iface.id)
        )
        await self.session.execute(link_stmt)
        await self.session.delete(iface)
        await self.session.flush()

    async def list_unlinked(self) -> list[dict]:
        """返回所有未建立链路的接口（未被任何链路作为源或对端引用）。

        用于连接总览的「孤儿口」开关：展示尚未连线的接口，补全布线全景。
        """
        # 任一链路引用（本端或对端）的接口 id 集合（去重）。
        linked_source = select(DeviceLink.source_interface_id).where(
            DeviceLink.source_interface_id.isnot(None)
        )
        linked_target = select(DeviceLink.target_interface_id).where(
            DeviceLink.target_interface_id.isnot(None)
        )
        linked_sub = linked_source.union(linked_target).subquery()
        stmt = (
            select(
                DeviceInterface.id.label("interface_id"),
                DeviceInterface.name.label("interface_name"),
                DeviceInterface.interface_type.label("interface_type"),
                Device.id.label("device_id"),
                Device.name.label("device_name"),
            )
            .select_from(DeviceInterface)
            .join(Device, DeviceInterface.device_id == Device.id)
            .outerjoin(
                linked_sub,
                DeviceInterface.id == linked_sub.c.source_interface_id,
            )
            .where(linked_sub.c.source_interface_id.is_(None))
            .order_by(Device.name, DeviceInterface.name)
        )
        rows = (await self.session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]
