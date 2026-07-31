"""操作日志 / 登录日志仓储（纯 DB 读写）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.login_log import LoginLog
from app.models.operation_log import OperationLog


def _shanghai_day_start_utc(value: str) -> Optional[datetime]:
    """将 ``YYYY-MM-DD`` 解析为「上海当日 0 点」对应的 UTC 起点。

    日志时间以 UTC 落库、前端按 Asia/Shanghai 展示；为让时间筛选与用户看到的
    日期一致，把所选日期当作上海本地日换算成 UTC 端点。上海固定 UTC+8 无夏令时，
    直接偏移 8 小时即可，避免 zoneinfo 依赖。
    """
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    return d - timedelta(hours=8)


def _shanghai_day_end_utc(value: str) -> Optional[datetime]:
    """上海当日 23:59:59 对应的 UTC 终点。"""
    start = _shanghai_day_start_utc(value)
    if start is None:
        return None
    return start + timedelta(hours=23, minutes=59, seconds=59)


def _time_range_conds(column, start_time: Optional[str], end_time: Optional[str]) -> list:
    conds = []
    if start_time:
        start_utc = _shanghai_day_start_utc(start_time)
        if start_utc is not None:
            conds.append(column >= start_utc)
    if end_time:
        end_utc = _shanghai_day_end_utc(end_time)
        if end_utc is not None:
            conds.append(column <= end_utc)
    return conds


async def _paginate(session: AsyncSession, model, conds, page: int, size: int):
    stmt = select(model)
    count_stmt = select(func.count()).select_from(model)
    if conds:
        stmt = stmt.where(*conds)
        count_stmt = count_stmt.where(*conds)
    total = (await session.execute(count_stmt)).scalar() or 0
    items = (
        await session.execute(
            stmt.order_by(model.created_at.desc()).offset((page - 1) * size).limit(size)
        )
    ).scalars().all()
    return list(items), total


async def delete_logs_before(session: AsyncSession, cutoff: datetime) -> tuple[int, int]:
    """硬删 ``created_at < cutoff`` 的操作日志与登录日志。

    - 审计日志只增不减、到期即清，不做软删（删除留痕靠 operation_logs +
      login_logs 自身的「新增」记录，以及日后归档，而非保留已过期行）。
    - 函数内部自行 commit；调用方无需再提交。
    - 返回 ``(operation_logs_deleted, login_logs_deleted)``，任一表被异常跳过时
      对应计数为 0，绝不因单表失败抛错中断清理。
    """
    op_deleted = 0
    login_deleted = 0
    try:
        op_result = await session.execute(
            delete(OperationLog).where(OperationLog.created_at < cutoff)
        )
        op_deleted = op_result.rowcount or 0
    except Exception:
        # 单表失败不影响另一表清理；异常上抛前记录日志由调用方决定。
        raise
    try:
        login_result = await session.execute(
            delete(LoginLog).where(LoginLog.created_at < cutoff)
        )
        login_deleted = login_result.rowcount or 0
    except Exception:
        raise
    await session.commit()
    return op_deleted, login_deleted


class OperationLogRepository:
    """操作日志表的查询。写入由中间件直接完成，无需仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        *,
        page: int = 1,
        size: int = 20,
        action: Optional[str] = None,
        keyword: Optional[str] = None,
        status_code: Optional[int] = None,
        resource: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ):
        conds = []
        if action:
            # 操作动作归一化键：create/update/delete（对应新增 / 更新 / 删除三态）。
            conds.append(OperationLog.action == action)
        if keyword:
            kw = f"%{keyword}%"
            conds.append(
                (OperationLog.path.ilike(kw))
                | (OperationLog.operator_name.ilike(kw))
                | (OperationLog.target.ilike(kw))
            )
        if status_code is not None:
            conds.append(OperationLog.status_code == status_code)
        if resource:
            conds.append(OperationLog.resource == resource)
        conds += _time_range_conds(OperationLog.created_at, start_time, end_time)
        return await _paginate(self.session, OperationLog, conds, page, size)


class LoginLogRepository:
    """登录日志表的查询。写入由认证端点完成。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        *,
        page: int = 1,
        size: int = 20,
        action: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ):
        conds = []
        if action:
            conds.append(LoginLog.action == action)
        if status:
            conds.append(LoginLog.status == status)
        if keyword:
            kw = f"%{keyword}%"
            conds.append((LoginLog.username.ilike(kw)) | (LoginLog.ip.ilike(kw)))
        conds += _time_range_conds(LoginLog.created_at, start_time, end_time)
        return await _paginate(self.session, LoginLog, conds, page, size)
