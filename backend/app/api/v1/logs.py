"""日志路由（只读，受 account:view 保护）。

- ``GET /logs/operations``：请求级操作日志（中间件自动写入）。
- ``GET /logs/logins``：登录 / 注销日志（认证端点写入）。
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import utcnow
from app.core.deps import get_db
from app.core.rbac import require_permission
from app.repositories.log_repo import (
    LoginLogRepository,
    OperationLogRepository,
    delete_logs_before,
)
from app.schemas.common import ok, paginated
from app.schemas.log import LoginLogOut, LogCleanupIn, OperationLogOut

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/operations", dependencies=[Depends(require_permission("account:view"))])
async def list_operation_logs(
    db: AsyncSession = Depends(get_db),
    action: Optional[str] = None,
    keyword: Optional[str] = None,
    status_code: Optional[int] = None,
    resource: Optional[str] = None,
    start_time: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD（含当日，按上海展示时区）"),
    end_time: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD（含当日，按上海展示时区）"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    repo = OperationLogRepository(db)
    items, total = await repo.list(
        page=page,
        size=size,
        action=action,
        keyword=keyword,
        status_code=status_code,
        resource=resource,
        start_time=start_time,
        end_time=end_time,
    )
    # 直接按属性构造出参，避免 ORM 的 detail 文本被当成 dict 自动校验；
    # 显式把 JSON 文本解析为 dict 注入 detail 字段。
    items_out = [
        OperationLogOut(
            id=r.id,
            operator_id=r.operator_id,
            operator_name=r.operator_name,
            method=r.method,
            path=r.path,
            resource=r.resource,
            action=r.action,
            target=r.target,
            status_code=r.status_code,
            ip=r.ip,
            detail=_parse_detail(r.detail),
            created_at=r.created_at,
        ).model_dump(mode="json")
        for r in items
    ]
    return paginated(items_out, total, page, size)


def _parse_detail(raw: Optional[str]) -> Optional[dict]:
    """把 operation_logs.detail 文本解析回 dict（解析失败返回 None，绝不抛错）。"""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


@router.get("/logins", dependencies=[Depends(require_permission("account:view"))])
async def list_login_logs(
    db: AsyncSession = Depends(get_db),
    action: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    start_time: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD（含当日，按上海展示时区）"),
    end_time: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD（含当日，按上海展示时区）"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    repo = LoginLogRepository(db)
    items, total = await repo.list(
        page=page,
        size=size,
        action=action,
        status=status,
        keyword=keyword,
        start_time=start_time,
        end_time=end_time,
    )
    return paginated(
        [LoginLogOut.model_validate(r).model_dump(mode="json") for r in items],
        total,
        page,
        size,
    )


@router.post("/cleanup", dependencies=[Depends(require_permission("account:view"))])
async def cleanup_logs(
    body: LogCleanupIn,
    db: AsyncSession = Depends(get_db),
):
    """手动清理超过保留期的日志（受 account:view 保护）。

    - 默认按配置 ``LOG_RETENTION_DAYS`` 计算 cutoff；``body.days`` 可临时覆盖。
    - cutoff = 当前 UTC - 保留天数；删除两表 ``created_at < cutoff`` 的过期行。
    - 返回被删条数与 cutoff，便于运维立即回收 / 验证，也便于自动化测试。
    """
    retention_days = body.days if body.days is not None else settings.LOG_RETENTION_DAYS
    # R-05：datetime.utcnow() 在 3.12+ 已弃用，统一走 app.core.database.utcnow
    # （naive UTC，与 created_at 列存储口径一致——差 8 小时会误删/漏删）。
    cutoff = utcnow() - timedelta(days=retention_days)
    op_deleted, login_deleted = await delete_logs_before(db, cutoff)
    return ok(
        {
            "operation_logs_deleted": op_deleted,
            "login_logs_deleted": login_deleted,
            "cutoff": cutoff.isoformat(),
            "retention_days": retention_days,
        }
    )
