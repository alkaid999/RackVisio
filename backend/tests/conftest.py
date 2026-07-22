"""pytest 配置与 fixtures。

- 在导入 app 之前设置 ``DATABASE_URL`` 指向临时 SQLite 库（避免污染 ./idc.db）。
- 每个测试前清空缓存并重建表 + 写入种子数据，保证用例间相互独立。
- 提供异步 httpx 客户端访问 /api/v1。
"""

from __future__ import annotations

import os
import sys
import tempfile

# 将 backend/ 加入 sys.path，确保 `from app...` 可被 pytest 解析。
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# 必须在导入 app 之前设置环境变量，使模块级引擎使用临时库。
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB_PATH = _TMP_DB.name
_TMP_DB.close()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH}"
os.environ["REDIS_ENABLED"] = "false"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.cache import cache  # noqa: E402
from app.core.database import Base, async_session_factory, engine, init_models  # noqa: E402
from app.db.init_db import seed_data  # noqa: E402
from main import app  # noqa: E402  (应用入口在 backend/main.py，模块名为 main)


@pytest.fixture(autouse=True)
async def setup_database():
    """每个测试前清空缓存、重建表并写入种子数据。"""
    await cache.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await seed_data(session)
        await session.commit()
    yield


@pytest.fixture
async def client():
    """异步测试客户端（不触发 lifespan，建表由 setup_database 负责）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def get_seeded_room_id(ac: AsyncClient) -> str:
    """辅助：从种子数据中取机房 id。"""
    resp = await ac.get("/api/v1/rooms")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    return items[0]["id"]


async def get_rack_id_by_code(ac: AsyncClient, room_id: str, code: str) -> str:
    """辅助：按 code 取机柜 id。"""
    resp = await ac.get(f"/api/v1/rooms/{room_id}/racks")
    assert resp.status_code == 200
    for r in resp.json()["data"]:
        if r["code"] == code:
            return r["id"]
    raise AssertionError(f"rack {code} not found")
