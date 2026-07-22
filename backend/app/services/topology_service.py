"""拓扑聚合服务（nodes + edges）。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.core.exceptions import NotFoundError
from app.models.link import DeviceLink
from app.repositories.device_repo import DeviceRepository
from app.repositories.interface_repo import InterfaceRepository
from app.repositories.link_repo import LinkRepository
from app.repositories.mount_record_repo import MountRecordRepository
from app.schemas.link import TopologyEdge, TopologyNode, TopologyResponse


class TopologyService:
    """拓扑数据聚合：设备为节点，链路为边。"""

    def __init__(self, session: AsyncSession, cache: Optional[Cache] = None) -> None:
        self.session = session
        self.cache = cache or Cache()
        self.device_repo = DeviceRepository(session)
        self.interface_repo = InterfaceRepository(session)
        self.link_repo = LinkRepository(session)
        self.mount_repo = MountRecordRepository(session)

    def _rack_id_map(self, mounts) -> dict[str, str]:
        """device_id -> rack_id（由有效上架记录推导当前机柜）。"""
        return {m.device_id: m.rack_id for m in mounts}

    async def get_topology(
        self,
        room_id: Optional[str] = None,
        rack_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> TopologyResponse:
        """聚合拓扑。支持 room_id / rack_id / device_id 过滤。"""
        if device_id:
            return await self.get_device_topology(device_id)

        # 当前位置过滤（机柜/机房）→ 经上架记录表得到设备 id 集合。
        device_ids_filter: list[str] | None = None
        if rack_id:
            device_ids_filter = await self.mount_repo.list_device_ids_by_rack(rack_id)
        if room_id:
            room_ids = await self.mount_repo.list_device_ids_by_room(room_id)
            device_ids_filter = (
                list(set(device_ids_filter) & set(room_ids))
                if device_ids_filter is not None
                else room_ids
            )
        devices = await self.device_repo.list_all(device_ids=device_ids_filter)
        active = await self.mount_repo.list_all_active()
        rack_map = self._rack_id_map(active)
        device_ids = {d.id for d in devices}
        nodes = [
            TopologyNode(
                id=d.id,
                name=d.name,
                device_type=d.device_type,
                status=d.status,
                rack_id=rack_map.get(d.id),
            )
            for d in devices
        ]
        return await self._build_edges(device_ids, nodes)

    async def get_device_topology(self, device_id: str) -> TopologyResponse:
        """单设备拓扑：包含该设备与其一跳邻居。"""
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        device_interfaces = await self.interface_repo.list_by_device(device_id)
        interface_ids = {p.id for p in device_interfaces}
        links = await self.link_repo.list_all()
        interface_map = await self._interface_map()

        edges: list[TopologyEdge] = []
        neighbor_ids: set[str] = set()
        for link in links:
            if (
                link.source_interface_id in interface_ids
                or link.target_interface_id in interface_ids
            ):
                sp = interface_map.get(link.source_interface_id)
                tp = interface_map.get(link.target_interface_id)
                if not sp or not tp:
                    continue
                src_dev, src_name = sp
                tgt_dev, tgt_name = tp
                # 跳过设备自连（source == target）的冗余自环链路，
                # 避免拓扑图出现无意义「节点0/链路0」自环。
                if src_dev == tgt_dev:
                    continue
                neighbor_ids.add(src_dev)
                neighbor_ids.add(tgt_dev)
                edges.append(
                    TopologyEdge(
                        id=link.id,
                        source=src_dev,
                        target=tgt_dev,
                        source_interface=src_name,
                        target_interface=tgt_name,
                        remark=link.remark,
                        medium=link.medium,
                        cable_length=link.cable_length,
                    )
                )
        neighbor_ids.discard(None)
        all_ids = neighbor_ids | {device_id}
        devices = await self.device_repo.get_many(list(all_ids))
        active = await self.mount_repo.list_all_active()
        rack_map = self._rack_id_map(active)
        nodes = [
            TopologyNode(
                id=d.id,
                name=d.name,
                device_type=d.device_type,
                status=d.status,
                rack_id=rack_map.get(d.id),
            )
            for d in devices
        ]
        return TopologyResponse(nodes=nodes, edges=edges)

    async def _interface_map(self) -> dict[str, tuple[str, str]]:
        """接口 id -> (device_id, name)。"""
        interfaces = await self.interface_repo.list_all()
        return {p.id: (p.device_id, p.name) for p in interfaces}

    async def _build_edges(
        self, device_ids: set[str], nodes: list[TopologyNode]
    ) -> TopologyResponse:
        """基于全部链路构建 edges（两端设备均在 device_ids 内）。"""
        interface_map = await self._interface_map()
        links: list[DeviceLink] = await self.link_repo.list_all()
        edges: list[TopologyEdge] = []
        for link in links:
            sp = interface_map.get(link.source_interface_id)
            tp = interface_map.get(link.target_interface_id)
            if not sp or not tp:
                continue
            src_dev, src_name = sp
            tgt_dev, tgt_name = tp
            if src_dev == tgt_dev:
                continue
            if src_dev in device_ids and tgt_dev in device_ids:
                edges.append(
                    TopologyEdge(
                        id=link.id,
                        source=src_dev,
                        target=tgt_dev,
                        source_interface=src_name,
                        target_interface=tgt_name,
                        remark=link.remark,
                        medium=link.medium,
                        cable_length=link.cable_length,
                    )
                )
        return TopologyResponse(nodes=nodes, edges=edges)
