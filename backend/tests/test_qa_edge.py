"""QA 独立边界用例（严过关）。

与 test_smoke.py 互补，使用「全新机房 + 全新机柜 + 全新设备」的隔离数据，
不依赖种子布局，从独立视角验证 PRD 6.6 与契约的关键边界行为：

1. 机柜 U 位越界校验（check-u 返回 conflict + 越界错误信息，对照 PRD 6.6）。
2. 端口批量生成（数量正确 + 命名按模板递增，新批量格式 groups）。
3. 机柜删除保护（含设备 -> 409；清空设备后可删）。

依赖 conftest 的 ``setup_database``（每测试重建表 + 种子）与 ``client``。
种子仅含管理员 + 耗材类型，无演示业务数据；辅助函数自建数据。
"""

from __future__ import annotations


# --------------------------------------------------------------------------- #
# 隔离数据构造辅助
# --------------------------------------------------------------------------- #
async def _make_room(client, code: str) -> str:
    resp = await client.post(
        "/api/v1/rooms",
        json={"name": f"QA机房-{code}", "code": code, "area": "A", "building": "B", "floor": "9F"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _make_rack(client, room_id: str, code: str, total_u: int = 20) -> str:
    resp = await client.post(
        f"/api/v1/rooms/{room_id}/racks",
        json={"code": code, "column_code": "A", "total_u": total_u, "status": "可用"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def _make_device(client, rack_id: str, name: str, u_height: int = 1) -> str:
    """创建设备（不传 start_u/size_u：上架位置由 mount 流程决定）。"""
    resp = await client.post(
        "/api/v1/devices",
        json={"name": name, "device_type": "server", "u_height": u_height},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _mount(client, rack_id: str, device_id: str, start_u: int) -> None:
    resp = await client.post(
        f"/api/v1/racks/{rack_id}/mount",
        json={"device_id": device_id, "start_u": start_u},
    )
    assert resp.status_code == 200, resp.text


async def _make_port(client, device_id: str, name: str) -> str:
    resp = await client.post(
        f"/api/v1/devices/{device_id}/interfaces",
        json={"name": name, "interface_type": "rj45", "speed": "1G"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# --------------------------------------------------------------------------- #
# 1. 机柜 U 位越界校验（PRD 6.6：超出机柜 U 位范围）
# --------------------------------------------------------------------------- #
async def test_qa_check_u_out_of_bounds(client):
    """全新机柜 total_u=10，验证越界分支与边界临界值。

    - 越界：u_height=10 的设备在 start_u=6 放置 -> 占 U6..15，末端 15 > 10 -> 应报越界错误。
    - 临界：u_height=3 的设备在 start_u=8 放置 -> 占 U8..10，末端 10 == 10 -> 不越界、不冲突。
    """
    room_id = await _make_room(client, "ROOM-QA-OOB")
    rack_id = await _make_rack(client, room_id, "RACK-QA-OOB", total_u=10)

    # 越界：用 u_height=10 的设备在 start_u=6 试探（占用 U6..15，超出 1~10）
    dev_oversize = await _make_device(client, rack_id, "QA-OOB", u_height=10)
    resp = await client.post(
        f"/api/v1/racks/{rack_id}/check-u", json={"device_id": dev_oversize, "start_u": 6}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["conflict"] is True
    assert data["error"] is not None
    assert "超出机柜 U 位范围" in data["error"], data

    # 临界：用 u_height=3 的设备在 start_u=8 试探（占用 U8..10，末端 == total_u），不应判越界
    dev_crit = await _make_device(client, rack_id, "QA-CRIT", u_height=3)
    resp = await client.post(
        f"/api/v1/racks/{rack_id}/check-u", json={"device_id": dev_crit, "start_u": 8}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["conflict"] is False, data


# --------------------------------------------------------------------------- #
# 2. 端口批量生成（新格式：groups 列表；数量 + 命名递增）
# --------------------------------------------------------------------------- #
async def test_qa_port_batch_naming(client):
    """全新设备批量生成 5 个端口，命名模板 Gig0/%d -> Gig0/1..Gig0/5。"""
    room_id = await _make_room(client, "ROOM-QA-PORT")
    rack = await _make_rack(client, room_id, "RACK-QA-PORT", total_u=10)
    dev = await _make_device(client, rack, "QA-PDEV")

    resp = await client.post(
        f"/api/v1/devices/{dev}/interfaces/batch",
        json={"groups": [{"count": 5, "naming_pattern": "Gig0/%d"}]},
    )
    assert resp.status_code == 201, resp.text
    ports = resp.json()["data"]
    assert len(ports) == 5, ports

    names = sorted(p["name"] for p in ports)
    expected = [f"Gig0/{i}" for i in range(1, 6)]
    assert names == expected, f"端口命名未按模板递增: {names}"


# --------------------------------------------------------------------------- #
# 3. 机柜删除保护
# --------------------------------------------------------------------------- #
async def test_qa_rack_delete_protection(client):
    """含设备的机柜 DELETE -> 409；先下架设备并删除后再删机柜 -> 200。"""
    room_id = await _make_room(client, "ROOM-QA-DEL")
    rack = await _make_rack(client, room_id, "RACK-QA-DEL", total_u=10)
    dev = await _make_device(client, rack, "QA-DEV")
    await _mount(client, rack, dev, 1)

    # 含设备：应拒绝删除
    resp = await client.delete(f"/api/v1/racks/{rack}")
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == 409
    assert "设备" in resp.json()["message"], resp.json()

    # 清空设备：先下架，再删除设备，最后删除机柜
    resp = await client.post(f"/api/v1/racks/{rack}/unmount", json={"device_id": dev})
    assert resp.status_code == 200, resp.text
    resp = await client.delete(f"/api/v1/devices/{dev}")
    assert resp.status_code == 200, resp.text
    resp = await client.delete(f"/api/v1/racks/{rack}")
    assert resp.status_code == 200, resp.text
    resp = await client.get(f"/api/v1/racks/{rack}")
    assert resp.status_code == 404
