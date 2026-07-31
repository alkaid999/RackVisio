"""操作日志增强回归测试（#684 / #685 / #686）。

覆盖本次三类修复：
- 修改类操作记录字段级 diff（旧值 → 新值），不再「无详情」；
- 资源类型精确归类（接口归 interface、链路归 link，不再误判设备）；
- 账号密码等敏感字段递归遮蔽，杜绝明文落库；
- 后端 operation_logs.resource 落库 + 按资源类型筛选生效。
"""

from __future__ import annotations


async def _op_logs(ac, **params):
    resp = await ac.get("/api/v1/logs/operations", params={"size": 200, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["items"]


async def _create_device(ac, name: str) -> str:
    resp = await ac.post(
        "/api/v1/devices", json={"name": name, "device_type": "server", "u_height": 1}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def test_put_room_records_field_diff(client):
    """PUT 修改机房地址：操作日志 detail.diff 应含字段级变更（旧值 → 新值）。"""
    created = await client.post(
        "/api/v1/rooms",
        json={"name": "diff 机房", "code": "DIFF-01", "address": "旧地址 1 号"},
    )
    assert created.status_code == 200, created.text
    room_id = created.json()["data"]["id"]

    upd = await client.put(
        f"/api/v1/rooms/{room_id}", json={"address": "新地址 2 号"}
    )
    assert upd.status_code == 200, upd.text

    items = await _op_logs(client)
    hit = next(
        (i for i in items if i["method"] == "PUT" and i["path"] == f"/api/v1/rooms/{room_id}"),
        None,
    )
    assert hit, "应产生 PUT /rooms/{id} 操作日志"
    assert hit["resource"] == "room", "机房操作 resource 应为 room"
    assert hit["detail"], "detail 不应为空"
    diff = hit["detail"].get("diff") or []
    addr_diff = next((d for d in diff if d["field"] == "address"), None)
    assert addr_diff, f"diff 应含 address 变更，实际：{diff}"
    assert addr_diff["old"] == "旧地址 1 号", "旧值应被快照"
    assert addr_diff["new"] == "新地址 2 号", "新值应为请求体值"


async def test_resource_classification_interface_and_link(client):
    """新增接口 / 新增链路 resource 应分别归为 interface / link（不再误判 device）。"""
    # 链路要求两端设备已上架机柜，先搭最小拓扑：机房 → 机柜 → 设备 → 接口。
    room = await client.post(
        "/api/v1/rooms", json={"name": "链机房", "code": "LNK-01"}
    )
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    rack = await client.post(
        f"/api/v1/rooms/{room_id}/racks",
        json={"code": "RK-A", "column_code": "A", "total_u": 42, "status": "可用"},
    )
    assert rack.status_code == 200, rack.text
    rack_id = rack.json()["data"]["id"]

    dev = await _create_device(client, "分类设备")
    await client.post(
        f"/api/v1/racks/{rack_id}/mount",
        json={"device_id": dev, "start_u": 1},
    )
    iface = await client.post(
        f"/api/v1/devices/{dev}/interfaces",
        json={"name": "eth0", "interface_type": "rj45"},
    )
    assert iface.status_code == 201, iface.text
    iface_id = iface.json()["data"]["id"]

    dev2 = await _create_device(client, "分类设备2")
    await client.post(
        f"/api/v1/racks/{rack_id}/mount",
        json={"device_id": dev2, "start_u": 2},
    )
    iface2 = await client.post(
        f"/api/v1/devices/{dev2}/interfaces",
        json={"name": "eth1", "interface_type": "rj45"},
    )
    assert iface2.status_code == 201, iface2.text
    iface2_id = iface2.json()["data"]["id"]

    link = await client.post(
        "/api/v1/links",
        json={
            "source_interface_id": iface_id,
            "target_interface_id": iface2_id,
            "medium": "tp",
            "connector_type": "cat5e",
        },
    )
    assert link.status_code == 201, link.text

    items = await _op_logs(client)
    iface_log = next(
        (i for i in items if i["method"] == "POST" and i["path"].endswith("/interfaces")),
        None,
    )
    assert iface_log, "应产生新增接口日志"
    assert iface_log["resource"] == "interface", "接口应归为 interface"

    link_log = next(
        (i for i in items if i["method"] == "POST" and i["path"] == "/api/v1/links"),
        None,
    )
    assert link_log, "应产生新增链路日志"
    assert link_log["resource"] == "link", "链路应归为 link"


async def test_password_masked_in_operation_log(client):
    """账号创建含明文密码：操作日志 detail.data.password 必须遮蔽为 ******。"""
    resp = await client.post(
        "/api/v1/accounts",
        json={"username": "secretuser", "password": "PlainText123", "role": "user"},
    )
    assert resp.status_code == 200, resp.text

    items = await _op_logs(client)
    hit = next(
        (i for i in items if i["method"] == "POST" and i["path"] == "/api/v1/accounts"),
        None,
    )
    assert hit, "应产生新增账号日志"
    assert hit["resource"] == "account"
    assert hit["detail"], "detail 不应为空"
    assert hit["detail"]["data"].get("password") == "******", "明文密码必须遮蔽"
    raw = str(hit["detail"])
    assert "PlainText123" not in raw, "明文密码不得出现在任何日志字段中"


async def test_device_put_records_field_diff(client):
    """PUT 修改设备：操作日志 detail.diff 应含字段级变更（旧值 → 新值）。

    复现用户反馈「修改了设备还是没有详情」——验证设备 PUT 与机房 PUT 走同一套
    diff 机制，落库 detail 不为空、含 remark 字段的原值 → 新值。
    """
    dev_id = await _create_device(client, "diff 设备")
    upd = await client.put(
        f"/api/v1/devices/{dev_id}", json={"remark": "新备注内容"}
    )
    assert upd.status_code == 200, upd.text

    items = await _op_logs(client)
    hit = next(
        (i for i in items if i["method"] == "PUT" and i["path"] == f"/api/v1/devices/{dev_id}"),
        None,
    )
    assert hit, "应产生 PUT /devices/{id} 操作日志"
    assert hit["resource"] == "device", "设备操作 resource 应为 device"
    assert hit["detail"], "detail 不应为空"
    diff = hit["detail"].get("diff") or []
    remark_diff = next((d for d in diff if d["field"] == "remark"), None)
    assert remark_diff, f"diff 应含 remark 变更，实际：{diff}"
    assert remark_diff["new"] == "新备注内容", "新值应为请求体值"


async def test_resource_filter(client):
    """GET /logs/operations?resource=XXX 仅返回对应资源类型的日志。"""
    await client.post("/api/v1/rooms", json={"name": "筛选机房", "code": "FILT-01"})
    dev = await _create_device(client, "筛选设备")
    await client.post(
        f"/api/v1/devices/{dev}/interfaces",
        json={"name": "filt0", "interface_type": "rj45"},
    )

    room_only = await _op_logs(client, resource="room")
    assert room_only, "按 room 筛选应有结果"
    assert all(i["resource"] == "room" for i in room_only), "筛选结果应全为 room"

    iface_only = await _op_logs(client, resource="interface")
    assert iface_only, "按 interface 筛选应有结果"
    assert all(i["resource"] == "interface" for i in iface_only), "筛选结果应全为 interface"

    # 不存在的资源类型返回空（旧日志 resource 为 NULL 不参与具体筛选）。
    none = await _op_logs(client, resource="link")
    assert all(i["resource"] == "link" for i in none)


async def test_action_filter_and_target(client):
    """GET /logs/operations?action=create|update|delete 仅返回对应动作；target 为对象可读名称。

    覆盖 #692/#693：操作动词归一化为 create/update/delete 三态，且新增「操作对象」
    target 列（设备名/机柜名/机房名等），前端据此展示具体被操作实体。
    """
    created = await client.post(
        "/api/v1/rooms", json={"name": "动作机房", "code": "ACT-01"}
    )
    assert created.status_code == 200, created.text
    room_id = created.json()["data"]["id"]

    # 新增：action=create，target=机房名（来自请求体 name）
    create_logs = await _op_logs(client, action="create")
    hit = next(
        (i for i in create_logs if i["path"] == "/api/v1/rooms" and i["resource"] == "room"),
        None,
    )
    assert hit, "应产生 create 动作日志"
    assert hit["action"] == "create", "action 应为 create"
    assert hit["target"] == "动作机房", "target 应为机房名"

    # 修改：action=update（PUT），body 无 name → target 回退旧快照名
    upd = await client.put(f"/api/v1/rooms/{room_id}", json={"alias": "动作别名"})
    assert upd.status_code == 200, upd.text
    update_logs = await _op_logs(client, action="update")
    hit_u = next(
        (i for i in update_logs if i["resource"] == "room" and i["method"] == "PUT"),
        None,
    )
    assert hit_u, "应产生 update 动作日志"
    assert hit_u["action"] == "update"
    assert hit_u["target"] == "动作机房", "update 的 target 应解析为机房名（旧快照回退）"

    # 删除：action=delete，target=机房名（来自旧快照）
    await client.delete(f"/api/v1/rooms/{room_id}")
    delete_logs = await _op_logs(client, action="delete")
    hit_d = next(
        (i for i in delete_logs if i["resource"] == "room" and i["method"] == "DELETE"),
        None,
    )
    assert hit_d, "应产生 delete 动作日志"
    assert hit_d["action"] == "delete"
    assert hit_d["target"] == "动作机房", "delete 的 target 应为机房名"


async def test_target_enrichment_for_link_interface_consumable(client):
    """操作对象（target）应富化解析，可反查具体设备（用户 #692 反馈）。

    - 接口：'{设备名} / {接口名}'（旧：仅接口名 ethX，无法确认设备）；
    - 链路：'{源设备}/{源接口} → {目标设备}/{目标接口}'（旧：依赖不存在的
      source_device_id/target_device_id，落库为 null）；
    - 耗材调整：'{条目名} {操作类型} {±数量}'（旧：仅条目名，无操作类型/数量）。
    """
    # ---- 最小拓扑：机房 → 机柜 → 设备 → 接口（链路两端） ----
    room = await client.post("/api/v1/rooms", json={"name": "目标机房", "code": "TGT-01"})
    assert room.status_code == 200, room.text
    room_id = room.json()["data"]["id"]
    rack = await client.post(
        f"/api/v1/rooms/{room_id}/racks",
        json={"code": "RK-T", "column_code": "A", "total_u": 42, "status": "可用"},
    )
    assert rack.status_code == 200, rack.text
    rack_id = rack.json()["data"]["id"]

    dev_a = await _create_device(client, "目标设备A")
    await client.post(f"/api/v1/racks/{rack_id}/mount", json={"device_id": dev_a, "start_u": 1})
    iface_a = await client.post(
        f"/api/v1/devices/{dev_a}/interfaces",
        json={"name": "ethA", "interface_type": "rj45"},
    )
    assert iface_a.status_code == 201, iface_a.text
    iface_a_id = iface_a.json()["data"]["id"]

    dev_b = await _create_device(client, "目标设备B")
    await client.post(f"/api/v1/racks/{rack_id}/mount", json={"device_id": dev_b, "start_u": 2})
    iface_b = await client.post(
        f"/api/v1/devices/{dev_b}/interfaces",
        json={"name": "ethB", "interface_type": "rj45"},
    )
    assert iface_b.status_code == 201, iface_b.text
    iface_b_id = iface_b.json()["data"]["id"]

    # ---- 接口：target = '{设备名} / {接口名}'（两条接口日志均须富化） ----
    items = await _op_logs(client)
    iface_logs = [
        i for i in items
        if i["method"] == "POST" and i["path"].endswith("/interfaces") and i["resource"] == "interface"
    ]
    assert len(iface_logs) >= 2, f"应至少产生两条新增接口日志，实际：{len(iface_logs)}"
    iface_targets = {log["target"] for log in iface_logs}
    assert "目标设备A / ethA" in iface_targets, (
        f"接口 ethA 的 target 应富化为「设备名 / 接口名」，实际：{iface_targets}"
    )
    assert "目标设备B / ethB" in iface_targets, (
        f"接口 ethB 的 target 应富化为「设备名 / 接口名」，实际：{iface_targets}"
    )

    # ---- 链路：先建，再改（PUT），target = '{源设备}/{源接口} → {目标设备}/{目标接口}' ----
    link = await client.post(
        "/api/v1/links",
        json={
            "source_interface_id": iface_a_id,
            "target_interface_id": iface_b_id,
            "medium": "tp",
            "connector_type": "cat5e",
        },
    )
    assert link.status_code == 201, link.text
    link_id = link.json()["data"]["id"]

    upd = await client.put(f"/api/v1/links/{link_id}", json={"remark": "调整后备注"})
    assert upd.status_code == 200, upd.text

    items = await _op_logs(client)
    link_log = next(
        (i for i in items if i["method"] == "PUT" and i["path"] == f"/api/v1/links/{link_id}"),
        None,
    )
    assert link_log, "应产生修改链路日志"
    assert link_log["resource"] == "link"
    expected_link_target = "目标设备A/ethA → 目标设备B/ethB"
    assert link_log["target"] == expected_link_target, (
        f"链路 target 应富化为「两端设备/接口」，实际：{link_log['target']!r}"
    )

    # ---- 耗材：建类型/分类/条目，再库存调整，target = '{条目名} {操作类型} {±数量}' ----
    ctype = await client.post("/api/v1/consumables/types", json={"name": "目标类型"})
    assert ctype.status_code == 200, ctype.text
    type_id = ctype.json()["data"]["id"]
    ccat = await client.post(
        f"/api/v1/consumables/types/{type_id}/categories",
        json={"name": "目标分类"},
    )
    assert ccat.status_code == 200, ccat.text
    cat_id = ccat.json()["data"]["id"]
    citem = await client.post(
        "/api/v1/consumables/items",
        json={"type_id": type_id, "category_id": cat_id, "name": "目标耗材", "current_quantity": 0},
    )
    assert citem.status_code == 200, citem.text
    item_id = citem.json()["data"]["id"]

    adjust = await client.post(
        f"/api/v1/consumables/items/{item_id}/adjust",
        json={"operation_type": "盘点", "quantity": 7},
    )
    assert adjust.status_code == 200, adjust.text

    items = await _op_logs(client)
    adjust_log = next(
        (i for i in items if i["method"] == "POST" and i["path"].endswith("/adjust")),
        None,
    )
    assert adjust_log, "应产生库存调整日志"
    assert adjust_log["resource"] == "consumable"
    assert adjust_log["target"] == "目标耗材 盘点 +7", (
        f"耗材调整 target 应富化为「条目名 操作类型 ±数量」，实际：{adjust_log['target']!r}"
    )


async def test_target_clipped_to_column_limit(client):
    """超长操作对象必须裁剪到 255，否则 PostgreSQL 会静默丢掉整条日志。

    链路 target 由「设备名(255)/接口名(64) → 设备名(255)/接口名(64)」拼成，
    最长可达 640+ 字符，远超 operation_logs.target 的 String(255)。SQLite 不
    强制长度所以本地无感，但 PostgreSQL 会抛 StringDataRightTruncation，被
    中间件外层 except 吞掉 → 该操作完全没有留痕。此处用超长设备名固化裁剪行为。
    """
    long_name = "超长设备名" * 50  # 250 字符，接近 Device.name 的 String(255) 上限
    room = await client.post("/api/v1/rooms", json={"name": "裁剪机房", "code": "CLIP-01"})
    assert room.status_code == 200, room.text
    rack = await client.post(
        f"/api/v1/rooms/{room.json()['data']['id']}/racks",
        json={"code": "RK-CLIP", "column_code": "A", "total_u": 42, "status": "可用"},
    )
    assert rack.status_code == 200, rack.text
    rack_id = rack.json()["data"]["id"]

    dev_a = await _create_device(client, long_name + "A")
    dev_b = await _create_device(client, long_name + "B")
    # 链路要求两端设备均已上架机柜。
    await client.post(f"/api/v1/racks/{rack_id}/mount", json={"device_id": dev_a, "start_u": 1})
    await client.post(f"/api/v1/racks/{rack_id}/mount", json={"device_id": dev_b, "start_u": 3})

    if_a = await client.post(
        f"/api/v1/devices/{dev_a}/interfaces",
        json={"name": "ethLongA", "interface_type": "rj45"},
    )
    assert if_a.status_code in (200, 201), if_a.text
    if_b = await client.post(
        f"/api/v1/devices/{dev_b}/interfaces",
        json={"name": "ethLongB", "interface_type": "rj45"},
    )
    assert if_b.status_code in (200, 201), if_b.text

    link = await client.post(
        "/api/v1/links",
        json={
            "source_interface_id": if_a.json()["data"]["id"],
            "target_interface_id": if_b.json()["data"]["id"],
            "medium": "tp",
            "connector_type": "cat5e",
        },
    )
    assert link.status_code in (200, 201), link.text

    items = await _op_logs(client)
    link_log = next(
        (i for i in items if i["method"] == "POST" and i["path"] == "/api/v1/links"),
        None,
    )
    assert link_log, "应产生新增链路日志"
    target = link_log["target"]
    assert target, "超长对象名不应导致 target 丢失"
    assert len(target) <= 255, (
        f"target 必须裁剪到列上限 255，实际 {len(target)} 字符——生产 PG 会写入失败"
    )
    assert target.endswith("…"), "裁剪后应带省略号标记，提示内容被截断"

    # 操作人字段同理不得超列宽（String(64)）。
    assert len(link_log["operator_name"] or "") <= 64
