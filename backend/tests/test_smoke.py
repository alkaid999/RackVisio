"""后端冒烟测试：覆盖健康、机房/机柜/设备/端口/链路/拓扑/大屏关键路径。

所有用例依赖 conftest 的 ``setup_database``（每测试重建表 + 种子数据）与 ``client``。
"""

from __future__ import annotations

from typing import Optional


async def _room_id(client) -> str:
    resp = await client.get("/api/v1/rooms")
    assert resp.status_code == 200
    return resp.json()["data"]["items"][0]["id"]


async def _rack_id(client, room_id: str, code: str) -> str:
    resp = await client.get(f"/api/v1/rooms/{room_id}/racks")
    assert resp.status_code == 200
    for r in resp.json()["data"]:
        if r["code"] == code:
            return r["id"]
    raise AssertionError(f"rack {code} not found")


async def _device_id_in_rack(client, rack_id: str, name: str) -> str:
    resp = await client.get(f"/api/v1/racks/{rack_id}/devices")
    assert resp.status_code == 200
    for d in resp.json()["data"]:
        if d["name"] == name:
            return d["id"]
    raise AssertionError(f"device {name} not found")


async def _interface_id(client, device_id: str, name: str) -> str:
    resp = await client.get(f"/api/v1/devices/{device_id}/interfaces")
    assert resp.status_code == 200
    for p in resp.json()["data"]:
        if p["name"] == name:
            return p["id"]
    raise AssertionError(f"interface {name} not found")


# --------------------------------------------------------------------------- #
# 健康检查
# --------------------------------------------------------------------------- #
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "up"


