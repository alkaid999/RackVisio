"""链路业务逻辑（含接口唯一性校验 + 建链/删链事务维护两端状态）。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.core.exceptions import ConflictError, NotFoundError
from app.models.device import Device
from app.models.interface import DeviceInterface
from app.models.link import DeviceLink
from app.repositories.device_repo import DeviceRepository
from app.repositories.interface_repo import InterfaceRepository
from app.repositories.link_repo import LinkRepository
from app.repositories.mount_record_repo import MountRecordRepository
from app.schemas.link import LinkCreate, LinkDetailOut, LinkUpdate


class LinkService:
    """设备互联链路业务逻辑：CRUD / 端口唯一性校验 / 建链启用两端。"""

    def __init__(
        self,
        session: AsyncSession,
        cache: Optional[Cache] = None,
        interface_repo: Optional[InterfaceRepository] = None,
        device_repo: Optional[DeviceRepository] = None,
        mount_repo: Optional[MountRecordRepository] = None,
    ) -> None:
        self.session = session
        self.cache = cache or Cache()
        self.link_repo = LinkRepository(session)
        self.interface_repo = interface_repo or InterfaceRepository(session)
        self.device_repo = device_repo or DeviceRepository(session)
        self.mount_repo = mount_repo or MountRecordRepository(session)

    async def check_interface_available(self, interface_id: str) -> dict:
        """检查接口是否可用于新建链路（一接口一链路）。

        Returns:
            可用：``{"available": True}``
            占用：``{"available": False, "reason": str, "link_id": str}``
        """
        existing = await self.link_repo.get_by_interface(interface_id)
        if existing:
            return {
                "available": False,
                "reason": "接口已被链路占用",
                "link_id": existing.id,
            }
        return {"available": True}

    async def _require_linkable(self, device_id: str) -> Device:
        """链路资格校验：设备必须已上架机柜且至少含 1 个接口，否则抛清晰错误。

        用于建链前强制「添加设备 → 添加接口 → 上架机柜」三步依赖；
        未上架（或无接口）的设备无法参与任何链路（含半链路的对端外部场景）。
        """
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        mounted = await self.mount_repo.get_active_by_device(device_id)
        if mounted is None:
            raise ConflictError(
                f"设备「{device.name}」尚未上架机柜，无法创建链路。"
                "请先在「设备管理」将其上架至机柜后，再来创建链路。"
            )
        iface_count = await self.interface_repo.count_by_device(device_id)
        if iface_count == 0:
            raise ConflictError(
                f"设备「{device.name}」已上架机柜，但尚未添加任何接口，无法创建链路。"
                "请先为其添加接口。"
            )
        return device

    async def create_link(self, data: LinkCreate) -> DeviceLink:
        src = await self.interface_repo.get(data.source_interface_id)
        if src is None:
            raise NotFoundError("源接口不存在")

        tgt: Optional[DeviceInterface] = None
        if data.target_interface_id:
            tgt = await self.interface_repo.get(data.target_interface_id)
            if tgt is None:
                raise NotFoundError("目标接口不存在")
            if data.source_interface_id == data.target_interface_id:
                raise ConflictError("源接口与目标接口不能相同")
            check_tgt = await self.check_interface_available(data.target_interface_id)
            if not check_tgt["available"]:
                raise ConflictError(
                    f"目标接口已被链路 {check_tgt['link_id']} 占用"
                )

        # 源接口唯一性校验（半链路也需校验源）。
        check_src = await self.check_interface_available(data.source_interface_id)
        if not check_src["available"]:
            raise ConflictError(
                f"源接口已被链路 {check_src['link_id']} 占用"
            )

        # —— 链路资格校验：源设备（及系统对端设备）必须已上架且含接口 ——
        await self._require_linkable(src.device_id)
        if tgt is not None:
            await self._require_linkable(tgt.device_id)

        link = await self.link_repo.create(data)
        # —— 同一事务启用两端：本端恒启用，对端存在则一并启用（对端外部不反查）——
        src.status = "up"
        if tgt is not None:
            tgt.status = "up"
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def get_link(self, link_id: str) -> DeviceLink:
        link = await self.link_repo.get(link_id)
        if link is None:
            raise NotFoundError("链路不存在")
        return link

    async def get_link_by_interface(self, interface_id: str) -> Optional[LinkDetailOut]:
        """返回该接口所在 active 链路的详情（无则 None）。"""
        detail = await self.link_repo.get_detail_by_interface(interface_id)
        if detail is None:
            return None
        return LinkDetailOut.model_validate(detail)

    async def list_links(
        self,
        *,
        room_id: Optional[str] = None,
        rack_id: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ):
        return await self.link_repo.list(
            room_id=room_id, rack_id=rack_id, page=page, size=size
        )

    async def list_links_detailed(
        self,
        *,
        room_id: Optional[str] = None,
        rack_id: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ):
        """联表查询链路详情（含设备名/接口名），用于前端链路列表展示。"""
        return await self.link_repo.list_detailed(
            room_id=room_id,
            rack_id=rack_id,
            keyword=keyword,
            page=page,
            size=size,
        )

    async def update_link(self, link_id: str, data: LinkUpdate) -> DeviceLink:
        link = await self.get_link(link_id)
        link = await self.link_repo.update(link, data)
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def delete_link(self, link_id: str) -> None:
        link = await self.get_link(link_id)
        # —— 同一事务回滚两端状态：A、B 一起回落 down（半链路只对端内部）——
        src = await self.interface_repo.get(link.source_interface_id)
        if src is not None:
            src.status = "down"
        if link.target_interface_id:
            tgt = await self.interface_repo.get(link.target_interface_id)
            if tgt is not None:
                tgt.status = "down"
        await self.link_repo.delete(link)
        await self.session.commit()
