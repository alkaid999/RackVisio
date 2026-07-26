"""审计日志仓储（纯 DB 读写）。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


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
