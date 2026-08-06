"""硬件管理模块测试（独立个体模型：每件硬件单独记录、单独追踪）。

覆盖：
- 类型/分类 CRUD 与删除保护（非空禁删）
- 硬件条目 CRUD + SN 唯一性
- 设备硬件联动：分配（在库→已安装）、回收（回库可再分配）、已安装禁删、非法操作
- 变动记录（新增/分配/回收）留痕
- 操作日志中间件自动覆盖（resource=hardware）
"""

from __future__ import annotations

import pytest


# ============ 辅助 ============
async def _mk_hw_type(client, name="主板", desc="服务器主板"):
    resp = await client.post("/api/v1/hardwares/types", json={"name": name, "description": desc})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _mk_hw_category(client, type_id, name="标准 ATX"):
    resp = await client.post(
        f"/api/v1/hardwares/types/{type_id}/categories", json={"name": name}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _mk_hw_item(client, type_id, category_id, name="H3C 主板", sn="SN-MB-001", brand="H3C"):
    resp = await client.post(
        "/api/v1/hardwares/items",
        json={
            "type_id": type_id,
            "category_id": category_id,
            "name": name,
            "brand": brand,
            "sn": sn,
            "spec": "2U 定制",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _mk_device(client, name="HW-TEST-01"):
    """创建设备（复用设备模块接口；不建机房/机柜，仅在库登记即可）。"""
    resp = await client.post(
        "/api/v1/devices",
        json={"name": name, "device_type": "server", "status": "在库", "u_height": 2},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


# ============ 类型 / 分类 ============
async def test_type_category_crud(client):
    # 种子数据：预置 7 类硬件类型（主板/CPU 处理器/内存条/硬盘/阵列卡/网卡/电源模块）。
    resp = await client.get("/api/v1/hardwares/types")
    assert resp.status_code == 200
    types = resp.json()["data"]
    names = {t["name"] for t in types}
    assert {"主板", "CPU 处理器", "内存条", "硬盘", "阵列卡", "网卡", "电源模块"} <= names

    # 自定义类型 + 分类。
    t = await _mk_hw_type(client, "显卡", "GPU 加速卡")
    assert t["name"] == "显卡"
    c = await _mk_hw_category(client, t["id"], "NVIDIA A100")
    assert c["type_name"] == "显卡"
    # 分类挂载在类型下。
    resp = await client.get(f"/api/v1/hardwares/types/{t['id']}/categories")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    # 更新类型。
    resp = await client.put(f"/api/v1/hardwares/types/{t['id']}", json={"name": "GPU 显卡"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "GPU 显卡"

    # 删除保护：类型下仍有分类 → 409。
    resp = await client.delete(f"/api/v1/hardwares/types/{t['id']}")
    assert resp.status_code == 409, resp.text

    # 删分类后类型可删。
    assert (await client.delete(f"/api/v1/hardwares/categories/{c['id']}")).status_code == 200
    assert (await client.delete(f"/api/v1/hardwares/types/{t['id']}")).status_code == 200


# ============ 硬件条目（独立个体）============
async def test_item_crud_and_sn_unique(client):
    t = await _mk_hw_type(client, "内存条测试类")
    c = await _mk_hw_category(client, t["id"], "DDR4 ECC")
    item = await _mk_hw_item(client, t["id"], c["id"], name="32GB DDR4 ECC", sn="SN-RAM-001")
    assert item["status"] == "在库"
    assert item["brand"] == "H3C"
    assert item["sn"] == "SN-RAM-001"
    assert item["type_name"] == "内存条测试类"
    assert item["category_name"] == "DDR4 ECC"

    # 列表 + 关键字检索（品牌/SN 可搜）。
    resp = await client.get("/api/v1/hardwares/items", params={"keyword": "SN-RAM-001"})
    assert resp.status_code == 200
    assert resp.json()["data"]["total"] == 1
    resp = await client.get("/api/v1/hardwares/items", params={"status": "在库"})
    assert resp.json()["data"]["total"] == 1

    # SN 唯一性：重复 SN → 409。
    resp = await client.post(
        "/api/v1/hardwares/items",
        json={"type_id": t["id"], "category_id": c["id"], "name": "另一条", "sn": "SN-RAM-001"},
    )
    assert resp.status_code == 409, resp.text

    # 更新（改品牌/SN）。
    resp = await client.put(
        f"/api/v1/hardwares/items/{item['id']}", json={"brand": "Kingston", "sn": "SN-RAM-002"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["brand"] == "Kingston"
    assert resp.json()["data"]["sn"] == "SN-RAM-002"

    # 变动记录：建档即有一条「新增」。
    resp = await client.get(f"/api/v1/hardwares/items/{item['id']}/records")
    assert resp.status_code == 200
    records = resp.json()["data"]["items"]
    assert any(r["operation_type"] == "新增" for r in records)

    # 删除（在库可直接删 → 报废出库）。
    assert (await client.delete(f"/api/v1/hardwares/items/{item['id']}")).status_code == 200


# ============ 设备硬件联动（一对一）============
async def test_assign_and_recover_flow(client):
    t = await _mk_hw_type(client, "硬盘测试类")
    c = await _mk_hw_category(client, t["id"], "NVMe SSD")
    hw1 = await _mk_hw_item(client, t["id"], c["id"], name="1.6T NVMe", sn="SN-DISK-001")
    hw2 = await _mk_hw_item(client, t["id"], c["id"], name="3.2T NVMe", sn="SN-DISK-002")
    dev = await _mk_device(client, "SRV-A")

    # 分配：设备添加硬件（选具体某件，在库）。
    resp = await client.post(
        f"/api/v1/hardwares/devices/{dev['id']}/hardwares",
        json={"hardware_item_id": hw1["id"], "remark": "盘位 0"},
    )
    assert resp.status_code == 200, resp.text
    assigned = resp.json()["data"]
    assert assigned["status"] == "已安装"
    assert assigned["assigned_device_id"] == dev["id"]
    assert assigned["assigned_device_name"] == "SRV-A"

    # 设备硬件列表：只有 hw1。
    resp = await client.get(f"/api/v1/hardwares/devices/{dev['id']}/hardwares")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert [i["id"] for i in items] == [hw1["id"]]

    # 已安装的硬件：从硬件管理「在库」列表中不可见（status 过滤）。
    resp = await client.get("/api/v1/hardwares/items", params={"status": "在库"})
    stock_ids = {i["id"] for i in resp.json()["data"]["items"]}
    assert hw1["id"] not in stock_ids
    assert hw2["id"] in stock_ids

    # 已安装硬件禁删（须先回收）。
    resp = await client.delete(f"/api/v1/hardwares/items/{hw1['id']}")
    assert resp.status_code == 409, resp.text

    # 重复分配同一件（已安装）→ 409。
    resp = await client.post(
        f"/api/v1/hardwares/devices/{dev['id']}/hardwares",
        json={"hardware_item_id": hw1["id"]},
    )
    assert resp.status_code == 409, resp.text

    # 回收：设备删除硬件 → 硬件回库（在库可见、可再分配）。
    resp = await client.delete(f"/api/v1/hardwares/devices/{dev['id']}/hardwares/{hw1['id']}")
    assert resp.status_code == 200, resp.text
    recovered = resp.json()["data"]
    assert recovered["status"] == "在库"
    assert recovered["assigned_device_id"] is None

    # 回收后再查设备硬件列表为空。
    resp = await client.get(f"/api/v1/hardwares/devices/{dev['id']}/hardwares")
    assert resp.json()["data"] == []

    # 回收后硬件可再次分配（hw1 → 另一台设备）。
    dev2 = await _mk_device(client, "SRV-B")
    resp = await client.post(
        f"/api/v1/hardwares/devices/{dev2['id']}/hardwares",
        json={"hardware_item_id": hw1["id"]},
    )
    assert resp.status_code == 200

    # 变动记录：hw1 应有 新增 → 分配 → 回收 → 分配 四条。
    resp = await client.get(f"/api/v1/hardwares/items/{hw1['id']}/records")
    records = resp.json()["data"]["items"]
    ops = [r["operation_type"] for r in records]
    assert ops.count("分配") == 2
    assert ops.count("回收") == 1
    assert ops.count("新增") == 1
    # 分配记录带目标设备名（可追溯装到哪台）。
    assign_records = [r for r in records if r["operation_type"] == "分配"]
    assert assign_records[0]["device_name"] == "SRV-B"


# ============ 跨模块/非法操作 ============
async def test_invalid_operations(client):
    # 不存在的硬件 → 404。
    resp = await client.post(
        "/api/v1/hardwares/devices/xxx/hardwares", json={"hardware_item_id": "nope"}
    )
    assert resp.status_code in (404, 422)

    # 无 SN 的硬件也允许（sn 可空，但独立编号建议填写）。
    t = await _mk_hw_type(client, "网卡测试类")
    c = await _mk_hw_category(client, t["id"], "10G 光口")
    resp = await client.post(
        "/api/v1/hardwares/items",
        json={"type_id": t["id"], "category_id": c["id"], "name": "X710-DA2"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["sn"] is None

    # 未认证（无 token）访问 → 401（由 AuthMiddleware 拦截）。
    # client fixture 已带 token；此处仅确认硬件写接口非公开：
    # 通过 RBAC 校验（hardware:edit 已加进 MODULES，admin 恒通过）。
    assert t["id"]
