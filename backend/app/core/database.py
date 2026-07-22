"""异步数据库引擎、会话工厂与声明式基类。

- 引擎按 ``DATABASE_URL`` scheme 自动选择驱动（aiosqlite / asyncpg）。
- 模型主键统一使用 ``String(36)`` 存储 UUID 字符串（详见架构文档 §1.2）。
- 建表使用 ``Base.metadata.create_all``（本期省略 Alembic）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def utcnow() -> datetime:
    """返回当前 UTC 时间（naive，统一存 UTC）。

    使用 ``datetime.now(timezone.utc).replace(tzinfo=None)`` 避免 Python 3.12+
    对 ``datetime.utcnow()`` 的弃用告警，同时保持跨库一致的 naive UTC 行为。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。"""


def _create_engine():
    """根据 DATABASE_URL 创建异步引擎。

    - SQLite（含 ``:memory:``）使用 ``StaticPool`` 与 ``check_same_thread=False``，
      保证单个内存库连接被会话共享。
    - 其他（PostgreSQL）使用默认连接池。
    """
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        kwargs: dict = {"echo": False, "future": True}
        connect_args: dict = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = connect_args
        return create_async_engine(url, **kwargs)
    return create_async_engine(url, echo=False, future=True)


# 模块级引擎与会话工厂单例。
engine = _create_engine()
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """FastAPI 依赖：提供一个异步 DB 会话（用完自动关闭）。"""
    async with async_session_factory() as session:
        yield session


async def init_models() -> None:
    """创建所有表（若尚未存在）。"""
    # 导入所有模型以确保元数据被登记。
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
