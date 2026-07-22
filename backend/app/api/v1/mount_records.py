"""上架记录路由：编辑 / 删除（追溯字段维护）。

U 位 / 占用 U 数不在此处修改，调整设备 U 位请先下架再重新上架
（已移除原 PUT /racks/{rack_id}/mount 原地改位接口）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.rbac import require_permission
from app.schemas.common import ok
from app.schemas.mount_record import MountRecordUpdate
from app.services.device_service import DeviceService

router = APIRouter(prefix="/mount-records", tags=["mount-records"])


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
