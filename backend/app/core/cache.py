"""可选缓存抽象层（架构文档 §1.1 / §8）。

- ``REDIS_ENABLED``（默认 ``true``）：为 ``true`` 时使用 Redis（lazy import，避免未安装时阻塞）。
- 本地未装 / Redis 不可达时自动降级为进程内字典（带 TTL），零外部依赖即可跑通，接口正常返回。
- 缓存键约定：``room_stats:{room_id}``、``dashboard:{room_id}``。
- 设备/机柜变更时通过 ``delete`` / ``delete_prefix`` 主动失效。

所有方法均为 ``async``，以统一内存 / Redis 两种后端的调用方式。
后端实例为模块级单例，确保全应用共享同一份缓存。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger("cache")


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

        # 强制 RESP2 协议（protocol=2）：新版 redis-py(>=5) 默认连接时会发
        # `HELLO 3` 握手，但 Windows 原生 Redis（如 tporadowski/redis 5.0.x）
        # 低于 6.0 无 HELLO 命令，会握手失败并静默降级。RESP2 对所有
        # 6.0 之前的版本兼容，对 6.0+ 也向下兼容，故统一指定。
        self._client = aioredis.from_url(url, decode_responses=False, protocol=2)

    async def get(self, key: str) -> Optional[Any]:
        # 缓存读取失败降级为「未命中」（回源 DB），绝不冒泡影响业务。
        try:
            raw = await self._client.get(key)
            if raw is None:
                return None
            # 写入时统一 JSON 编码（见 set），此处解码还原原对象。
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                # 兜底：非 JSON 负载（理论上不会发生）原样返回。
                return raw
        except Exception:
            logger.warning("Redis get 失败（已降级回源）", exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            # 统一序列化为 JSON 字节：缓存值多为 dict/list 等结构化数据，
            # 直接传入 redis 客户端会因类型不支持而静默失败（序列化修复见提交 44a9a0e）。
            payload = json.dumps(value).encode("utf-8")
            await self._client.set(key, payload, ex=ttl)
        except Exception:
            logger.warning("Redis set 失败（已忽略）", exc_info=True)

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except Exception:
            logger.warning("Redis delete 失败（已忽略）", exc_info=True)

    async def delete_prefix(self, prefix: str) -> None:
        # 缓存失效为非关键操作：Redis 临时不可用时静默忽略，
        # 避免「事务已提交 + 缓存失效抛异常」导致接口 500 且审计漏记。
        try:
            async for key in self._client.scan_iter(match=f"{prefix}*"):
                await self._client.delete(key)
        except Exception:
            logger.warning("Redis delete_prefix 失败（已忽略）", exc_info=True)

    async def clear(self) -> None:
        try:
            await self._client.flushdb()
        except Exception:
            logger.warning("Redis clear 失败（已忽略）", exc_info=True)


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
        # 缓存读取失败降级为「未命中」（回源 DB），绝不冒泡影响业务。
        try:
            return await _get_backend().get(key)
        except Exception:
            logger.warning("cache get 失败（已降级回源）", exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else settings.CACHE_TTL
        try:
            await _get_backend().set(key, value, ttl)
        except Exception:
            logger.warning("cache set 失败（已忽略）", exc_info=True)

    async def delete(self, key: str) -> None:
        try:
            await _get_backend().delete(key)
        except Exception:
            logger.warning("cache delete 失败（已忽略）", exc_info=True)

    async def delete_prefix(self, prefix: str) -> None:
        # 缓存失效为非关键操作，失败静默（见 RedisCache.delete_prefix 说明）。
        try:
            await _get_backend().delete_prefix(prefix)
        except Exception:
            logger.warning("cache delete_prefix 失败（已忽略）", exc_info=True)

    async def clear(self) -> None:
        try:
            await _get_backend().clear()
        except Exception:
            logger.warning("cache clear 失败（已忽略）", exc_info=True)


# 全局缓存单例，供服务层直接引用。
cache = Cache()
