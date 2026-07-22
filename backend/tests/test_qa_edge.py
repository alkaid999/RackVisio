"""QA 独立边界用例（严过关）。

与 test_smoke.py 互补，使用「全新机房 + 全新机柜 + 全新设备」的隔离数据，
不依赖种子布局，从独立视角验证 PRD 6.6 与契约的关键边界行为：

1. 机柜 U 位越界校验（check-u 返回 conflict + 越界错误信息，对照 PRD 6.6）。
2. 拓扑按机柜过滤（nodes 仅属该机柜、edges 仅连接该机柜内节点）。
3. 端口批量生成（数量正确 + 命名按模板递增）。
4. 机柜删除保护（含设备 -> 409；清空设备后可删）。

依赖 conftest 的 ``setup_database``（每测试重建表 + 种子）与 ``client``。
"""

from __future__ import annotations


# --------------------------------------------------------------------------- #
# 隔离数据构造辅助
# --------------------------------------------------------------------------- #
async def _make_room(client, code: str) -> str:
    resp = await client.post(
        "/api/v1/rooms",
        json={
            "name": f"QA机房-{code}",
            "code": code,
            "location": "9F",
            "category": "T1",
            "rows": 1,
            "cols": 2,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _make_rack(client, room_id: str, code: str, total_u: int = 20) -> str:
    resp = await client.post(
        f"/api/v1/rooms/{room_id}/racks",
        json={
            "name": f"QA机柜-{code}",
            "code": code,
            "row_num": 0,
            "col_num": 0,
            "total_u": total_u,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _make_device(
    client, rack_id: str, name: str, start_u: int, size_u: int, device_type: str = "server"
) -> str:
    resp = await client.post(
        "/api/v1/devices",
        json={
            "rack_id": rack_id,
            "name": name,
            "device_type": device_type,
            "start_u": start_u,
            "size_u": size_u,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _make_port(client, device_id: str, name: str) -> str:
    resp = await client.post(
        f"/api/v1/devices/{device_id}/interfaces",
        json={"name": name, "interface_type": "electrical", "speed": "1G"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# --------------------------------------------------------------------------- #
# 1. 机柜 U 位越界校验（PRD 6.6：超出机柜 U 位范围）
# --------------------------------------------------------------------------- #
async def test_qa_check_u_out_of_bounds(client):
    """全新机柜 total_u=10，验证越界分支与边界临界值。

    - 越界：start_u=6, size_u=10 -> 占用 U6..15，末端 15 > 10 -> 应报越界错误。
    - 临界：start_u=8, size_u=3 -> 占用 U8..10，末端 10 == 10 -> 不越界、不冲突。
    """
    room_id = await _make_room(client, "ROOM-QA-OOB")
    rack_id = await _make_rack(client, room_id, "RACK-QA-OOB", total_u=10)

    # 越界：末端 U 位超过 total_u
    resp = await client.post(
        f"/api/v1/racks/{rack_id}/check-u", json={"start_u": 6, "size_u": 10}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["conflict"] is True
    assert data["error"] is not None
    assert "超出机柜 U 位范围" in data["error"], data

    # 临界：恰好占满 U8..U10（末端 == total_u），不应判越界
    resp = await client.post(
        f"/api/v1/racks/{rack_id}/check-u", json={"start_u": 8, "size_u": 3}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["conflict"] is False, data


# --------------------------------------------------------------------------- #
# 2. 拓扑按机柜过滤
# --------------------------------------------------------------------------- #
async def test_qa_topology_rack_filter(client):
    """两机柜：rack1 内有 A、C 与一条同机柜链路；rack2 内有 B。

    建立一条跨机柜链路 A<->B 后，按 rack_id=rack1 过滤拓扑应：
    - nodes 仅含 A、C（不含 B）；
    - edges 仅连接 rack1 内节点（保留 A<->C，剔除 A<->B）。
    """
    room_id = await _make_room(client, "ROOM-QA-TOPO")
    rack1 = await _make_rack(client, room_id, "RACK-QA-R1", total_u=20)
    rack2 = await _make_rack(client, room_id, "RACK-QA-R2", total_u=20)

    A = await _make_device(client, rack1, "QA-A", 1, 1)
    C = await _make_device(client, rack1, "QA-C", 2, 1)
    B = await _make_device(client, rack2, "QA-B", 1, 1, device_type="switch")

    pa1 = await _make_port(client, A, "pA1")
    pa2 = await _make_port(client, A, "pA2")
    pc1 = await _make_port(client, C, "pC1")
    pb1 = await _make_port(client, B, "pB1")

    # 同机柜链路 A<->C
    resp = await client.post(
        "/api/v1/links",
        json={
            "source_interface_id": pa1,
            "target_interface_id": pc1,
            "medium": "tp",
            "connector_type": "cat5e",
        },
    )
    assert resp.status_code == 201, resp.text
    # 跨机柜链路 A<->B
    resp = await client.post(
        "/api/v1/links",
        json={
            "source_interface_id": pa2,
            "target_interface_id": pb1,
            "medium": "tp",
            "connector_type": "cat5e",
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get("/api/v1/topology", params={"rack_id": rack1})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    node_ids = {n["id"] for n in data["nodes"]}
    # 节点仅属于 rack1
    assert node_ids == {A, C}, f"rack1 拓扑节点越界: {node_ids}"
    assert B not in node_ids

    # 边只连接 rack1 内节点
    for e in data["edges"]:
        assert e["source"] in node_ids and e["target"] in node_ids, f"跨机柜边未过滤: {e}"

    edge_pairs = {(e["source"], e["target"]) for e in data["edges"]}
    # 同机柜链路应保留
    assert (A, C) in edge_pairs or (C, A) in edge_pairs
    # 跨机柜链路不应出现
    assert (A, B) not in edge_pairs and (B, A) not in edge_pairs


# --------------------------------------------------------------------------- #
# 3. 端口批量生成（数量 + 命名递增）
# --------------------------------------------------------------------------- #
async def test_qa_port_batch_naming(client):
    """全新设备批量生成 5 个端口，命名模板 Gig0/%d -> Gig0/1..Gig0/5。"""
    room_id = await _make_room(client, "ROOM-QA-PORT")
    rack = await _make_rack(client, room_id, "RACK-QA-PORT", total_u=10)
    dev = await _make_device(client, rack, "QA-PDEV", 1, 1)

    resp = await client.post(
        f"/api/v1/devices/{dev}/interfaces/batch",
        json={"count": 5, "naming_pattern": "Gig0/%d"},
    )
    assert resp.status_code == 201, resp.text
    ports = resp.json()["data"]
    assert len(ports) == 5, ports

    names = sorted(p["name"] for p in ports)
    expected = [f"Gig0/{i}" for i in range(1, 6)]
    assert names == expected, f"端口命名未按模板递增: {names}"


# --------------------------------------------------------------------------- #
# 4. 机柜删除保护
# --------------------------------------------------------------------------- #
async def test_qa_rack_delete_protection(client):
    """含设备的机柜 DELETE -> 409；清空设备后可删（200）。"""
    room_id = await _make_room(client, "ROOM-QA-DEL")
    rack = await _make_rack(client, room_id, "RACK-QA-DEL", total_u=10)
    dev = await _make_device(client, rack, "QA-DEV", 1, 1)

    # 含设备：应拒绝删除
    resp = await client.delete(f"/api/v1/racks/{rack}")
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == 409
    assert "设备" in resp.json()["message"], resp.json()

    # 清空设备后再删：应成功
    resp = await client.delete(f"/api/v1/devices/{dev}")
    assert resp.status_code == 200, resp.text
    resp = await client.delete(f"/api/v1/racks/{rack}")
    assert resp.status_code == 200, resp.text
    resp = await client.get(f"/api/v1/racks/{rack}")
    assert resp.status_code == 404
