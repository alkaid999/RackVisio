"""审计日志仓储（纯 DB 读写）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


def _parse_shanghai_date(value: str) -> Optional[datetime]:
    """将 ``YYYY-MM-DD`` 解析为「上海当日 0 点」对应的 UTC 起点。

    审计时间以 UTC 落库、前端按 Asia/Shanghai 展示；为让时间筛选与用户看到的
    日期一致，这里把所选日期当作上海本地日，换算成对应的 UTC 区间端点。
    上海固定 UTC+8 且无夏令时，故直接偏移 8 小时即可，避免 zoneinfo 依赖。
    """
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    # 上海 00:00:00 == UTC 前一日 16:00:00
    start_utc = d - timedelta(hours=8)
    return start_utc


class AuditLogRepository:
    """审计日志表的读写操作。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def list(
        self,
        *,
        page: int = 1,
        size: int = 20,
        module: Optional[str] = None,
        action: Optional[str] = None,
        keyword: Optional[str] = None,
        operator: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ):
        conds = []
        if module:
            conds.append(AuditLog.module == module)
        if action:
            conds.append(AuditLog.action == action)
        if operator:
            conds.append(AuditLog.operator_name.ilike(f"%{operator}%"))
        if keyword:
            kw = f"%{keyword}%"
            conds.append(
                (AuditLog.object_name.ilike(kw))
                | (AuditLog.detail.ilike(kw))
                | (AuditLog.operator_name.ilike(kw))
            )
        # 时间范围：按上海展示日换算 UTC 区间（含端点当日全天）。
        if start_time:
            start_utc = _parse_shanghai_date(start_time)
            if start_utc is not None:
                conds.append(AuditLog.created_at >= start_utc)
        if end_time:
            # 上海当日 23:59:59 == UTC 当日 15:59:59
            end_utc = _parse_shanghai_date(end_time)
            if end_utc is not None:
                end_utc = datetime(end_utc.year, end_utc.month, end_utc.day, 23, 59, 59) - timedelta(hours=8)
                conds.append(AuditLog.created_at <= end_utc)
        stmt = select(AuditLog)
        count_stmt = select(func.count()).select_from(AuditLog)
        if conds:
            stmt = stmt.where(*conds)
            count_stmt = count_stmt.where(*conds)
        total = (await self.session.execute(count_stmt)).scalar() or 0
        items = (
            await self.session.execute(
                stmt.order_by(AuditLog.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).scalars().all()
        return list(items), total
