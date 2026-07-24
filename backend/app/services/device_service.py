"""设备业务逻辑（不含位置；位置由上架记录表管理）。

职责：
- 设备 CRUD（仅固有属性）。
- U 位冲突检测（基于有效上架记录）。
- 删除守卫：已上架（存在有效上架记录）设备禁止删除，须先下架。
- 响应时附带「当前位置」派生字段（有效上架记录的位置）。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.core.database import utcnow
from app.core.enums import DevicePowerStatus, DeviceStatus, DeviceType, MountRecordStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.ip_conflict import assert_ip_cidr, assert_ip_unique
from app.core.meta import FACILITY_TYPES
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError
from app.models.device import Device
from app.models.mount_record import MountRecord
from app.repositories.device_repo import DeviceRepository
from app.repositories.interface_repo import InterfaceRepository
from app.repositories.mount_record_repo import MountRecordRepository
from app.repositories.rack_repo import RackRepository
from app.repositories.room_repo import RoomRepository
from app.schemas.common import ImportFailure, ImportResult
from app.schemas.device import DeviceCreate, DeviceImportItem, DeviceOut, DeviceUpdate
from app.schemas.mount_record import MountRecordUpdate


def _conflict_message(conflict: dict) -> str:
    """将 check_u_conflict 的结果转换为可读错误信息。"""
    if conflict.get("error"):
        return str(conflict["error"])
    return (
        f"U 位冲突：U{conflict['conflict_u']} 已被设备「{conflict['conflict_device']}」占用"
    )


def _gen_device_code() -> str:
    """生成全局唯一设备编号（DEV- + 8 位十六进制）。"""
    return "DEV-" + uuid.uuid4().hex[:8].upper()


class DeviceService:
    """设备相关业务逻辑：CRUD / U 位冲突 / 当前位置派生。"""

    def __init__(self, session: AsyncSession, cache: Optional[Cache] = None) -> None:
        self.session = session
        self.cache = cache or Cache()
        self.device_repo = DeviceRepository(session)
        self.mount_repo = MountRecordRepository(session)
        self.rack_repo = RackRepository(session)
        self.room_repo = RoomRepository(session)
        self.interface_repo = InterfaceRepository(session)

    # ----------------------------------------------------- 当前位置派生
    def _build_out(self, device: Device, active: Optional[MountRecord]) -> DeviceOut:
        """组装 DeviceOut，填充当前有效上架记录的位置（若有）。"""
        data = DeviceOut.model_validate(device)
        if active is not None:
            data.current_room_id = active.room_id
            data.current_rack_id = active.rack_id
            data.current_start_u = active.start_u
        return data

    async def _to_out(
        self,
        device: Device,
        *,
        interface_count: Optional[int] = None,
        active: Optional[MountRecord] = None,
        rack=None,
        room=None,
    ) -> DeviceOut:
        # 列表场景：active/rack/room 已批量预取并传入，避免逐设备查库的 N+1。
        # 其余调用方（get_device 等）不传，则按需单查。
        if active is None:
            active = await self.mount_repo.get_active_by_device(device.id)
        # 回填机柜 / 机房名称（仅用于展示，机房用于设备列表「所属机房」列）。
        out = self._build_out(device, active)
        if active is not None:
            if rack is None:
                rack = await self.rack_repo.get(active.rack_id)
            out.current_rack_name = rack.name if rack else None
            if room is None:
                room = await self.room_repo.get(active.room_id)
            out.current_room_name = room.name if room else None
        # 派生接口总数（链路资格判定：已上架且含接口方可建链）。
        out.interface_count = (
            interface_count
            if interface_count is not None
            else await self.interface_repo.count_by_device(device.id)
        )
        return out

    # ------------------------------------------------------------ U 位冲突
    async def check_u_conflict(
        self,
        rack_id: str,
        start_u: int,
        size_u: int,
        exclude_device_id: Optional[str] = None,
    ) -> dict:
        """检测 U 位冲突（基于机柜内有效上架记录）。

        Returns:
            无冲突：``{"conflict": False}``
            有重叠：``{"conflict": True, "conflict_u": [...], "conflict_device": str}``
            越界：``{"conflict": True, "error": str}``
        """
        if start_u < 1 or size_u < 1:
            return {"conflict": True, "error": "起始 U 位必须 ≥1 且占用 U 位数 ≥1"}
        rack = await self.rack_repo.get(rack_id)
        if rack is None:
            return {"conflict": True, "error": "机柜不存在"}
        mounts = await self.mount_repo.list_active_in_rack(rack_id)
        target_range = set(range(start_u, start_u + size_u))
        for record, name, _, _ in mounts:
            if exclude_device_id and record.device_id == exclude_device_id:
                continue
            existing_range = set(
                range(record.start_u, record.start_u + record.occupied_u)
            )
            overlap = target_range & existing_range
            if overlap:
                return {
                    "conflict": True,
                    "conflict_u": sorted(overlap),
                    "conflict_device": name,
                }
        if (start_u + size_u - 1) > rack.total_u:
            return {"conflict": True, "error": f"超出机柜 U 位范围（1~{rack.total_u}）"}
        return {"conflict": False}

    async def recalculate_rack_usage(self, rack_id: str) -> None:
        """委托 RackService 实现 used_u 重算。"""
        from app.services.rack_service import RackService

        await RackService(self.session, self.cache).recalculate_rack_usage(rack_id)

    # --------------------------------------------------------------- CRUD
    async def create_device(self, data: DeviceCreate) -> DeviceOut:
        # 设备编号留空时自动生成全局唯一编号。
        if not data.device_code:
            data.device_code = _gen_device_code()
        # 确保编号唯一（极小概率碰撞则重试）。
        while await self.device_repo.get_by_code(data.device_code) is not None:
            data.device_code = _gen_device_code()
        # 设施（patch/odf/other_facility）强制 is_asset=False：占 U 位但不进资产统计、
        # 不建接口、不显设备编码。前端若误传 True 也以 False 为准。
        if data.device_type.value in FACILITY_TYPES:
            data = data.model_copy(update={"is_asset": False})
        # 归一化 IP：空串视为未设置 → None。否则空串 '' 会被 uq_device_ip 部分唯一索引
        # （WHERE ip_address IS NOT NULL）当作有效值强制唯一，导致第二个不填 IP 的设备
        # 触发 UNIQUE 冲突。同时把 repo 写操作纳入 try，避免 flush 抛 IntegrityError 冒泡成 500。
        raw_ip = (data.ip_address or "").strip()
        if raw_ip:
            assert_ip_cidr(raw_ip)
            await assert_ip_unique(self.device_repo, self.interface_repo, raw_ip)
            data = data.model_copy(update={"ip_address": raw_ip})
        else:
            data = data.model_copy(update={"ip_address": None})
        try:
            device = await self.device_repo.create(data)
            await self.session.commit()
            await self.session.refresh(device)
        except IntegrityError:
            await self.session.rollback()
            raise ConflictError("IP 地址冲突：该地址已被占用（可能由并发写入导致）")
        return await self._to_out(device)

    async def _prepare_device_import(
        self, data: DeviceCreate, seen_codes: set
    ) -> DeviceCreate:
        """导入设备落库准备：编号自动生成 / 设施强制非资产 / IP 归一化与唯一校验。

        与 ``create_device`` 核心逻辑一致，但返回准备就绪的 ``DeviceCreate``，
        由调用方在 ``begin_nested`` 保存点内提交，实现逐行隔离。
        """
        if not data.device_code:
            data.device_code = _gen_device_code()
        while data.device_code in seen_codes or await self.device_repo.get_by_code(
            data.device_code
        ) is not None:
            data.device_code = _gen_device_code()
        seen_codes.add(data.device_code)
        if data.device_type.value in FACILITY_TYPES:
            data = data.model_copy(update={"is_asset": False})
        raw_ip = (data.ip_address or "").strip()
        if raw_ip:
            assert_ip_cidr(raw_ip)
            await assert_ip_unique(self.device_repo, self.interface_repo, raw_ip)
            data = data.model_copy(update={"ip_address": raw_ip})
        else:
            data = data.model_copy(update={"ip_address": None})
        return data

    async def import_devices(self, items: list[DeviceImportItem]) -> ImportResult:
        """批量导入设备：逐行 ``begin_nested`` 保存点隔离，单条失败不影响其余。

        必填（名称）与类型/枚举/格式校验在前（复用 ``DeviceCreate``）；编号生成 /
        设施强制非资产 / IP 唯一校验在保存点内进行。返回成功条数与失败明细（行号 + 原因）。
        """
        result = ImportResult()
        seen_codes: set[str] = set()
        for idx, item in enumerate(items):
            row = idx + 1
            name = (item.name or "").strip()
            if not name:
                result.failures.append(
                    ImportFailure(row=row, errors=["设备名称不能为空"])
                )
                continue
            # 组装建表参数：仅带显式提供的字段，其余走 DeviceCreate 默认值。
            raw: dict = {
                "name": name,
                "u_height": item.u_height or 1,
                "is_asset": item.is_asset if item.is_asset is not None else True,
            }
            if item.device_code and item.device_code.strip():
                raw["device_code"] = item.device_code.strip()
            if item.device_type and item.device_type.strip():
                raw["device_type"] = item.device_type.strip()
            if item.model and item.model.strip():
                raw["model"] = item.model.strip()
            if item.sn and item.sn.strip():
                raw["sn"] = item.sn.strip()
            if item.ip_address not in (None, ""):
                raw["ip_address"] = item.ip_address
            if item.warranty_expire is not None:
                raw["warranty_expire"] = item.warranty_expire
            if item.remark and item.remark.strip():
                raw["remark"] = item.remark.strip()
            if item.status and item.status.strip():
                raw["status"] = item.status.strip()
            if item.power_status and item.power_status.strip():
                raw["power_status"] = item.power_status.strip()
            try:
                data = DeviceCreate(**raw)
            except PydanticValidationError as exc:
                msgs = [
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in exc.errors()
                ]
                result.failures.append(ImportFailure(row=row, errors=msgs))
                continue

            await self.session.begin_nested()
            try:
                data = await self._prepare_device_import(data, seen_codes)
                device = await self.device_repo.create(data)
                await self.session.flush()
                result.created += 1
                await self.session.commit()
            except Exception as exc:  # 唯一约束 / IP 冲突 / 其它异常 → 仅该条失败
                await self.session.rollback()
                if isinstance(exc, (IntegrityError, ConflictError)):
                    reason = "设备编号或 IP 冲突，或数据不合法"
                elif isinstance(exc, ValidationError):
                    reason = str(exc)
                else:
                    reason = (str(exc) or "创建失败")[:200]
                result.failures.append(ImportFailure(row=row, errors=[reason]))
        result.failed = len(result.failures)
        return result

    async def get_device(self, device_id: str) -> DeviceOut:
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        return await self._to_out(device)

    async def get_device_obj(self, device_id: str) -> Optional[Device]:
        """返回原始 Device 模型（不含派生位置），供需要固有字段的场景使用。"""
        return await self.device_repo.get(device_id)

    async def list_devices(
        self,
        *,
        page: int = 1,
        size: int = 50,
        rack_id: Optional[str] = None,
        device_type: Optional[str] = None,
        status: Optional[str] = None,
        room_id: Optional[str] = None,
        keyword: Optional[str] = None,
        is_asset: Optional[bool] = None,
    ) -> Tuple[list[DeviceOut], int]:
        # 当前位置过滤（机柜 / 机房）→ 经上架记录表得到设备 id 集合。
        device_ids: Optional[list[str]] = None
        if rack_id:
            device_ids = await self.mount_repo.list_device_ids_by_rack(rack_id)
        if room_id:
            room_ids = await self.mount_repo.list_device_ids_by_room(room_id)
            device_ids = (
                list(set(device_ids) & set(room_ids))
                if device_ids is not None
                else room_ids
            )
        devices, total = await self.device_repo.list(
            page=page,
            size=size,
            device_ids=device_ids,
            device_type=device_type,
            status=status,
            keyword=keyword,
            is_asset=is_asset,
        )
        # 批量预取：有效上架记录 + 关联机柜/机房名 + 接口数，将 N+1 降为常量级查询。
        device_ids_all = [d.id for d in devices]
        active_map = await self.mount_repo.get_active_by_devices(device_ids_all)
        rack_ids = {a.rack_id for a in active_map.values()}
        room_ids = {a.room_id for a in active_map.values()}
        racks = (
            {r.id: r for r in await self.rack_repo.get_many(list(rack_ids))}
            if rack_ids
            else {}
        )
        rooms = (
            {r.id: r for r in await self.room_repo.get_many(list(room_ids))}
            if room_ids
            else {}
        )
        counts = await self.interface_repo.count_by_device_ids(device_ids_all)
        outs = []
        for d in devices:
            a = active_map.get(d.id)
            outs.append(
                await self._to_out(
                    d,
                    interface_count=counts.get(d.id, 0),
                    active=a,
                    rack=racks.get(a.rack_id) if a else None,
                    room=rooms.get(a.room_id) if a else None,
                )
            )
        return outs, total

    async def update_device(self, device_id: str, data: DeviceUpdate) -> DeviceOut:
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        # 设施强制 is_asset=False（即使前端误传 True）：设备或即将变更的类型属设施时强制非资产。
        effective_type = (
            data.device_type.value if data.device_type is not None else device.device_type
        )
        if effective_type in FACILITY_TYPES:
            data = data.model_copy(update={"is_asset": False})
        # 若改编号，校验唯一（非空时）。
        if data.device_code and data.device_code != device.device_code:
            if await self.device_repo.get_by_code(data.device_code) is not None:
                raise ConflictError(f"设备编号「{data.device_code}」已存在")
        # 改 U 数且设备已上架：仅同步已上架记录的占用 U 数，保证机柜占用统计一致。
        # 说明：架上设备「调整 U 位 / U 数」能力已移除（统一通过下架后重新上架完成），
        # 故此处不再做重叠拦截，避免「偶尔允许 / 偶尔拒绝」的混乱提示；重叠由 2D 视图可视化告警。
        active = None
        if data.u_height is not None and data.u_height != (device.u_height or 1):
            active = await self.mount_repo.get_active_by_device(device_id)
        # 全局 IP 唯一校验（设备级 IP 与接口级 IP 之间不重复）。清空（空串）跳过。
        if data.ip_address is not None:
            new_ip = data.ip_address.strip()
            # 仅当 IP 发生变化时才校验 CIDR 格式，避免历史无前缀数据（如种子设备）无法编辑。
            if new_ip and new_ip != (device.ip_address or ""):
                assert_ip_cidr(new_ip)
            if new_ip:
                await assert_ip_unique(
                    self.device_repo,
                    self.interface_repo,
                    new_ip,
                    exclude_device_id=device_id,
                )
            data = data.model_copy(update={"ip_address": new_ip or None})
        # 把 repo 写操作与同步 flush 纳入 try：否则 update 内部 flush 抛出的 IntegrityError
        # 会在 try 块之外冒泡，被 FastAPI 当作 500 而非转成 409 冲突提示。
        try:
            device = await self.device_repo.update(device, data)
            # 同步已上架记录的占用 U 数，保证机柜 U 位图 / 占用统计与设备 U 数一致。
            if active is not None:
                # 防御性下界：占用 U 数恒 ≥1（schema 已约束 ge=1，此处兜底避免脏数据）。
                active.occupied_u = max(1, data.u_height or 1)
                await self.session.flush()
                await self.recalculate_rack_usage(active.rack_id)
            await self.session.commit()
            await self.session.refresh(device)
        except IntegrityError:
            await self.session.rollback()
            raise ConflictError("IP 地址冲突：该地址已被占用（可能由并发写入导致）")
        return await self._to_out(device)

    async def delete_device(self, device_id: str) -> None:
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        # 删除守卫：已上架（存在有效上架记录）设备禁止删除，须先下架。
        active = await self.mount_repo.get_active_by_device(device_id)
        if active is not None:
            raise ConflictError("设备已上架，请先下架再删除")
        await self.device_repo.delete_device(device_id)
        await self.session.commit()

    # --------------------------------------------------- 上下架操作流水
    async def get_mount_history(self, device_id: str) -> list[dict]:
        """返回设备上下架操作流水。

        每条上架记录展开为「上架」事件（mounted_at / mounted_by）；若记录已下架，再
        展开一条「下架」事件（unmounted_at / unmounted_by）。全部事件按操作时间倒序，
        供设备详情「上下架记录」表展示。
        """
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        rows = await self.mount_repo.list_by_device(device_id)
        events: list[dict] = []
        for record, rack_name, room_name in rows:
            base = {
                "id": record.id,
                "rack_id": record.rack_id,
                "rack_name": rack_name,
                "room_name": room_name,
                "start_u": record.start_u,
                "occupied_u": record.occupied_u,
                "record_status": record.record_status,
            }
            events.append(
                {
                    **base,
                    "event_type": "上架",
                    "operated_at": record.mounted_at,
                    "operator": record.mounted_by,
                }
            )
            # 已下架的记录补充一条「下架」事件。
            if record.record_status == MountRecordStatus.UNMOUNTED.value:
                events.append(
                    {
                        **base,
                        "event_type": "下架",
                        "operated_at": record.unmounted_at,
                        "operator": record.unmounted_by,
                    }
                )
        # 按操作时间倒序（active 记录无 unmounted_at，置为最小时间）。
        events.sort(
            key=lambda e: e["operated_at"].timestamp() if e["operated_at"] else 0,
            reverse=True,
        )
        return events

    # --------------------------------------------------- 全局上下架记录（集中管理页）
    async def list_mount_events(
        self,
        *,
        device_name: Optional[str] = None,
        device_code: Optional[str] = None,
        op_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[dict]:
        """全局上下架操作流水（跨设备），供「上下架记录」集中管理页展示与导出。

        复用与设备详情页完全一致的事件展开逻辑：每条 MountRecord 展开为「上架」事件
        （mounted_at / mounted_by），若已下架再展开一条「下架」事件（unmounted_at /
        unmounted_by）。因此两处数据同源，不会出现重复或分歧。

        筛选：
        - device_name / device_code：按设备名称 / 编号模糊匹配（下推到 SQL）。
        - op_type：上架 / 下架（事件级，展开后过滤）。
        - start_time / end_time：按事件操作时间范围过滤（上架或下架时间落入区间即命中）。
        """
        rows = await self.mount_repo.list_all_with_device(
            device_name=device_name,
            device_code=device_code,
            start_time=start_time,
            end_time=end_time,
        )
        events: list[dict] = []
        for record, rack_name, room_name, device_code_val, device_name_val in rows:
            base = {
                "id": record.id,
                "device_id": record.device_id,
                "device_name": device_name_val,
                "device_code": device_code_val,
                "rack_id": record.rack_id,
                "rack_name": rack_name,
                "room_name": room_name,
                "start_u": record.start_u,
                "occupied_u": record.occupied_u,
                "record_status": record.record_status,
                "position": f"{room_name} / {rack_name} · {record.start_u}U~{record.start_u + record.occupied_u - 1}U（{record.occupied_u}U）",
            }
            # 上架事件。
            mount_event = {
                **base,
                "event_type": "上架",
                "operated_at": record.mounted_at,
                "operator": record.mounted_by,
            }
            # 下架事件（仅已下架记录）。
            unmount_event = None
            if record.record_status == MountRecordStatus.UNMOUNTED.value:
                unmount_event = {
                    **base,
                    "event_type": "下架",
                    "operated_at": record.unmounted_at,
                    "operator": record.unmounted_by,
                }
            for ev in (mount_event, unmount_event):
                if ev is None:
                    continue
                # 操作类型筛选。
                if op_type and ev["event_type"] != op_type:
                    continue
                # 时间范围筛选（基于事件自身操作时间）。
                op_at = ev["operated_at"]
                if start_time and (op_at is None or op_at < start_time):
                    continue
                if end_time and (op_at is None or op_at > end_time):
                    continue
                events.append(ev)
        # 按操作时间倒序。
        events.sort(
            key=lambda e: e["operated_at"].timestamp() if e["operated_at"] else 0,
            reverse=True,
        )
        return events

    # --------------------------------------------------- 上架记录编辑 / 删除
    async def update_mount_record(self, record_id: int, data: MountRecordUpdate) -> int:
        """编辑上架记录（仅操作人等追溯字段）。返回记录 id。"""
        record = await self.mount_repo.get_by_id(record_id)
        if record is None:
            raise NotFoundError("上架记录不存在")
        await self.mount_repo.update(record, data)
        await self.session.commit()
        return record.id

    async def delete_mount_record(self, record_id: int) -> None:
        """删除一条上架记录（含历史追溯）。

        若该记录为当前有效上架记录，删除后设备失去位置 → 退回「在库」并重算机柜
        used_u，避免设备状态与位置派生不一致的脏数据。删除非有效（已下架）记录为
        纯历史清理。
        """
        record = await self.mount_repo.get_by_id(record_id)
        if record is None:
            raise NotFoundError("上架记录不存在")
        was_active = record.record_status == MountRecordStatus.ACTIVE.value
        device = await self.device_repo.get(record.device_id)
        await self.mount_repo.delete(record)
        if was_active and device is not None:
            device.status = DeviceStatus.IN_STOCK.value
            await self.session.flush()
            await self.recalculate_rack_usage(record.rack_id)
        await self.session.commit()
