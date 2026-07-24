"""机柜业务逻辑。

面向政企 / IDC 租用场景：机柜以「列编号(column_code) + 机柜编号(code)」定位，
业务状态(status)由用户维护（可用/空闲/维护中/空调柜/电柜），容量状态(used_u)由后端
按有效上架记录自动重算，两者解耦。设备上架 / 下架通过 ``mount_records`` 表实现，
设备表本身不含位置字段。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.core.database import utcnow
from app.core.enums import DeviceStatus, MountRecordStatus, RackBizStatus
from app.core.exceptions import ConflictError, NotFoundError
from app.models.rack import Rack
from app.repositories.device_repo import DeviceRepository
from app.repositories.mount_record_repo import MountRecordRepository
from app.repositories.rack_repo import RackRepository
from app.repositories.room_repo import RoomRepository
from app.schemas.common import ImportFailure, ImportResult
from app.schemas.rack import (
    RackBatchCreate,
    RackBatchFailure,
    RackBatchResult,
    RackCreate,
    RackImportItem,
    RackListItem,
    RackOut,
    RackUpdate,
)
from app.services.device_service import DeviceService


def _build_grid_allocator(existing: list[Rack]):
    """构建机柜平面图网格坐标的内存增量分配器（与单条 ``_assign_grid`` 规则一致）。

    - 同列编号归同一行，行内取下一列；新列另起一行。
    - 返回 ``(next_grid, existing_keys)``：``next_grid`` 按列分配坐标（可显式指定）；
      ``existing_keys`` 为该机房已有 ``(column_code, code)`` 集合，供唯一性校验。
    """
    col_row_map: dict[str, int] = {}
    col_used_cols: dict[str, set] = {}
    max_row = -1
    for r in existing:
        if r.column_code and r.grid_row is not None:
            col_row_map.setdefault(r.column_code, r.grid_row)
            col_used_cols.setdefault(r.column_code, set())
            if r.grid_col is not None:
                col_used_cols[r.column_code].add(r.grid_col)
                max_row = max(max_row, r.grid_row)
    next_new_row = max_row + 1
    existing_keys = {(r.column_code, r.code) for r in existing}

    def next_grid(column_code: str, explicit_row=None, explicit_col=None):
        nonlocal next_new_row
        if explicit_row is not None and explicit_col is not None:
            col_used_cols.setdefault(column_code, set()).add(explicit_col)
            col_row_map.setdefault(column_code, explicit_row)
            return explicit_row, explicit_col
        if column_code in col_row_map:
            row = col_row_map[column_code]
            used = col_used_cols[column_code]
            nxt = (max(used) + 1) if used else 0
        else:
            row = next_new_row
            next_new_row = next_new_row + 1
            col_row_map[column_code] = row
            col_used_cols[column_code] = set()
            nxt = 0
        col_used_cols[column_code].add(nxt)
        return row, nxt

    return next_grid, existing_keys


def _normalize_rack_status(val: Optional[str]) -> RackBizStatus:
    """导入机柜状态归一化：接受业务枚举中文值，缺省「可用」。"""
    if not val:
        return RackBizStatus.AVAILABLE
    try:
        return RackBizStatus(val.strip())
    except ValueError:
        return RackBizStatus.AVAILABLE


class RackService:
    """机柜相关业务逻辑：CRUD / U 位重算 / 设备上架下架 / 候选设备。"""

    def __init__(self, session: AsyncSession, cache: Optional[Cache] = None) -> None:
        self.session = session
        self.cache = cache or Cache()
        self.rack_repo = RackRepository(session)
        self.device_repo = DeviceRepository(session)
        self.mount_repo = MountRecordRepository(session)

    # ------------------------------------------------------------------ CRUD
    async def create_rack(self, data: RackCreate) -> Rack:
        room_repo = RoomRepository(self.session)
        room = await room_repo.get(data.room_id)
        if room is None:
            raise NotFoundError("所属机房不存在")

        if await self.rack_repo.exists_code(
            data.room_id, data.column_code, data.code
        ):
            raise ConflictError(
                f"机柜编号「{data.code}」在列「{data.column_code}」内已存在"
            )

        if not data.name:
            data.name = f"{data.column_code}-{data.code}"

        rack = await self.rack_repo.create(data)
        await self._assign_grid(data, rack)
        await self.session.commit()
        await self.session.refresh(rack)
        await self._invalidate_room_cache(data.room_id)
        return rack

    async def create_racks_batch(self, data: RackBatchCreate) -> RackBatchResult:
        """批量新增机柜：一次请求在一个事务内完成，替代前端循环调单条。

        - 机房校验一次；同机房已有 ``(column_code, code)`` 集合一次性取出，避免逐条查库。
        - 平面图 grid 坐标在内存中增量分配：同列归同一行、行内取下一列，新列另起一行，
          与单条 ``_assign_grid`` 规则一致；同批次内条目也互斥。
        - 每条机柜用 ``begin_nested()`` 保存点隔离：冲突 / 空值 / 唯一约束违规只计入
          ``failed``，不影响其余条目；全部成功项在循环结束后统一 ``commit``。
        """
        room_repo = RoomRepository(self.session)
        room = await room_repo.get(data.room_id)
        if room is None:
            raise NotFoundError("所属机房不存在")

        existing = await self.rack_repo.list_by_room(data.room_id)
        existing_keys = {(r.column_code, r.code) for r in existing}

        # ---- 内存中维护 grid 占用状态，实现增量分配 ----
        col_row_map: dict[str, int] = {}
        col_used_cols: dict[str, set] = {}
        max_row = -1
        for r in existing:
            if r.column_code and r.grid_row is not None:
                col_row_map.setdefault(r.column_code, r.grid_row)
                col_used_cols.setdefault(r.column_code, set())
                if r.grid_col is not None:
                    col_used_cols[r.column_code].add(r.grid_col)
                    max_row = max(max_row, r.grid_row)
        next_new_row = max_row + 1

        def next_grid(column_code: str) -> tuple[int, int]:
            nonlocal next_new_row
            if column_code in col_row_map:
                row = col_row_map[column_code]
                used = col_used_cols[column_code]
                nxt = (max(used) + 1) if used else 0
            else:
                row = next_new_row
                next_new_row = next_new_row + 1
                col_row_map[column_code] = row
                col_used_cols[column_code] = set()
                nxt = 0
            col_used_cols[column_code].add(nxt)
            return row, nxt

        result = RackBatchResult()
        seen: set = set()
        for idx, item in enumerate(data.items):
            col = (item.column_code or "").strip()
            code = (item.code or "").strip()
            if not col or not code:
                result.failed.append(
                    RackBatchFailure(
                        index=idx, column_code=col, code=code,
                        name=item.name, error="列编号与机柜编号均必填",
                    )
                )
                continue
            key = (col, code)
            if key in seen:
                result.failed.append(
                    RackBatchFailure(
                        index=idx, column_code=col, code=code,
                        name=item.name, error="本批次内存在重复编号（同列同号）",
                    )
                )
                continue
            if key in existing_keys:
                result.failed.append(
                    RackBatchFailure(
                        index=idx, column_code=col, code=code,
                        name=item.name, error="该列编号下机柜编号已存在",
                    )
                )
                continue
            seen.add(key)

            grid_row, grid_col = (
                (item.grid_row, item.grid_col)
                if item.grid_row is not None and item.grid_col is not None
                else next_grid(col)
            )
            name = (item.name or "").strip() or f"{col}-{code}"
            payload = RackCreate(
                room_id=data.room_id,
                name=name,
                code=code,
                column_code=col,
                total_u=data.total_u,
                rack_group=data.rack_group,
                status=data.status,
                grid_row=grid_row,
                grid_col=grid_col,
            )

            await self.session.begin_nested()
            try:
                rack = await self.rack_repo.create(payload)
                rack.created_at = utcnow()
                rack.updated_at = rack.created_at
                await self.session.flush()
                result.created.append(RackOut.model_validate(rack))
                await self.session.commit()  # 释放保存点，保留到外层事务
            except Exception as exc:  # 唯一约束 / 其他 DB 异常 → 仅该条失败
                await self.session.rollback()  # 回滚到保存点
                reason = (
                    "编号重复（同机房同列同号）或数据不合法"
                    if isinstance(exc, IntegrityError)
                    else (str(exc) or "创建失败")[:200]
                )
                result.failed.append(
                    RackBatchFailure(
                        index=idx, column_code=col, code=code,
                        name=item.name, error=reason,
                    )
                )

        if result.created:
            await self.session.commit()  # 一次性提交所有成功项
            await self._invalidate_room_cache(data.room_id)
        return result

    async def import_racks(self, items: list[RackImportItem]) -> ImportResult:
        """批量导入机柜：按机房分组，逐行 ``begin_nested`` 保存点隔离。

        以「机房编号」定位机房（更贴合表格用户）；每组复用内存 grid 增量分配
        （同 ``create_racks_batch``）；唯一性（同机房同列同号）与必填校验失败仅计入
        ``failures``。返回成功条数与失败明细。
        """
        result = ImportResult()
        room_repo = RoomRepository(self.session)
        rooms = await room_repo.list_all()
        room_by_code = {r.code: r for r in rooms}
        room_state: dict[str, dict] = {}

        for idx, item in enumerate(items):
            row = idx + 1
            room_code = (item.room_code or "").strip()
            col = (item.column_code or "").strip()
            code = (item.code or "").strip()
            errors: list[str] = []
            if not room_code:
                errors.append("所属机房编号不能为空")
            if not col:
                errors.append("列编号不能为空")
            if not code:
                errors.append("机柜编号不能为空")
            if errors:
                result.failures.append(ImportFailure(row=row, errors=errors))
                continue
            room = room_by_code.get(room_code)
            if room is None:
                result.failures.append(
                    ImportFailure(row=row, errors=[f"所属机房编号「{room_code}」不存在"])
                )
                continue
            st = room_state.get(room.id)
            if st is None:
                existing = await self.rack_repo.list_by_room(room.id)
                next_grid, existing_keys = _build_grid_allocator(existing)
                st = {"existing": existing_keys, "seen": set(), "next_grid": next_grid}
                room_state[room.id] = st
            key = (col, code)
            if key in st["existing"] or key in st["seen"]:
                result.failures.append(
                    ImportFailure(row=row, errors=[f"机柜「{col}-{code}」在该机房已存在"])
                )
                continue
            st["seen"].add(key)
            name = (item.name or "").strip() or f"{col}-{code}"
            status = _normalize_rack_status(item.status)
            total_u = item.total_u or 42
            grid_row, grid_col = st["next_grid"](col, item.grid_row, item.grid_col)
            payload = RackCreate(
                room_id=room.id,
                name=name,
                code=code,
                column_code=col,
                total_u=total_u,
                rack_group=(item.rack_group or "").strip() or None,
                status=status,
                grid_row=grid_row,
                grid_col=grid_col,
            )
            await self.session.begin_nested()
            try:
                rack = await self.rack_repo.create(payload)
                rack.created_at = utcnow()
                rack.updated_at = rack.created_at
                await self.session.flush()
                result.created += 1
                await self.session.commit()
                await self._invalidate_room_cache(room.id)
            except Exception as exc:  # 唯一约束 / 其它 DB 异常 → 仅该条失败
                await self.session.rollback()
                reason = (
                    "机柜编号重复（同机房同列同号）或数据不合法"
                    if isinstance(exc, IntegrityError)
                    else (str(exc) or "创建失败")[:200]
                )
                result.failures.append(ImportFailure(row=row, errors=[reason]))
        result.failed = len(result.failures)
        return result

    async def _assign_grid(self, data: RackCreate, rack: Rack) -> None:
        """为新机柜自动分配平面图网格坐标（若未显式指定）。

        规则：同列编号(column_code)归同一行(grid_row)，行内按机柜编号(code)顺序
        排到下一列(grid_col)；新列编号则另起一行。与 3D 自动布局、2D 平面图
        默认排列保持一致。
        """
        if data.grid_row is not None and data.grid_col is not None:
            rack.grid_row = data.grid_row
            rack.grid_col = data.grid_col
            return
        existing = await self.rack_repo.list_by_room(rack.room_id)
        other = [r for r in existing if r.id != rack.id]
        col_codes = sorted({r.column_code for r in other})
        if data.column_code in {r.column_code for r in other}:
            ridx = col_codes.index(data.column_code)
            members = [r for r in other if r.column_code == data.column_code]
            cols = [r.grid_col for r in members if r.grid_col is not None]
            max_col = max(cols) if cols else -1
            rack.grid_row = ridx
            rack.grid_col = max_col + 1
        else:
            rows = [r.grid_row for r in other if r.grid_row is not None]
            max_row = max(rows) if rows else -1
            rack.grid_row = max_row + 1
            rack.grid_col = 0

    async def get_rack(self, rack_id: str) -> Rack:
        rack = await self.rack_repo.get(rack_id)
        if rack is None:
            raise NotFoundError("机柜不存在")
        return rack

    async def list_racks(self, room_id: str) -> list[Rack]:
        return await self.rack_repo.list_by_room(room_id)

    async def list_filtered(
        self,
        *,
        room_id: Optional[str] = None,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        size: int = 200,
    ) -> tuple[list[RackListItem], int]:
        """机柜管理列表（带机房名称），支持按机房 / 关键字 / 状态过滤与分页。"""
        return await self.rack_repo.list_filtered(
            room_id=room_id, keyword=keyword, status=status, page=page, size=size
        )

    async def update_rack(self, rack_id: str, data: RackUpdate) -> Rack:
        rack = await self.get_rack(rack_id)
        if (data.column_code is not None and data.column_code != rack.column_code) or (
            data.code is not None and data.code != rack.code
        ):
            new_col = data.column_code or rack.column_code
            new_code = data.code or rack.code
            if await self.rack_repo.exists_code(
                rack.room_id, new_col, new_code, rack.id
            ):
                raise ConflictError(
                    f"机柜编号「{new_code}」在列「{new_col}」内已存在"
                )
        rack = await self.rack_repo.update(rack, data)
        if data.name is None and rack.name in (None, ""):
            rack.name = f"{rack.column_code}-{rack.code}"
        await self.session.commit()
        await self.session.refresh(rack)
        await self._invalidate_room_cache(rack.room_id)
        return rack

    # --------------------------------------------------- 平面图坐标批量更新
    async def update_positions(self, positions: list[dict]) -> None:
        """批量写入机柜网格坐标（2D 平面图拖拽持久化）。"""
        await self.rack_repo.update_positions(positions)
        await self.session.commit()

    async def delete_rack(self, rack_id: str) -> None:
        rack = await self.get_rack(rack_id)
        # 机柜内仍有有效上架设备则禁止删除（需先下架）。
        active = await self.mount_repo.list_active_in_rack(rack.id)
        if active:
            raise ConflictError(f"机柜内还有 {len(active)} 台已上架设备，无法删除")
        await self.rack_repo.delete(rack)
        await self.session.commit()
        await self._invalidate_room_cache(rack.room_id)

    # ----------------------------------------------------- 容量重算（仅 used_u）
    async def recalculate_rack_usage(self, rack_id: str) -> None:
        """重算机柜 used_u（按有效上架记录 occupied_u 求和）。"""
        rack = await self.rack_repo.get(rack_id)
        if rack is None:
            return
        total_used = await self.mount_repo.sum_occupied_u_in_rack(rack_id)
        rack.used_u = total_used
        await self.session.flush()
        await self.session.commit()
        await self._invalidate_room_cache(rack.room_id)

    # ------------------------------------------------------------ 设备上架 / 下架
    async def mount_device(
        self,
        rack_id: str,
        device_id: str,
        start_u: int,
        mounted_by: Optional[str] = None,
    ) -> None:
        """将设备挂载到机柜指定 U 位，写入上架记录并同步设备状态为「已上架」。"""
        rack = await self.get_rack(rack_id)
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        # 已存在有效上架记录 → 需先下架。
        existing = await self.mount_repo.get_active_by_device(device.id)
        if existing is not None:
            raise ConflictError("设备已在机柜中上架，请先下架再重新上架")
        size_u = device.u_height or 1
        # U 位冲突校验（排除设备自身，允许在同一机柜内重新摆放）。
        conflict = await DeviceService(self.session, self.cache).check_u_conflict(
            rack_id, start_u, size_u, exclude_device_id=device.id
        )
        if conflict.get("conflict"):
            msg = conflict.get("error") or (
                f"U 位冲突：U{conflict.get('conflict_u')} 已被设备"
                f"「{conflict.get('conflict_device')}」占用"
            )
            raise ConflictError(msg)
        await self.mount_repo.create(
            device_id=device.id,
            room_id=rack.room_id,
            rack_id=rack.id,
            start_u=start_u,
            occupied_u=size_u,
            mounted_by=mounted_by,
        )
        device.status = DeviceStatus.MOUNTED.value  # 上架 → 已上架
        await self.session.flush()
        await self.recalculate_rack_usage(rack.id)

    async def unmount_device(
        self,
        rack_id: str,
        device_id: str,
        unmounted_by: Optional[str] = None,
    ) -> None:
        """将设备从机柜下架：有效记录置「已下架」并填下架信息，设备状态退回「在库」。

        下架即把设备放回资产池（在库），不再保留独立的「已下架」生命周期终态；
        本次下架操作本身由 ``mount_records`` 中记录状态=「已下架」保留以作追溯。
        """
        rack = await self.get_rack(rack_id)
        device = await self.device_repo.get(device_id)
        if device is None:
            raise NotFoundError("设备不存在")
        active = await self.mount_repo.get_active_by_device(device.id)
        if active is None or active.rack_id != rack.id:
            raise ConflictError("该设备并不在此机柜内")
        await self.mount_repo.set_unmounted(
            active, unmounted_at=utcnow(), unmounted_by=unmounted_by
        )
        device.status = DeviceStatus.IN_STOCK.value  # 下架 → 退回在库（资产池）
        await self.session.flush()
        await self.recalculate_rack_usage(rack.id)

    async def list_candidate_devices(self) -> list:
        """候选上架设备：无有效上架记录的设备（仓库 / 已下架 / 待报废候选池）。"""
        return await self.mount_repo.list_unmounted_devices()

    # --------------------------------------------------------------- 缓存失效
    async def _invalidate_room_cache(self, room_id: str) -> None:
        await self.cache.delete_prefix(f"room_stats:{room_id}")
        await self.cache.delete_prefix(f"dashboard:{room_id}")