# --------------------------------------------------------------------------- #
# 机房 CRUD
# --------------------------------------------------------------------------- #
async def test_room_crud(client):
    # 创建
    resp = await client.post(
        "/api/v1/rooms",
        json={
            "name": "测试机房",
            "code": "ROOM-TEST",
            "location": "2F",
            "category": "T2",
            "rows": 2,
            "cols": 2,
        },
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
    resp = await client.put(
        f"/api/v1/rooms/{room_id}", json={"name": "测试机房-改", "category": "T3"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "测试机房-改"
    assert resp.json()["data"]["category"] == "T3"

    # 软删除
    resp = await client.delete(f"/api/v1/rooms/{room_id}")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/rooms/{room_id}")
    assert resp.json()["data"]["status"] == "disabled"


async def test_room_code_unique(client):
    resp = await client.post(
        "/api/v1/rooms",
        json={
            "name": "重复编号",
            "code": "ROOM-A",  # 种子已存在
            "category": "T1",
            "rows": 1,
            "cols": 1,
        },
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 409


# --------------------------------------------------------------------------- #
# 机柜 + 机房下机柜
# --------------------------------------------------------------------------- #
async def test_room_rack_endpoints(client):
    room_id = await _room_id(client)
    # 在机房下创建机柜
    resp = await client.post(
        f"/api/v1/rooms/{room_id}/racks",
        json={"name": "新机柜", "code": "RACK-NEW", "row_num": 1, "col_num": 1, "total_u": 45},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["total_u"] == 45

    # 列表
    resp = await client.get(f"/api/v1/rooms/{room_id}/racks")
    assert resp.status_code == 200
    assert any(r["code"] == "RACK-NEW" for r in resp.json()["data"])

    # 平面图
    resp = await client.get(f"/api/v1/rooms/{room_id}/floor-plan")
    assert resp.status_code == 200
    fp = resp.json()["data"]
    assert fp["rows"] == 2 and fp["cols"] == 2
    assert len(fp["cells"]) == 4

    # 容量统计（已新增 1 台机柜，共 4 台）
    resp = await client.get(f"/api/v1/rooms/{room_id}/stats")
    assert resp.status_code == 200
    stats = resp.json()["data"]
    assert stats["rack_count"] == 4


async def test_rack_detail_update_delete(client):
    room_id = await _room_id(client)
    r1 = await _rack_id(client, room_id, "test-rack-01")
    r3 = await _rack_id(client, room_id, "RACK-A-03")

    # 详情
    resp = await client.get(f"/api/v1/racks/{r1}")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "full"

    # 更新
    resp = await client.put(f"/api/v1/racks/{r1}", json={"total_u": 47})
    assert resp.status_code == 200
    assert resp.json()["data"]["total_u"] == 47

    # 有设备的机柜禁止删除 -> 409
    resp = await client.delete(f"/api/v1/racks/{r1}")
    assert resp.status_code == 409

    # 空机柜可删除
    resp = await client.delete(f"/api/v1/racks/{r3}")
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/racks/{r3}")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 设备：U 位冲突 + used_u 重算
# --------------------------------------------------------------------------- #
async def test_device_u_conflict_and_create(client):
    room_id = await _room_id(client)
    r1 = await _rack_id(client, room_id, "test-rack-01")  # srv-01(1-20), srv-02(21-35)

    # 冲突：U2 在 srv-01 范围内
    resp = await client.post(
        "/api/v1/devices",
        json={
            "rack_id": r1,
            "name": "冲突设备",
            "device_type": "server",
            "start_u": 2,
            "size_u": 1,
        },
    )
    assert resp.status_code == 409, resp.text
    assert "冲突" in resp.json()["message"]

    # 无冲突：U36~37
    resp = await client.post(
        "/api/v1/devices",
        json={
            "rack_id": r1,
            "name": "正常设备",
            "device_type": "server",
            "start_u": 36,
            "size_u": 2,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["start_u"] == 36


async def test_device_delete_recalculate(client):
    room_id = await _room_id(client)
    r1 = await _rack_id(client, room_id, "test-rack-01")
    before = (await client.get(f"/api/v1/racks/{r1}")).json()["data"]["used_u"]
    assert before == 35

    # 删除 srv-02（size_u=15）
    dev2 = await _device_id_in_rack(client, r1, "test-web-srv-02")
    resp = await client.delete(f"/api/v1/devices/{dev2}")
    assert resp.status_code == 200

    # used_u 应重算为 20
    after = (await client.get(f"/api/v1/racks/{r1}")).json()["data"]["used_u"]
    assert after == 20


async def test_device_u_map_and_check_u(client):
    room_id = await _room_id(client)
    r1 = await _rack_id(client, room_id, "test-rack-01")

    # U 位图
    resp = await client.get(f"/api/v1/racks/{r1}/u-map")
    assert resp.status_code == 200
    umap = resp.json()["data"]
    assert umap["total_u"] == 42
    # U1 被 srv-01 占用
    slot1 = next(s for s in umap["slots"] if s["u"] == 1)
    assert slot1["device_name"] == "test-web-srv-01"

    # check-u
    resp = await client.post(
        f"/api/v1/racks/{r1}/check-u",
        json={"start_u": 2, "size_u": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["conflict"] is True

    resp = await client.post(
        f"/api/v1/racks/{r1}/check-u",
        json={"start_u": 40, "size_u": 2},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["conflict"] is False


# --------------------------------------------------------------------------- #
# 端口：创建 + 批量生成
# --------------------------------------------------------------------------- #
async def test_port_crud_and_batch(client):
    room_id = await _room_id(client)
    r1 = await _rack_id(client, room_id, "test-rack-01")
    dev1 = await _device_id_in_rack(client, r1, "test-web-srv-01")

    # 创建接口
    resp = await client.post(
        f"/api/v1/devices/{dev1}/interfaces",
        json={"name": "mgmt0", "interface_type": "electrical", "speed": "1G"},
    )
    assert resp.status_code == 201, resp.text

    # 同名冲突
    resp = await client.post(
        f"/api/v1/devices/{dev1}/interfaces",
        json={"name": "mgmt0", "interface_type": "electrical"},
    )
    assert resp.status_code == 409

    # 批量生成
    before = len((await client.get(f"/api/v1/devices/{dev1}/interfaces")).json()["data"])
    resp = await client.post(
        f"/api/v1/devices/{dev1}/interfaces/batch",
        json={"count": 3, "naming_pattern": "Gig%d"},
    )
    assert resp.status_code == 201, resp.text
    after = len((await client.get(f"/api/v1/devices/{dev1}/interfaces")).json()["data"])
    assert after == before + 3


# --------------------------------------------------------------------------- #
# 链路：端口唯一性
# --------------------------------------------------------------------------- #
async def test_link_port_reuse_409(client):
    room_id = await _room_id(client)
    r1 = await _rack_id(client, room_id, "test-rack-01")
    r2 = await _rack_id(client, room_id, "test-rack-02")
    sw = await _device_id_in_rack(client, r2, "test-core-sw")  # Gig0/1(已用), Gig0/2(空闲)
    srv2 = await _device_id_in_rack(client, r1, "test-web-srv-02")  # eth0(空闲)

    free_src = await _interface_id(client, sw, "Gig0/2")
    free_tgt = await _interface_id(client, srv2, "eth0")

    # 创建新链路（成功）
    resp = await client.post(
        "/api/v1/links",
        json={
            "source_interface_id": free_src,
            "target_interface_id": free_tgt,
            "medium": "tp",
            "connector_type": "cat5e",
        },
    )
    assert resp.status_code == 201, resp.text

    # 复用源接口 -> 409
    resp = await client.post(
        "/api/v1/links",
        json={
            "source_interface_id": free_src,
            "target_interface_id": free_tgt,
            "medium": "tp",
            "connector_type": "cat5e",
        },
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == 409


# --------------------------------------------------------------------------- #
# 拓扑
# --------------------------------------------------------------------------- #
async def test_topology(client):
    room_id = await _room_id(client)

    # 按机房过滤
    resp = await client.get("/api/v1/topology", params={"room_id": room_id})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data["nodes"]) >= 1
    assert len(data["edges"]) >= 1

    # 单设备拓扑（test-core-sw 与其邻居）
    r2 = await _rack_id(client, room_id, "test-rack-02")
    sw = await _device_id_in_rack(client, r2, "test-core-sw")
    resp = await client.get(f"/api/v1/topology/device/{sw}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    node_ids = {n["id"] for n in data["nodes"]}
    assert sw in node_ids


# --------------------------------------------------------------------------- #
# 大屏
# --------------------------------------------------------------------------- #
async def test_dashboard(client):
    room_id = await _room_id(client)
    resp = await client.get(f"/api/v1/rooms/{room_id}/dashboard")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["kpi"]["rack_count"] == 3
    assert data["kpi"]["device_count"] == 3
    assert data["kpi"]["fault_count"] == 1
    assert "rack_status_distribution" in data
    assert "device_status_distribution" in data
    assert "topology_overview" in data
