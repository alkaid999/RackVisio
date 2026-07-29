"""操作审计日志路由（只读接口，受 account:view 保护）。

审计日志面向系统管理员 / 具备账号查看权限的用户，用于追溯
「谁改了什么 / 导入导出记录」。写入由业务接口通过 ``app.core.audit.log_audit`` 完成。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.rbac import require_permission
from app.repositories.audit_log_repo import AuditLogRepository
from app.schemas.audit import AuditLogOut
from app.schemas.common import paginated

router = APIRouter(prefix="/audit-logs", tags=["audit"])

# 前端筛选下拉用的模块 / 操作枚举（与写日志时保持一致语义）。
AUDIT_MODULES = [
    "room",
    "rack",
    "device",
    "account",
    "link",
    "consumable",
    "import",
    "export",
    "system",
]
AUDIT_ACTIONS = ["create", "update", "delete", "restore", "purge", "import", "export", "login"]


@router.get("", dependencies=[Depends(require_permission("account:view"))])
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    module: Optional[str] = None,
    action: Optional[str] = None,
    keyword: Optional[str] = None,
    operator: Optional[str] = None,
    start_time: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD（含当日，按上海展示时区）"),
    end_time: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD（含当日，按上海展示时区）"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    repo = AuditLogRepository(db)
    items, total = await repo.list(
        page=page,
        size=size,
        module=module,
        action=action,
        keyword=keyword,
        operator=operator,
        start_time=start_time,
        end_time=end_time,
    )
    return paginated(
        [AuditLogOut.model_validate(r).model_dump(mode="json") for r in items],
        total,
        page,
        size,
    )


@router.get("/meta", dependencies=[Depends(require_permission("account:view"))])
async def audit_meta():
    """返回模块 / 操作枚举，供前端筛选下拉使用。"""
    return {"code": 0, "message": "ok", "data": {"modules": AUDIT_MODULES, "actions": AUDIT_ACTIONS}}
