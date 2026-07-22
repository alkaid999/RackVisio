"""可选缓存抽象层（架构文档 §1.1 / §8）。

- ``REDIS_ENABLED=false``（默认）：使用进程内字典（带 TTL），零外部依赖即可跑通。
- ``REDIS_ENABLED=true``：使用 Redis（lazy import，避免未安装时阻塞）。
- 缓存键约定：``room_stats:{room_id}``、``dashboard:{room_id}``。
- 设备/机柜变更时通过 ``delete`` / ``delete_prefix`` 主动失效。

所有方法均为 ``async``，以统一内存 / Redis 两种后端的调用方式。
后端实例为模块级单例，确保全应用共享同一份缓存。
"""

from __future__ import annotations

import time
from typing import Any, Optional

from app.core.config import settings


class InMemoryCache:
    """进程内缓存（带 TTL）。"""

    def __init__(self) -> None:
        # 存储结构：key -> (expire_at_epoch, value)
        self._store: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if item is None:
            return None
        expire_at, value = item
        if expire_at > time.time():
            return value
        del self._store[key]
        return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        self._store[key] = (time.time() + ttl, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_prefix(self, prefix: str) -> None:
        for k in list(self._store.keys()):
            if k.startswith(prefix):
                del self._store[k]

    async def clear(self) -> None:
        self._store.clear()


class RedisCache:
    """Redis 缓存后端（lazy import redis，避免未安装时阻塞）。"""

    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(url, decode_responses=False)

    async def get(self, key: str) -> Optional[Any]:
        return await self._client.get(key)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        await self._client.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def delete_prefix(self, prefix: str) -> None:
        async for key in self._client.scan_iter(match=f"{prefix}*"):
            await self._client.delete(key)

    async def clear(self) -> None:
        await self._client.flushdb()


# 模块级单例后端，全应用共享同一份缓存。
_backend: Any = None


def _get_backend() -> Any:
    """惰性创建并返回缓存后端单例。"""
    global _backend
    if _backend is None:
        if settings.REDIS_ENABLED:
            try:
                _backend = RedisCache(settings.REDIS_URL)
            except Exception:
                # 任何 Redis 连接/导入问题都回退到内存缓存，保证沙箱可跑通。
                _backend = InMemoryCache()
        else:
            _backend = InMemoryCache()
    return _backend


class Cache:
    """缓存门面，按配置在内存 / Redis 之间切换。

    使用方式：::

        cache = Cache()
        await cache.set("dashboard:123", payload, ttl=30)
        payload = await cache.get("dashboard:123")
        await cache.delete_prefix("room_stats:")
    """

    async def get(self, key: str) -> Optional[Any]:
        return await _get_backend().get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else settings.CACHE_TTL
        await _get_backend().set(key, value, ttl)

    async def delete(self, key: str) -> None:
        await _get_backend().delete(key)

    async def delete_prefix(self, prefix: str) -> None:
        await _get_backend().delete_prefix(prefix)

    async def clear(self) -> None:
        await _get_backend().clear()


# 全局缓存单例，供服务层直接引用。
cache = Cache()
