"""链路仓储（纯 DB 读写）。"""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.device import Device
from app.models.interface import DeviceInterface
from app.models.link import DeviceLink
from app.models.rack import Rack
from app.repositories.mount_record_repo import MountRecordRepository
from app.schemas.link import LinkCreate, LinkUpdate

# 链路联表查询需要同时引用「本端」与「对端」的设备/接口，故对模型取别名。
SDev = aliased(Device)
TDev = aliased(Device)
SInterface = aliased(DeviceInterface)
TInterface = aliased(DeviceInterface)


class LinkRepository:
    """设备互联链路表的读写操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.mount_repo = MountRecordRepository(session)

    async def create(self, data: LinkCreate) -> DeviceLink:
        link = DeviceLink(**data.model_dump())
        self.session.add(link)
        await self.session.flush()
        return link

    async def get(self, link_id: str) -> Optional[DeviceLink]:
        stmt = select(DeviceLink).where(DeviceLink.id == link_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        room_id: Optional[str] = None,
        rack_id: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[list[DeviceLink], int]:
        # 通过 source_interface -> device 关联以支持按机柜/机房过滤；
        # 当前位置（机柜/机房）经上架记录表得到设备 id 集合后过滤。
        device_ids = await self._resolve_device_ids(rack_id, room_id)
        base = select(DeviceLink).join(
            DeviceInterface, DeviceLink.source_interface_id == DeviceInterface.id
        ).join(Device, DeviceInterface.device_id == Device.id)
        count_base = (
            select(func.count())
            .select_from(DeviceLink)
            .join(DeviceInterface, DeviceLink.source_interface_id == DeviceInterface.id)
            .join(Device, DeviceInterface.device_id == Device.id)
        )
        conditions = []
        if device_ids is not None:
            conditions.append(Device.id.in_(device_ids))

        if conditions:
            base = base.where(*conditions)
            count_base = count_base.where(*conditions)

        total = (await self.session.execute(count_base)).scalar() or 0
        stmt = (
            base.order_by(DeviceLink.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def list_all(self) -> list[DeviceLink]:
        stmt = select(DeviceLink)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_all(self) -> int:
        """全量链路计数（统计页使用，避免 list_all 全表拉取内存计数）。"""
        stmt = select(func.count()).select_from(DeviceLink)
        return int((await self.session.execute(stmt)).scalar() or 0)

    async def list_detailed(
        self,
        *,
        room_id: Optional[str] = None,
        rack_id: Optional[str] = None,
        keyword: Optional[str] = None,
        medium: Optional[str] = None,
        connector_type: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Tuple[list[dict], int]:
        """联表查询链路详情（含本端/对端设备名与接口名）。

        返回 ``(rows, total)``，``rows`` 为可直接喂给 ``LinkDetailOut`` 的字典列表。
        半链路（target_interface_id 为空）时，对端设备名退回 target_external 文本。
        """
        columns = [
            DeviceLink.id,
            DeviceLink.remark,
            DeviceLink.medium,
            DeviceLink.cable_length,
            DeviceLink.connector_type,
            DeviceLink.target_external,
            DeviceLink.created_at,
            DeviceLink.updated_at,
            SInterface.id.label("source_interface_id"),
            SInterface.name.label("source_interface_name"),
            SDev.id.label("source_device_id"),
            SDev.name.label("source_device_name"),
            TInterface.id.label("target_interface_id"),
            TInterface.name.label("target_interface_name"),
            TDev.id.label("target_device_id"),
            TDev.name.label("target_device_name"),
        ]
        base = (
            select(*columns)
            .select_from(DeviceLink)
            .join(SInterface, DeviceLink.source_interface_id == SInterface.id)
            .join(SDev, SInterface.device_id == SDev.id)
            .outerjoin(
                TInterface, DeviceLink.target_interface_id == TInterface.id
            )
            .outerjoin(TDev, TInterface.device_id == TDev.id)
        )
        count_base = (
            select(func.count())
            .select_from(DeviceLink)
            .join(SInterface, DeviceLink.source_interface_id == SInterface.id)
            .join(SDev, SInterface.device_id == SDev.id)
            .outerjoin(
                TInterface, DeviceLink.target_interface_id == TInterface.id
            )
            .outerjoin(TDev, TInterface.device_id == TDev.id)
        )
        conditions = []
        device_ids = await self._resolve_device_ids(rack_id, room_id)
        if device_ids is not None:
            conditions.append(SDev.id.in_(device_ids))
        if keyword:
            like = f"%{keyword}%"
            # 注意：必须用已 JOIN 的别名 SInterface / TInterface，不能引用未别名的
            # DeviceInterface 基础表——否则 SQLAlchemy 会隐式笛卡尔扇出，导致同一链路
            # 被复制成「接口总数」那么多行（搜索结果大量重复）。
            conditions.append(
                (SDev.name.like(like))
                | (TDev.name.like(like))
                | (SInterface.name.like(like))
                | (TInterface.name.like(like))
                | (DeviceLink.target_external.like(like))
            )
        if medium:
            conditions.append(DeviceLink.medium == medium)
        if connector_type:
            conditions.append(DeviceLink.connector_type == connector_type)
        if conditions:
            base = base.where(*conditions)
            count_base = count_base.where(*conditions)

        total = (await self.session.execute(count_base)).scalar() or 0
        stmt = (
            base.order_by(DeviceLink.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await self.session.execute(stmt)).mappings().all()
        return [self._normalize_detail(dict(r)) for r in rows], total

    @staticmethod
    def _normalize_detail(row: dict) -> dict:
        """半链路（target_interface_id 为空）时，对端设备名退回 target_external 文本，
        保证 ``LinkDetailOut.target_device_name`` 恒为字符串，对端接口名置空。"""
        if row.get("target_interface_id") is None:
            row["target_device_name"] = row.get("target_external") or "外部"
            row["target_interface_name"] = None
        return row

    async def get_by_interface(
        self, interface_id: str
    ) -> Optional[DeviceLink]:
        """查找占用该接口（源或目标）的链路（一接口一链路校验，链路恒为可用状态）。"""
        stmt = select(DeviceLink).where(
            (DeviceLink.source_interface_id == interface_id)
            | (DeviceLink.target_interface_id == interface_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_detail_by_interface(
        self, interface_id: str
    ) -> Optional[dict]:
        """返回该接口所在 active 链路的详情（联表），用于接口详情页展示。"""
        columns = [
            DeviceLink.id,
            DeviceLink.remark,
            DeviceLink.medium,
            DeviceLink.cable_length,
            DeviceLink.connector_type,
            DeviceLink.target_external,
            DeviceLink.created_at,
            DeviceLink.updated_at,
            SInterface.id.label("source_interface_id"),
            SInterface.name.label("source_interface_name"),
            SDev.id.label("source_device_id"),
            SDev.name.label("source_device_name"),
            TInterface.id.label("target_interface_id"),
            TInterface.name.label("target_interface_name"),
            TDev.id.label("target_device_id"),
            TDev.name.label("target_device_name"),
        ]
        stmt = (
            select(*columns)
            .select_from(DeviceLink)
            .join(SInterface, DeviceLink.source_interface_id == SInterface.id)
            .join(SDev, SInterface.device_id == SDev.id)
            .outerjoin(TInterface, DeviceLink.target_interface_id == TInterface.id)
            .outerjoin(TDev, TInterface.device_id == TDev.id)
            .where(
                (DeviceLink.source_interface_id == interface_id)
                | (DeviceLink.target_interface_id == interface_id),
            )
        )
        result = (await self.session.execute(stmt)).mappings().first()
        return self._normalize_detail(dict(result)) if result is not None else None

    async def list_detailed_by_device(
        self, device_id: str
    ) -> list[dict]:
        """返回某设备作为本端或对端的全部链路（归一到「设备视角」）。

        用于设备详情页「链路」Card：每行包含本设备接口（local）与对端（peer）。
        半链路（对端非系统内）时 peer 设备名退回 target_external 文本。
        """
        columns = [
            DeviceLink.id,
            DeviceLink.remark,
            DeviceLink.medium,
            DeviceLink.cable_length,
            DeviceLink.connector_type,
            DeviceLink.target_external,
            DeviceLink.created_at,
            DeviceLink.updated_at,
            SInterface.id.label("source_interface_id"),
            SInterface.name.label("source_interface_name"),
            SDev.id.label("source_device_id"),
            SDev.name.label("source_device_name"),
            TInterface.id.label("target_interface_id"),
            TInterface.name.label("target_interface_name"),
            TDev.id.label("target_device_id"),
            TDev.name.label("target_device_name"),
        ]
        stmt = (
            select(*columns)
            .select_from(DeviceLink)
            .join(SInterface, DeviceLink.source_interface_id == SInterface.id)
            .join(SDev, SInterface.device_id == SDev.id)
            .outerjoin(TInterface, DeviceLink.target_interface_id == TInterface.id)
            .outerjoin(TDev, TInterface.device_id == TDev.id)
            .where((SDev.id == device_id) | (TDev.id == device_id))
            .order_by(DeviceLink.created_at.desc())
        )
        rows = (await self.session.execute(stmt)).mappings().all()
        return [self._normalize_device_link(dict(r), device_id) for r in rows]

    @staticmethod
    def _normalize_device_link(row: dict, device_id: str) -> dict:
        """把一条链路归一到「本设备视角」：local=本设备接口，peer=对端（或外部）。"""
        is_source = row.get("source_device_id") == device_id
        if is_source:
            local_iface_id = row.get("source_interface_id")
            local_iface_name = row.get("source_interface_name")
            peer_device_id = row.get("target_device_id")
            peer_device_name = row.get("target_device_name")
            peer_iface_id = row.get("target_interface_id")
            peer_iface_name = row.get("target_interface_name")
        else:
            local_iface_id = row.get("target_interface_id")
            local_iface_name = row.get("target_interface_name")
            peer_device_id = row.get("source_device_id")
            peer_device_name = row.get("source_device_name")
            peer_iface_id = row.get("source_interface_id")
            peer_iface_name = row.get("source_interface_name")
        # 半链路：对端接口为空，设备名退回外部文本。
        if not peer_iface_id:
            peer_device_name = row.get("target_external") or "外部"
        return {
            "link_id": row.get("id"),
            "local_interface_id": local_iface_id,
            "local_interface_name": local_iface_name,
            "peer_device_id": peer_device_id,
            "peer_device_name": peer_device_name,
            "peer_interface_id": peer_iface_id,
            "peer_interface_name": peer_iface_name,
            "is_half": not bool(peer_iface_id),
            "medium": row.get("medium"),
            "connector_type": row.get("connector_type"),
            "cable_length": row.get("cable_length"),
            "remark": row.get("remark"),
            "created_at": row.get("created_at"),
        }

    async def count_by_device(self, device_id: str) -> int:
        """计算某设备作为本端或对端参与的链路总数（用于下架前校验）。

        只要设备的任一接口出现在链路的 source_interface_id 或 target_interface_id 中，
        即计为一条关联链路。已删除的链路不存在于表中，自然不计入。
        """
        stmt = (
            select(func.count())
            .select_from(DeviceLink)
            .join(DeviceInterface, DeviceLink.source_interface_id == DeviceInterface.id)
            .where(
                (DeviceInterface.device_id == device_id)
                | (
                    DeviceLink.target_interface_id.isnot(None)
                    & DeviceLink.target_interface_id.in_(
                        select(DeviceInterface.id).where(
                            DeviceInterface.device_id == device_id
                        )
                    )
                )
            )
        )
        return int((await self.session.execute(stmt)).scalar() or 0)

    async def update(self, link: DeviceLink, data: LinkUpdate) -> DeviceLink:
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(link, field, value)
        await self.session.flush()
        return link

    async def delete(self, link: DeviceLink) -> None:
        await self.session.delete(link)
        await self.session.flush()

    async def _resolve_device_ids(
        self, rack_id: Optional[str], room_id: Optional[str]
    ) -> Optional[list[str]]:
        """按当前位置（机柜/机房）解析有效上架设备 id 集合。

        rack_id / room_id 均为 None 时返回 None（不过滤）。
        返回的 id 集合用于 ``Device.id.in_(...)`` 过滤链路。
        """
        if not rack_id and not room_id:
            return None
        ids: list[str] = []
        if rack_id:
            ids = await self.mount_repo.list_device_ids_by_rack(rack_id)
        if room_id:
            room_ids = await self.mount_repo.list_device_ids_by_room(room_id)
            ids = list(set(ids) & set(room_ids)) if rack_id else room_ids
        return ids
