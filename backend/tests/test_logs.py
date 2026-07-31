"""原生日志回归测试。

覆盖重构后的两类日志（#675）：
- 操作日志（operation_logs）：写请求由中间件自动留痕（谁/方法/路径/状态码/IP），
  GET 读请求与 /auth/* 认证域不留痕。
- 登录日志（login_logs）：登录成功 / 登录失败 / 注销由认证端点写入。
- 种子 / 建表阶段（无 HTTP 请求）不产生任何日志。
- 日志清理（#696）：保留期过期行被硬删，保留期内行不动；手动 /logs/cleanup 与
  repo.delete_logs_before 均按 cutoff 精确删除。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.database import async_session_factory
from app.models.login_log import LoginLog
from app.models.operation_log import OperationLog
from app.repositories.log_repo import delete_logs_before


async def _seed_old_logs(n_op: int, n_login: int, days_ago: int) -> None:
    """辅助：直接写入过期日志行（created_at 前移到 days_ago 天前）。

    用以验证清理函数只删 ``created_at < cutoff`` 的过期行，保留期内的行不动。
    """
    base = datetime.utcnow() - timedelta(days=days_ago)
    async with async_session_factory() as session:
        for i in range(n_op):
            session.add(
                OperationLog(
                    operator_id="00000000-0000-0000-0000-000000000000",
                    operator_name="oldadmin",
                    method="POST",
                    path="/api/v1/rooms",
                    resource="room",
                    action="create",
                    target=f"old-room-{i}",
                    status_code=200,
                    ip="127.0.0.1",
                    created_at=base,
                )
            )
        for i in range(n_login):
            session.add(
                LoginLog(
                    username="oldadmin",
                    action="login",
                    status="success",
                    ip="127.0.0.1",
                    created_at=base,
                )
            )
        await session.commit()


async def _op_logs(ac, **params):
    resp = await ac.get("/api/v1/logs/operations", params={"size": 200, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["items"]


async def _login_logs(ac, **params):
    resp = await ac.get("/api/v1/logs/logins", params={"size": 200, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["items"]


async def test_write_request_logged(client):
    """写请求（POST 创建机房）自动落一条操作日志，含操作人/方法/路径/状态码。"""
    resp = await client.post(
        "/api/v1/rooms", json={"name": "日志机房", "code": "LOG-01"}
    )
    assert resp.status_code == 200, resp.text

    items = await _op_logs(client)
    hits = [i for i in items if i["method"] == "POST" and i["path"] == "/api/v1/rooms"]
    assert hits, "POST /rooms 应自动产生操作日志"
    log = hits[0]
    assert log["operator_name"] == "admin"
    assert log["status_code"] == 200
    assert log["operator_id"]


async def test_get_request_not_logged(client):
    """GET 读请求不产生操作日志（查询日志本身也是 GET，同样不留痕）。"""
    before = await _op_logs(client)
    await client.get("/api/v1/rooms")
    await client.get("/api/v1/stats/overview")
    after = await _op_logs(client)
    assert len(after) == len(before), "GET 请求不应产生操作日志"


async def test_failed_write_also_logged(client):
    """失败的写请求（422）同样留痕，状态码如实记录，便于追溯异常操作。"""
    resp = await client.post("/api/v1/rooms", json={"name": ""})  # 非法入参
    assert resp.status_code == 422
    items = await _op_logs(client)
    hits = [
        i
        for i in items
        if i["method"] == "POST" and i["path"] == "/api/v1/rooms" and i["status_code"] == 422
    ]
    assert hits, "失败写请求也应留痕（状态码 422）"


async def test_auth_paths_not_in_operation_logs(client):
    """/auth/* 认证域不进操作日志（由登录日志单独负责）。"""
    items = await _op_logs(client)
    assert not any(i["path"].startswith("/api/v1/auth") for i in items), (
        "认证域请求不应出现在操作日志中"
    )


async def test_login_success_and_failure_logged(client):
    """登录成功 / 失败均写入登录日志，注销亦留痕。"""
    # client fixture 已完成一次成功登录。
    items = await _login_logs(client)
    success = [i for i in items if i["action"] == "login" and i["status"] == "success"]
    assert success and success[0]["username"] == "admin"
    assert success[0]["user_id"]

    # 密码错误 → failed 记录（user_id 为空）。
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-pass"}
    )
    assert resp.status_code == 401
    items = await _login_logs(client, status="failed")
    assert items and items[0]["username"] == "admin"
    assert items[0]["user_id"] is None

    # 注销 → logout 记录（注销后令牌即失效，需重新登录后查询）。
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    relogin = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert relogin.status_code == 200
    client.headers["Authorization"] = f"Bearer {relogin.json()['data']['token']}"
    items = await _login_logs(client, action="logout")
    assert items and items[0]["username"] == "admin"


async def test_seed_produces_no_logs(client):
    """种子 / 建表阶段无 HTTP 请求，不产生任何操作日志。

    登录日志仅允许含 client fixture 登录产生的记录。
    """
    ops = await _op_logs(client)
    assert ops == [], "种子阶段不应产生操作日志"
    logins = await _login_logs(client)
    assert all(i["username"] == "admin" and i["action"] == "login" for i in logins)


async def test_room_crud_multiple_writes_logged(client):
    """连续写操作逐条留痕：创建→更新→删除机房产生 POST/PUT/DELETE 三条日志。"""
    created = await client.post(
        "/api/v1/rooms", json={"name": "crud 机房", "code": "LOG-02"}
    )
    assert created.status_code == 200, created.text
    room_id = created.json()["data"]["id"]

    upd = await client.put(f"/api/v1/rooms/{room_id}", json={"name": "crud 机房改"})
    assert upd.status_code == 200, upd.text
    dele = await client.delete(f"/api/v1/rooms/{room_id}")
    assert dele.status_code == 200, dele.text

    items = await _op_logs(client)
    methods = [i["method"] for i in items if "/api/v1/rooms" in i["path"]]
    assert methods.count("POST") >= 1
    assert methods.count("PUT") >= 1
    assert methods.count("DELETE") >= 1


async def test_write_request_captures_body_detail(client):
    """写请求（PUT 改机房名）的操作日志应抓取请求体到 detail.data。

    回归点：曾经因在 call_next 之后读 request.body() 导致 body 流已被内层消费，
    detail.data 恒为 None（所有编辑的「详情」都是空的）。修复后应在 call_next 之前读取。
    """
    created = await client.post(
        "/api/v1/rooms", json={"name": "抓包机房", "code": "CAP-03"}
    )
    assert created.status_code == 200, created.text
    room_id = created.json()["data"]["id"]

    upd = await client.put(f"/api/v1/rooms/{room_id}", json={"name": "抓包机房改"})
    assert upd.status_code == 200, upd.text

    items = await _op_logs(client)
    hit = next(
        (i for i in items if i["method"] == "PUT" and i["path"] == f"/api/v1/rooms/{room_id}"),
        None,
    )
    assert hit, "应产生 PUT /rooms/{id} 操作日志"
    assert hit["detail"], "detail 不应为空"
    assert hit["detail"]["data"], "detail.data 应含请求体"
    assert hit["detail"]["data"].get("name") == "抓包机房改"


# —— 日志清理回归（#696）：保留期过期行硬删，保留期内行不动 ——


async def test_cleanup_deletes_expired_only(client):
    """清理仅删过期行：保留期外的日志被硬删，保留期内的（如 admin 登录）仍在。"""
    await _seed_old_logs(3, 2, days_ago=200)  # 远超默认 180 天
    resp = await client.post("/api/v1/logs/cleanup", json={"days": 180})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["operation_logs_deleted"] == 3, data
    assert data["login_logs_deleted"] == 2, data
    # 过期行已清空，admin 当前登录日志保留。
    remaining_ops = await _op_logs(client)
    assert not any(i["operator_name"] == "oldadmin" for i in remaining_ops)
    remaining_logins = await _login_logs(client)
    assert any(i["username"] == "admin" for i in remaining_logins)


async def test_cleanup_default_uses_config_retention(client):
    """省略 days 时回退配置 LOG_RETENTION_DAYS（180）。"""
    await _seed_old_logs(1, 1, days_ago=400)  # 远超默认 180 天
    resp = await client.post("/api/v1/logs/cleanup", json={})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["operation_logs_deleted"] == 1, data
    assert data["login_logs_deleted"] == 1, data
    assert data["retention_days"] == 180, data


async def test_cleanup_zero_when_within_retention(client):
    """全部日志在保留期内时清理删除 0 条（用超长保留期验证不误删）。"""
    resp = await client.post("/api/v1/logs/cleanup", json={"days": 3650})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["operation_logs_deleted"] == 0, data
    assert data["login_logs_deleted"] == 0, data


async def test_cleanup_rejects_invalid_days(client):
    """days <= 0 被 Pydantic 拒绝，返回 422，避免误删全量日志。"""
    resp = await client.post("/api/v1/logs/cleanup", json={"days": 0})
    assert resp.status_code == 422, resp.text


async def test_cleanup_requires_permission():
    """未授权访问 /logs/cleanup 应被 401（AuthMiddleware 拦截）。"""
    from httpx import ASGITransport, AsyncClient

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/logs/cleanup", json={"days": 1})
        assert resp.status_code == 401, resp.text


async def test_delete_logs_before_function():
    """直接验证 repo 清理函数：硬删两表过期行、返回计数、库中确已无过期行。"""
    await _seed_old_logs(2, 3, days_ago=500)
    cutoff = datetime.utcnow() - timedelta(days=100)
    async with async_session_factory() as session:
        op_deleted, login_deleted = await delete_logs_before(session, cutoff)
    assert op_deleted == 2, (op_deleted, login_deleted)
    assert login_deleted == 3, (op_deleted, login_deleted)
    # 确认库中已无 oldadmin 的过期行。
    from sqlalchemy import func, select

    async with async_session_factory() as session:
        op_count = (
            await session.execute(
                select(func.count())
                .select_from(OperationLog)
                .where(OperationLog.operator_name == "oldadmin")
            )
        ).scalar() or 0
        login_count = (
            await session.execute(
                select(func.count())
                .select_from(LoginLog)
                .where(LoginLog.username == "oldadmin")
            )
        ).scalar() or 0
    assert op_count == 0, op_count
    assert login_count == 0, login_count


async def test_rack_positions_logged_as_update(client):
    """机柜平面图移动（POST /racks/positions 带 id）应记为「更新」而非「新增」，
    且操作对象解析为机柜名（#702）。此前机械按 HTTP 方法把 POST 记为 create，
    导致平面移动被误记为「新增」。"""
    room = await client.post("/api/v1/rooms", json={"name": "平面图机房", "code": "FP-01"})
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    rack = await client.post(
        f"/api/v1/rooms/{room_id}/racks",
        json={"code": "01", "column_code": "A"},
    )
    assert rack.status_code == 200, rack.text
    rack_id = rack.json()["data"]["id"]
    rack_name = rack.json()["data"]["name"]

    resp = await client.post(
        "/api/v1/racks/positions",
        json={"positions": [{"id": rack_id, "grid_row": 4, "grid_col": 0}]},
    )
    assert resp.status_code == 200, resp.text

    items = await _op_logs(client, keyword="racks/positions")
    pos_logs = [i for i in items if i["path"].endswith("/racks/positions")]
    assert pos_logs, "未记录平面图移动日志"
    log = pos_logs[0]
    assert log["action"] == "update", f"期望 update，实际 {log['action']}"
    assert log["target"] == rack_name, f"操作对象应解析为机柜名，实际 {log['target']!r}"
