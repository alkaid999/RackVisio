"""FastAPI 依赖注入：数据库会话与缓存。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.core.database import async_session_factory


async def get_db() -> AsyncSession:
    """提供请求作用域的异步数据库会话。

    会话在整个请求期间复用，异常退出时自动关闭并回滚未提交事务。
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def get_cache() -> Cache:
    """提供缓存单例实例。"""
    return Cache()
