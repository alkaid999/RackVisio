"""后端冒烟测试：覆盖健康、机房/机柜/设备/端口/链路/大屏关键路径。

所有用例依赖 conftest 的 ``setup_database``（每测试重建表 + 种子数据）与 ``client``。
种子数据仅含管理员 + 耗材类型，**无演示业务数据**；每个用例自建所需数据、互不依赖。
"""

from __future__ import annotations

from typing import Optional

from app.core.database import async_session_factory


# --------------------------------------------------------------------------- #
# 自包含数据构造辅助（不依赖种子业务数据）
# --------------------------------------------------------------------------- #
async def _create_room(client, code: str, name: Optional[str] = None) -> str:
    resp = await client.post(
        "/api/v1/rooms",
        json={
            "name": name or f"机房-{code}",
            "code": code,
            "area": "A",
            "building": "B",
            "floor": "2F",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _create_rack(
    client, room_id: str, code: str, total_u: int = 42, column_code: str = "A"
) -> str:
    resp = await client.post(
        f"/api/v1/rooms/{room_id}/racks",
        json={
            "code": code,
            "column_code": column_code,
            "total_u": total_u,
            "status": "可用",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _create_device(client, name: str, u_height: int = 1, **extra) -> str:
    payload: dict = {"name": name, "device_type": "server", "u_height": u_height}
    payload.update(extra)
    resp = await client.post("/api/v1/devices", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _mount(client, rack_id: str, device_id: str, start_u: int) -> None:
    """上架设备（占用 U 位 = 设备 u_height，由后端推导）。"""
    resp = await client.post(
        f"/api/v1/racks/{rack_id}/mount",
        json={"device_id": device_id, "start_u": start_u},
    )
    assert resp.status_code == 200, resp.text


# --------------------------------------------------------------------------- #
# 健康检查
# --------------------------------------------------------------------------- #
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    # 新契约：data.status 为 ok/degraded，并含 db/redis 依赖探活明细。
    assert body["data"]["status"] in ("ok", "degraded")
    assert body["data"]["db"]["ok"] is True
    assert "redis" in body["data"]


# --------------------------------------------------------------------------- #
# 机房 CRUD
# --------------------------------------------------------------------------- #
async def test_room_crud(client):
    # 创建（机房编号全局唯一，无 category / rows / cols 字段）
    resp = await client.post(
        "/api/v1/rooms",
        json={"name": "测试机房", "code": "ROOM-TEST", "area": "A", "building": "B", "floor": "2F"},
    )
    assert resp.status_code == 200, resp.text
    room = resp.json()["data"]
    assert room["code"] == "ROOM-TEST"
    room_id = room["id"]

    # 列表包含
    resp = await client.get("/api/v1/rooms", params={"name": "测试机房"})
    assert resp.status_code == 200
    codes = [r["code"] for r in resp.json()["data"]["items"]]
    assert "ROOM-TEST" in codes

    # 详情
    resp = await client.get(f"/api/v1/rooms/{room_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "测试机房"

    # 更新
    resp = await client.put(f"/api/v1/rooms/{room_id}", json={"name": "测试机房-改"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "测试机房-改"

    # 删除（机房删除为物理删除：清上架记录/机柜后删机房，删除后不可再查询到）
    resp = await client.delete(f"/api/v1/rooms/{room_id}")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/rooms/{room_id}")
    assert resp.status_code == 404
    assert resp.json()["code"] == 404


async def test_room_code_unique(client):
    # 先建一个机房
    resp = await client.post(
        "/api/v1/rooms", json={"name": "重复编号A", "code": "ROOM-DUP", "area": "A"}
    )
    assert resp.status_code == 200, resp.text
    # 再用同一编号创建 -> 409（种子不再预置机房数据，故显式创建）
    resp = await client.post(
        "/api/v1/rooms", json={"name": "重复编号B", "code": "ROOM-DUP", "area": "A"}
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == 409


# --------------------------------------------------------------------------- #
# 机柜 + 机房下机柜
# --------------------------------------------------------------------------- #
async def test_room_rack_endpoints(client):
    room_id = await _create_room(client, "ROOM-RE")
    # 在机房下创建 2 个机柜（无 row_num / col_num 字段）
    await _create_rack(client, room_id, "RE-R1", total_u=42)
    await _create_rack(client, room_id, "RE-R2", total_u=42)

    # 列表包含两者
    resp = await client.get(f"/api/v1/rooms/{room_id}/racks")
    assert resp.status_code == 200
    assert {r["code"] for r in resp.json()["data"]} >= {"RE-R1", "RE-R2"}

    # 容量统计
    resp = await client.get(f"/api/v1/rooms/{room_id}/stats")
    assert resp.status_code == 200
    stats = resp.json()["data"]
    assert stats["rack_count"] == 2


async def test_rack_detail_update_delete(client):
    room_id = await _create_room(client, "ROOM-RD")
    # r1：total_u=10，上架一台 u_height=10 占满 -> used_u=10，业务状态保持「可用」
    r1 = await _create_rack(client, room_id, "RD-R1", total_u=10)
    dev1 = await _create_device(client, "rd-dev1", u_height=10)
    await _mount(client, r1, dev1, 1)
    # r2：空机柜
    r2 = await _create_rack(client, room_id, "RD-R2", total_u=10)

    # 详情：used_u 已重算，业务状态为「可用」（容量状态由大屏另行计算）
    resp = await client.get(f"/api/v1/racks/{r1}")
    assert resp.status_code == 200
    assert resp.json()["data"]["used_u"] == 10
    assert resp.json()["data"]["status"] == "可用"

    # 更新
    resp = await client.put(f"/api/v1/racks/{r1}", json={"total_u": 12})
    assert resp.status_code == 200
    assert resp.json()["data"]["total_u"] == 12

    # 有设备的机柜禁止删除 -> 409
    resp = await client.delete(f"/api/v1/racks/{r1}")
    assert resp.status_code == 409

    # 空机柜可删除
    resp = await client.delete(f"/api/v1/racks/{r2}")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/racks/{r2}")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 设备：U 位冲突 + used_u 重算
# --------------------------------------------------------------------------- #
async def test_device_u_conflict_and_create(client):
    room_id = await _create_room(client, "ROOM-UCONF")
    rack_id = await _create_rack(client, room_id, "R-UCONF", total_u=42)
    # 先上架一台占 U1-20 的设备
    dev_a = await _create_device(client, "srv-occupied", u_height=20)
    await _mount(client, rack_id, dev_a, 1)

    # 冲突：在 U2 上架一台设备，与 U1-20 重叠 -> 409
    dev_conflict = await _create_device(client, "srv-conflict", u_height=1)
    r = await client.post(
        f"/api/v1/racks/{rack_id}/mount",
        json={"device_id": dev_conflict, "start_u": 2},
    )
    assert r.status_code == 409, r.text
    assert "冲突" in r.json()["message"]

    # 无冲突：在 U36 上架（u_height=2，占 U36-37）-> 200
    dev_ok = await _create_device(client, "srv-ok", u_height=2)
    r = await client.post(
        f"/api/v1/racks/{rack_id}/mount",
        json={"device_id": dev_ok, "start_u": 36},
    )
    assert r.status_code == 200, r.text
    resp = await client.get(f"/api/v1/devices/{dev_ok}")
    assert resp.status_code == 200
    assert resp.json()["data"]["current_start_u"] == 36


async def test_device_delete_recalculate(client):
    room_id = await _create_room(client, "ROOM-DELREC")
    rack_id = await _create_rack(client, room_id, "R-DELREC", total_u=42)
    dev1 = await _create_device(client, "srv-a", u_height=20)
    dev2 = await _create_device(client, "srv-b", u_height=15)
    await _mount(client, rack_id, dev1, 1)   # U1-20
    await _mount(client, rack_id, dev2, 21)  # U21-35

    before = (await client.get(f"/api/v1/racks/{rack_id}")).json()["data"]["used_u"]
    assert before == 35

    # 已上架设备禁止直接删除：先下架再删除，验证 used_u 重算
    resp = await client.post(
        f"/api/v1/racks/{rack_id}/unmount", json={"device_id": dev2}
    )
    assert resp.status_code == 200, resp.text
    resp = await client.delete(f"/api/v1/devices/{dev2}")
    assert resp.status_code == 200, resp.text

    after = (await client.get(f"/api/v1/racks/{rack_id}")).json()["data"]["used_u"]
    assert after == 20


async def test_device_u_map_and_check_u(client):
    room_id = await _create_room(client, "ROOM-UMAP")
    rack_id = await _create_rack(client, room_id, "R-UMAP", total_u=42)
    # 上架一台 u_height=20 的设备占 U1-20
    dev1 = await _create_device(client, "srv-umap-1", u_height=20)
    await _mount(client, rack_id, dev1, 1)

    # U 位图
    resp = await client.get(f"/api/v1/racks/{rack_id}/u-map")
    assert resp.status_code == 200
    umap = resp.json()["data"]
    assert umap["total_u"] == 42
    slot1 = next(s for s in umap["slots"] if s["u"] == 1)
    assert slot1["device_name"] == "srv-umap-1"

    # check-u：U2 被占（u_height=1 设备尝试放 U2）-> 冲突
    probe = await _create_device(client, "probe-conflict", u_height=1)
    resp = await client.post(
        f"/api/v1/racks/{rack_id}/check-u",
        json={"device_id": probe, "start_u": 2},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["conflict"] is True

    # check-u：U40 起放一台 u_height=2 的设备（U40-41）空闲 -> 不冲突
    probe2 = await _create_device(client, "probe-free", u_height=2)
    resp = await client.post(
        f"/api/v1/racks/{rack_id}/check-u",
        json={"device_id": probe2, "start_u": 40},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["conflict"] is False


# --------------------------------------------------------------------------- #
# 端口：创建 + 批量生成（新批量格式：groups 列表）
# --------------------------------------------------------------------------- #
async def test_port_crud_and_batch(client):
    room_id = await _create_room(client, "ROOM-PORT")
    rack_id = await _create_rack(client, room_id, "R-PORT")
    dev = await _create_device(client, "srv-port")
    await _mount(client, rack_id, dev, 1)

    # 创建接口
    resp = await client.post(
        f"/api/v1/devices/{dev}/interfaces",
        json={"name": "mgmt0", "interface_type": "rj45", "speed": "1G"},
    )
    assert resp.status_code == 201, resp.text

    # 同名冲突
    resp = await client.post(
        f"/api/v1/devices/{dev}/interfaces",
        json={"name": "mgmt0", "interface_type": "rj45"},
    )
    assert resp.status_code == 409

    # 批量生成（新格式：groups 列表）
    before = len((await client.get(f"/api/v1/devices/{dev}/interfaces")).json()["data"])
    resp = await client.post(
        f"/api/v1/devices/{dev}/interfaces/batch",
        json={"groups": [{"count": 3, "naming_pattern": "Gig%d"}]},
    )
    assert resp.status_code == 201, resp.text
    after = len((await client.get(f"/api/v1/devices/{dev}/interfaces")).json()["data"])
    assert after == before + 3


# --------------------------------------------------------------------------- #
# 链路：端口唯一性
# --------------------------------------------------------------------------- #
async def test_link_port_reuse_409(client):
    room_id = await _create_room(client, "ROOM-LINK")
    rack1 = await _create_rack(client, room_id, "R-LINK1")
    rack2 = await _create_rack(client, room_id, "R-LINK2")
    sw = await _create_device(client, "core-sw", device_type="switch")
    srv2 = await _create_device(client, "srv-02")
    await _mount(client, rack1, srv2, 1)  # 两端设备均需上架方可建链
    await _mount(client, rack2, sw, 1)

    # sw 建两个接口：Gig0/1、Gig0/2
    r = await client.post(
        f"/api/v1/devices/{sw}/interfaces", json={"name": "Gig0/1", "interface_type": "rj45"}
    )
    assert r.status_code == 201
    r = await client.post(
        f"/api/v1/devices/{sw}/interfaces", json={"name": "Gig0/2", "interface_type": "rj45"}
    )
    assert r.status_code == 201
    # srv2 建接口 eth0
    r = await client.post(
        f"/api/v1/devices/{srv2}/interfaces", json={"name": "eth0", "interface_type": "rj45"}
    )
    assert r.status_code == 201

    ifaces = (await client.get(f"/api/v1/devices/{sw}/interfaces")).json()["data"]
    src1 = next(p for p in ifaces if p["name"] == "Gig0/1")["id"]
    src2 = next(p for p in ifaces if p["name"] == "Gig0/2")["id"]
    tgt = next(
        p for p in (await client.get(f"/api/v1/devices/{srv2}/interfaces")).json()["data"]
        if p["name"] == "eth0"
    )["id"]

    # 创建新链路（成功）
    resp = await client.post(
        "/api/v1/links",
        json={
            "source_interface_id": src2,
            "target_interface_id": tgt,
            "medium": "tp",
            "connector_type": "cat5e",
        },
    )
    assert resp.status_code == 201, resp.text

    # 复用源接口 -> 409
    resp = await client.post(
        "/api/v1/links",
        json={
            "source_interface_id": src2,
            "target_interface_id": tgt,
            "medium": "tp",
            "connector_type": "cat5e",
        },
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == 409


# --------------------------------------------------------------------------- #
# 大屏（H1 修复：device_repo.list_by_room 缺失导致 500；H2：真实枚举统计）
# --------------------------------------------------------------------------- #
async def test_dashboard(client):
    # 构造机房 + 2 机柜 + 3 设备上架，校验大屏聚合。
    resp = await client.post(
        "/api/v1/rooms",
        json={"name": "大屏测试机房", "code": "ROOM-DASH", "area": "A", "building": "B", "floor": "2F"},
    )
    assert resp.status_code == 200, resp.text
    room_id = resp.json()["data"]["id"]

    # 创建 2 个机柜
    for code in ("RACK-D1", "RACK-D2"):
        r = await client.post(
            f"/api/v1/rooms/{room_id}/racks",
            json={"code": code, "column_code": "A", "total_u": 20, "status": "可用"},
        )
        assert r.status_code == 200, r.text

    # 创建 3 台设备（初始在库，上架后统一变为「已上架」）
    dev_ids = []
    for n in ("dash-srv-1", "dash-srv-2", "dash-srv-3"):
        d = await client.post(
            "/api/v1/devices",
            json={"name": n, "device_type": "server", "u_height": 1, "status": "在库"},
        )
        assert d.status_code == 201, d.text
        dev_ids.append(d.json()["data"]["id"])

    # 上架到两个机柜（mount 流程会把状态置为「已上架」）；错开 U 位避免同柜冲突
    racks = (await client.get(f"/api/v1/rooms/{room_id}/racks")).json()["data"]
    start_us = [1, 1, 2]  # dev3 落在与 dev1 不同的 U 位
    for idx, dev_id in enumerate(dev_ids):
        rack = racks[idx % len(racks)]
        m = await client.post(
            f"/api/v1/racks/{rack['id']}/mount",
            json={"device_id": dev_id, "start_u": start_us[idx]},
        )
        assert m.status_code == 200, m.text

    resp = await client.get(f"/api/v1/rooms/{room_id}/dashboard")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # H1 回归：接口不再 500（此前 device_repo 缺 list_by_room 导致 AttributeError）
    assert data["kpi"]["rack_count"] == 2
    assert data["kpi"]["device_count"] == 3
    # H2 回归：设备状态分布基于真实枚举（已上架），旧的 fault_count 已移除
    assert "fault_count" not in data["kpi"]
    assert data["device_status_distribution"]["mounted"] == 3
    assert data["device_status_distribution"]["in_stock"] == 0
    assert "rack_status_distribution" in data
    assert "device_status_distribution" in data


async def test_dashboard_distribution_real_statuses():
    """H2 回归：设备状态分布按真实 DeviceStatus 枚举（在库/已上架/已下架/待报废/借出）统计。

    直接构造 5 台不同状态且均带有效上架记录的设备（绕过 mount 流程对状态的强制覆盖），
    验证各分支计数正确、且旧字段（running/offline/fault/maintenance）已移除。
    """
    from app.core.cache import Cache
    from app.core.enums import DeviceStatus, RackBizStatus
    from app.repositories.device_repo import DeviceRepository
    from app.repositories.mount_record_repo import MountRecordRepository
    from app.repositories.rack_repo import RackRepository
    from app.repositories.room_repo import RoomRepository
    from app.schemas.device import DeviceCreate
    from app.schemas.rack import RackCreate
    from app.schemas.room import RoomCreate
    from app.services.dashboard_service import DashboardService

    async with async_session_factory() as session:
        room = await RoomRepository(session).create(RoomCreate(code="RM-DIST", name="分布机房"))
        rack = await RackRepository(session).create(
            RackCreate(room_id=room.id, code="RD1", name="RD1", column_code="A", total_u=20, status=RackBizStatus.AVAILABLE)
        )
        specs = [
            DeviceStatus.MOUNTED,
            DeviceStatus.IN_STOCK,
            DeviceStatus.UNMOUNTED,
            DeviceStatus.SCRAPPED,
            DeviceStatus.LENT,
        ]
        devs = []
        for i, st in enumerate(specs):
            d = await DeviceRepository(session).create(
                DeviceCreate(name=f"dist-{i}", device_type="server", u_height=1, status=st)
            )
            devs.append(d)
        await session.flush()
        mrepo = MountRecordRepository(session)
        for d in devs:
            # 直接写有效上架记录，避免 mount 流程把状态覆盖为「已上架」
            await mrepo.create(device_id=d.id, room_id=room.id, rack_id=rack.id, start_u=1, occupied_u=1)
        await session.commit()

        svc = DashboardService(session, cache=Cache())
        dash = await svc.get_room_dashboard(room.id)
        dist = dash.device_status_distribution
        assert dist.mounted == 1
        assert dist.in_stock == 1
        assert dist.unmounted == 1
        assert dist.scrapped == 1
        assert dist.lent == 1
        # 旧 schema 字段已移除
        assert not hasattr(dist, "running")
        assert not hasattr(dist, "offline")
        assert not hasattr(dist, "fault")
        assert not hasattr(dist, "maintenance")


async def test_unified_error_envelope(client):
    """H4 回归：未注册路由的 404 返回统一信封 {code:404,...}（不再是默认 detail 结构）。"""
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 404
    assert isinstance(body["message"], str)
    assert body["data"] is None
