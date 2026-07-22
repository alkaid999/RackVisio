"""接口业务逻辑（端口 → 接口 统一命名）。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.core.enums import InterfaceRole, InterfaceSpeed, InterfaceType
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.ip_conflict import assert_ip_cidr, assert_ip_unique
from sqlalchemy.exc import IntegrityError
from app.models.interface import DeviceInterface
from app.repositories.device_repo import DeviceRepository
from app.repositories.interface_repo import InterfaceRepository
from app.repositories.link_repo import LinkRepository
from app.schemas.interface import (
    InterfaceBatchCreate,
    InterfaceCreate,
    InterfaceUpdate,
)


class InterfaceService:
    """设备接口业务逻辑：CRUD / 批量生成。

    接口状态（up/down）由链路事务维护：新增接口恒为 down；建链/删链经 LinkService
    事务同步两端状态。本服务不直接翻转 status。
    """

    def __init__(
        self,
        session: AsyncSession,
        cache: Optional[Cache] = None,
        link_repo: Optional[LinkRepository] = None,
    ) -> None:
        self.session = session
        self.cache = cache or Cache()
        self.interface_repo = InterfaceRepository(session)
        self.device_repo = DeviceRepository(session)
        self.link_repo = link_repo or LinkRepository(session)

    @staticmethod
    def _resolve_interface_no(
        data: InterfaceCreate, existing: list[DeviceInterface]
    ) -> InterfaceCreate:
        """维护 (device_id, interface_no) 设备内唯一：0/留空/已占用则自动分配下一个序号。"""
        used = {p.interface_no for p in existing}
        no = data.interface_no or 0
        if no <= 0 or no in used:
            no = (max(used) + 1) if used else 1
            return data.model_copy(update={"interface_no": no})
        return data

    async def create_interface(
        self, device_id: str, data: InterfaceCreate
    ) -> DeviceInterface:
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        existing = await self.interface_repo.list_by_device(device_id)
        if any(p.name == data.name for p in existing):
            raise ConflictError(f"接口名称 {data.name} 在该设备内已存在")
        # 维护 (device_id, interface_no) 唯一：0 / 留空 / 已占用则自动分配下一个序号。
        data = self._resolve_interface_no(data, existing)
        # 全局 IP 唯一校验（设备级 IP 与接口级 IP 之间不重复）。
        if data.ip_address:
            data = data.model_copy(update={"ip_address": data.ip_address.strip()})
            assert_ip_cidr(data.ip_address)
            await assert_ip_unique(self.device_repo, self.interface_repo, data.ip_address)
        iface = await self.interface_repo.create(device_id, data)
        try:
            await self.session.commit()
            await self.session.refresh(iface)
        except IntegrityError:
            await self.session.rollback()
            raise ConflictError("IP 地址冲突：该地址已被占用（可能由并发写入导致）")
        return iface

    async def list_interfaces(self, device_id: str) -> list[DeviceInterface]:
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        return await self.interface_repo.list_by_device(device_id)

    async def update_interface(
        self, interface_id: str, data: InterfaceUpdate
    ) -> DeviceInterface:
        iface = await self.interface_repo.get(interface_id)
        if iface is None:
            raise NotFoundError("接口不存在")
        # 若修改了 interface_no，需保证设备内唯一（与兄弟接口不冲突）。
        # 前面板序号具有物理意义（面板端口号），必须唯一；显式设为已占用序号时
        # 直接拒绝更新并提示，而非静默改号（避免「更新成功」却破坏唯一性）。
        if data.interface_no is not None and data.interface_no != iface.interface_no:
            siblings = await self.interface_repo.list_by_device(iface.device_id)
            used = {p.interface_no for p in siblings if p.id != iface.id}
            no = data.interface_no
            if no <= 0:
                # 0 / 留空：自动追加到末尾（与新建行为一致），保持设备内唯一。
                no = (max(used) + 1) if used else 1
                data = data.model_copy(update={"interface_no": no})
            elif no in used:
                raise ConflictError(
                    f"前面板序号 {no} 在该设备内已存在，无法修改。请更换为其他序号。"
                )
        # 全局 IP 唯一校验（设备级 IP 与接口级 IP 之间不重复）。清空（空串）跳过。
        if data.ip_address is not None:
            new_ip = data.ip_address.strip()
            # 仅当 IP 发生变化时才校验 CIDR 格式，避免历史无前缀数据（如种子接口）无法编辑。
            if new_ip and new_ip != (iface.ip_address or ""):
                assert_ip_cidr(new_ip)
            if new_ip:
                await assert_ip_unique(
                    self.device_repo,
                    self.interface_repo,
                    new_ip,
                    exclude_interface_id=interface_id,
                )
            data = data.model_copy(update={"ip_address": new_ip or None})
        iface = await self.interface_repo.update(iface, data)
        try:
            await self.session.commit()
            await self.session.refresh(iface)
        except IntegrityError:
            await self.session.rollback()
            raise ConflictError("IP 地址冲突：该地址已被占用（可能由并发写入导致）")
        return iface

    async def delete_interface(self, interface_id: str) -> None:
        iface = await self.interface_repo.get(interface_id)
        if iface is None:
            raise NotFoundError("接口不存在")
        # 回滚对端接口状态：本接口所参与的链路另一端应回落 down。
        link = await self.link_repo.get_by_interface(interface_id)
        if link is not None:
            other_id = (
                link.target_interface_id
                if link.source_interface_id == interface_id
                else link.source_interface_id
            )
            if other_id:
                other = await self.interface_repo.get(other_id)
                if other is not None:
                    other.status = "down"
        # 解除关联链路 + 删除接口（接口仓储内完成）。
        await self.interface_repo.delete(iface)
        await self.session.commit()

    async def batch_create_interfaces(
        self, device_id: str, groups: list[InterfaceBatchCreate]
    ) -> list[DeviceInterface]:
        """按多组命名模板批量生成接口（支持大型交换机混合端口类型）。

        每组生成后共享 ``interface_no`` 序号池，保证设备内唯一；不同组的序号自动错开，
        例如 第 1 组 RJ-45（Gig0/1..48，序号 1..48）+ 第 2 组 SFP（Te0/1..4，序号 49..52）。
        """
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        existing = await self.interface_repo.list_by_device(device_id)
        existing_names = {p.name for p in existing}
        existing_nos = {p.interface_no for p in existing}
        created: list[DeviceInterface] = []
        for data in groups:
            start = (max(existing_nos) + 1) if existing_nos else 1
            default_payload = InterfaceCreate(
                name="",
                interface_type=data.interface_type,
                speed=data.speed,
                role=data.role,
            )
            for i in range(start, start + data.count):
                name = data.naming_pattern % i
                if name in existing_names:
                    continue  # 跳过已存在，避免重复
                default_payload.name = name
                # 批量生成的接口按序号绑定前面板序号（interface_no 设备内唯一）。
                default_payload.interface_no = i
                iface = await self.interface_repo.create(device_id, default_payload)
                created.append(iface)
                existing_names.add(name)
                existing_nos.add(i)
        await self.session.commit()
        for iface in created:
            await self.session.refresh(iface)
        return created
