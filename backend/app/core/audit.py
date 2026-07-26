"""审计日志写入辅助。

在请求作用域外使用独立会话提交，确保审计写入与业务事务隔离：
业务失败回滚不影响审计落库，审计异常也不影响主流程（失败静默忽略）。
"""

from __future__ import annotations

import logging

from app.core.database import async_session_factory

logger = logging.getLogger("audit")


async def log_audit(
    *,
    module: str,
    action: str,
    request=None,
    object_type: str | None = None,
    object_id: str | None = None,
    object_name: str | None = None,
    detail: str | None = None,
) -> None:
    """记录一条审计日志（独立会话，失败静默）。

    ``request`` 用于解析操作人与来源 IP（JWT payload 的 ``sub`` / ``user_name``，
    以及 ``X-Forwarded-For`` 或直连 ``client.host``）。未传入 request 时操作人留空。
    """
    operator_id = None
    operator_name = None
    ip = None
    if request is not None:
        u = getattr(request.state, "user", None)
        if isinstance(u, dict):
            operator_id = u.get("sub")
            operator_name = u.get("user_name") or u.get("sub")
        client = getattr(request, "client", None)
        if client is not None and getattr(client, "host", None):
            fwd = request.headers.get("x-forwarded-for") if hasattr(request, "headers") else None
            ip = fwd.split(",")[0].strip() if fwd else client.host
    try:
        from app.models.audit_log import AuditLog

        async with async_session_factory() as s:
            s.add(
                AuditLog(
                    module=module,
                    action=action,
                    object_type=object_type,
                    object_id=object_id,
                    object_name=object_name,
                    operator_id=operator_id,
                    operator_name=operator_name,
                    detail=detail,
                    ip=ip,
                )
            )
            await s.commit()
    except Exception:
        logger.warning("审计日志写入失败（已忽略）", exc_info=True)
