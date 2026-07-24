"""设备仓储（纯 DB 读写）。

设备表仅含固有属性；按机房/机柜过滤（即「当前位置」）需经上架记录表，由
``MountRecordRepository`` 提供设备 id 集合后，在此处用 ``device_ids`` 过滤。
"""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.link import DeviceLink
from app.models.interface import DeviceInterface
from app.schemas.device import DeviceCreate, DeviceUpdate


class DeviceRepository:
    """设备表的读写操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: DeviceCreate) -> Device:
        device = Device(**data.model_dump())
        self.session.add(device)
        await self.session.flush()
        return device

    async def get(self, device_id: str) -> Optional[Device]:
        stmt = select(Device).where(Device.id == device_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, device_code: str) -> Optional[Device]:
        """按设备编号（唯一）查询。"""
        stmt = select(Device).where(Device.device_code == device_code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ip_excluding(
        self, ip: str, exclude_id: Optional[str] = None
    ) -> Optional[Device]:
        """按 IP 查设备（排除指定 id），用于全局 IP 唯一校验。"""
        stmt = select(Device).where(Device.ip_address == ip)
        if exclude_id:
            stmt = stmt.where(Device.id != exclude_id)
        result = await self.session.execute(stmt)
        # 用 first() 而非 scalar_one_or_none()：历史数据若存在重复 IP，多行命中时
        # scalar_one_or_none() 会抛 MultipleResultsFound -> 500；first() 取首行即可。
        return result.scalars().first()

    async def list(
        self,
        *,
        page: int = 1,
        size: int = 50,
        device_ids: Optional[list[str]] = None,
        device_type: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        is_asset: Optional[bool] = None,
    ) -> Tuple[list[Device], int]:
        conditions = []
        if device_ids is not None:
            # 按当前位置（机柜/机房）过滤：仅包含有有效上架记录的设备集合。
            conditions.append(Device.id.in_(device_ids))
        if device_type:
            conditions.append(Device.device_type == device_type)
        if status:
            conditions.append(Device.status == status)
        if is_asset is not None:
            # 资产/设施过滤：True=仅资产，False=仅设施（非资产）。
            conditions.append(Device.is_asset == is_asset)
        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                (Device.name.like(like))
                | (Device.model.like(like))
                | (Device.sn.like(like))
                | (Device.device_code.like(like))
            )

        base = select(Device)
        count_base = select(func.count()).select_from(Device)
        if conditions:
            base = base.where(*conditions)
            count_base = count_base.where(*conditions)

        total = (await self.session.execute(count_base)).scalar() or 0
        stmt = (
            base.order_by(Device.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def list_all(
        self, device_ids: Optional[list[str]] = None
    ) -> list[Device]:
        """获取全部设备（拓扑用），可限定当前位置设备集合。"""
        stmt = select(Device)
        if device_ids is not None:
            stmt = stmt.where(Device.id.in_(device_ids))
        stmt = stmt.order_by(Device.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_many(self, ids: list[str]) -> list[Device]:
        if not ids:
            return []
        stmt = select(Device).where(Device.id.in_(ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, device: Device, data: DeviceUpdate) -> Device:
        # exclude_unset=True：仅更新请求体中显式提供的字段（未提供的保持不变）。
        # 注意：必须无条件 setattr——前端清空可选字段时显式传 "" 或 null，
        # 若此处 `if value is not None` 跳过，清空操作无法持久化（旧值残留 bug）。
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(device, field, value)
        await self.session.flush()
        return device

    async def delete_device(self, device_id: str) -> None:
        """删除设备：先清理引用其端口的链路，再级联删除端口与设备。"""
        device = await self.get(device_id)
        if device is None:
            return
        interface_stmt = select(DeviceInterface.id).where(
            DeviceInterface.device_id == device_id
        )
        interface_ids = list(
            (await self.session.execute(interface_stmt)).scalars().all()
        )
        if interface_ids:
            link_stmt = delete(DeviceLink).where(
                DeviceLink.source_interface_id.in_(interface_ids)
                | DeviceLink.target_interface_id.in_(interface_ids)
            )
            await self.session.execute(link_stmt)
        await self.session.delete(device)
        await self.session.flush()
