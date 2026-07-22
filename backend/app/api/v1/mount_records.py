"""上架记录路由：列表（集中管理页）/ 编辑 / 删除（追溯字段维护）。

U 位 / 占用 U 数不在此处修改，调整设备 U 位请先下架再重新上架
（已移除原 PUT /racks/{rack_id}/mount 原地改位接口）。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.rbac import require_permission
from app.schemas.common import ok, paginated
from app.schemas.mount_record import MountRecordUpdate
from app.services.device_service import DeviceService

router = APIRouter(prefix="/mount-records", tags=["mount-records"])


@router.get("", dependencies=[Depends(require_permission("device:view"))])
async def list_mount_records(
    device_name: str | None = Query(default=None, description="设备名称（模糊）"),
    device_code: str | None = Query(default=None, description="设备编号（模糊）"),
    op_type: str | None = Query(default=None, description="操作类型：上架 / 下架"),
    start_time: datetime | None = Query(default=None, description="操作时间起始（ISO8601）"),
    end_time: datetime | None = Query(default=None, description="操作时间截止（ISO8601）"),
    export: bool = Query(default=False, description="为 true 时返回全量（不分页），供前端导出"),
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=200, description="每页条数"),
    db: AsyncSession = Depends(get_db),
):
    """全局上下架记录列表（集中管理页）。

    筛选：设备名称 / 设备编号（模糊）、操作类型（上架 / 下架）、操作时间范围。
    export=true 时忽略分页，返回全部匹配记录（用于前端 Excel 导出）。
    数据来源与设备详情页完全一致（同一 MountRecord 表 + 同一事件展开逻辑）。
    """
    events = await DeviceService(db).list_mount_events(
        device_name=device_name,
        device_code=device_code,
        op_type=op_type,
        start_time=start_time,
        end_time=end_time,
    )
    total = len(events)
    if export:
        return ok(events)
    start = (page - 1) * size
    paged = events[start : start + size]
    return paginated(paged, total, page, size)


@router.patch("/{record_id}", dependencies=[Depends(require_permission("device:edit"))])
async def update_mount_record(
    record_id: int, payload: MountRecordUpdate, db: AsyncSession = Depends(get_db)
):
    """编辑上架记录（上架人 / 下架人）。"""
    svc = DeviceService(db)
    rid = await svc.update_mount_record(record_id, payload)
    return ok({"id": rid})


@router.delete("/{record_id}", dependencies=[Depends(require_permission("device:edit"))])
async def delete_mount_record(record_id: int, db: AsyncSession = Depends(get_db)):
    """删除一条上架记录（二次确认由前端完成）。"""
    svc = DeviceService(db)
    await svc.delete_mount_record(record_id)
    return ok()
