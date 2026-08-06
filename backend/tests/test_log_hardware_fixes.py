"""操作日志修复回归测试（硬件资源分类 + 新建硬件单条整合 + 清除日志留痕）。

覆盖：
- 硬件管理操作日志 resource 精确归类（不再「未知」）：类型/分类/条目/分配/回收。
- 新建硬件：一次操作 = 一条日志，detail.data 含全部提交字段（不拆分）。
- 「清除日志」操作本身产生日志记录（resource=log、action=cleanup）。
"""

from __future__ import annotations

from typing import Optional


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


async def test_hardware_resource_classification(client):
    """硬件类型/分类/条目/分配/回收的日志 resource 均应归类为 hardware（不再「未知」）。"""
    # 类型
    t = await client.post("/api/v1/hardwares/types", json={"name": "日志测试-内存"})
    assert t.status_code == 200, t.text
    type_id = t.json()["data"]["id"]
    # 分类
    c = await client.post(
        f"/api/v1/hardwares/types/{type_id}/categories", json={"name": "日志测试-DDR5"}
    )
    assert c.status_code == 200, c.text
    cat_id = c.json()["data"]["id"]
    # 条目（独立个体，含品牌/SN/规格多字段）
    hw = await client.post(
        "/api/v1/hardwares/items",
        json={
            "type_id": type_id,
            "category_id": cat_id,
            "name": "日志测试-32GB内存条",
            "brand": "Kingston",
            "sn": "LOG-SN-001",
            "spec": "32GB DDR5-4800 ECC",
        },
    )
    assert hw.status_code == 200, hw.text
    hw_id = hw.json()["data"]["id"]

    logs = await _op_logs(client)
    # 按路径精确找三条硬件相关日志。
    type_log = next((i for i in logs if i["path"] == "/api/v1/hardwares/types"), None)
    cat_log = next(
        (i for i in logs if i["path"] == f"/api/v1/hardwares/types/{type_id}/categories"), None
    )
    item_log = next((i for i in logs if i["path"] == "/api/v1/hardwares/items"), None)
    assert type_log and cat_log and item_log, "应产生类型/分类/条目三条硬件日志"

    for log, label in ((type_log, "类型"), (cat_log, "分类"), (item_log, "条目")):
        assert log["resource"] == "hardware", (
            f"硬件{label}日志 resource 应为 hardware（修复「未知」），实际：{log['resource']!r}"
        )
    assert item_log["action"] == "create"

    # 分配（设备添加硬件）→ resource=hardware, action=assign
    dev = await _create_device(client, "日志测试-服务器")
    resp = await client.post(
        f"/api/v1/hardwares/devices/{dev}/hardwares",
        json={"hardware_item_id": hw_id},
    )
    assert resp.status_code == 200, resp.text
    # 回收 → action=recover
    resp = await client.delete(f"/api/v1/hardwares/devices/{dev}/hardwares/{hw_id}")
    assert resp.status_code == 200, resp.text

    logs = await _op_logs(client)
    assign_log = next(
        (i for i in logs if i["method"] == "POST" and i["path"].endswith("/hardwares")),
        None,
    )
    recover_log = next(
        (i for i in logs if i["method"] == "DELETE" and "hardwares" in i["path"] and dev in i["path"]),
        None,
    )
    assert assign_log, "应产生硬件分配日志"
    assert assign_log["resource"] == "hardware"
    assert assign_log["action"] == "assign", f"分配动作应为 assign，实际：{assign_log['action']!r}"
    assert assign_log["target"] == "日志测试-32GB内存条 @ 日志测试-服务器", (
        f"分配 target 应为「硬件 @ 设备」，实际：{assign_log['target']!r}"
    )
    assert recover_log, "应产生硬件回收日志"
    assert recover_log["resource"] == "hardware"
    assert recover_log["action"] == "recover", f"回收动作应为 recover，实际：{recover_log['action']!r}"


async def test_hardware_create_is_single_log(client):
    """新建硬件（多字段）应归纳为【一条】完整日志，detail.data 含全部字段。"""
    t = await client.post("/api/v1/hardwares/types", json={"name": "日志测试-硬盘"})
    type_id = t.json()["data"]["id"]
    c = await client.post(
        f"/api/v1/hardwares/types/{type_id}/categories", json={"name": "日志测试-NVMe"}
    )
    cat_id = c.json()["data"]["id"]
    hw = await client.post(
        "/api/v1/hardwares/items",
        json={
            "type_id": type_id,
            "category_id": cat_id,
            "name": "日志测试-1.6T NVMe",
            "brand": "Samsung",
            "sn": "LOG-SN-002",
            "spec": "1.6T NVMe U.2",
        },
    )
    assert hw.status_code == 200, hw.text
    hw_id = hw.json()["data"]["id"]

    logs = await _op_logs(client)
    # 新建硬件应只有【一条】日志（路径精确匹配）。
    create_logs = [i for i in logs if i["path"] == "/api/v1/hardwares/items"]
    assert len(create_logs) == 1, (
        f"新建硬件应只产生一条日志（预期整合为单条），实际 {len(create_logs)} 条"
    )
    log = create_logs[0]
    detail = log.get("detail") or {}
    data = detail.get("data") or {}
    # detail.data 含全部提交字段（不拆分）。
    assert data.get("name") == "日志测试-1.6T NVMe"
    assert data.get("brand") == "Samsung"
    assert data.get("sn") == "LOG-SN-002"
    assert data.get("spec") == "1.6T NVMe U.2"
    assert data.get("type_id") == type_id
    assert data.get("category_id") == cat_id
    # 外键名称已解析（detail.names）。
    names = detail.get("names") or {}
    assert names.get("category_id") == "日志测试-NVMe", f"分类外键应解析为名称：{names}"
    # target 富化：条目名。
    assert log["target"] == "日志测试-1.6T NVMe"


async def test_cleanup_logs_records_itself(client):
    """「清除日志」操作本身应产生一条日志（resource=log, action=cleanup）。"""
    resp = await client.post("/api/v1/logs/cleanup", json={"days": 180})
    assert resp.status_code == 200, resp.text

    logs = await _op_logs(client)
    cleanup_log = next(
        (i for i in logs if i["method"] == "POST" and i["path"].endswith("/logs/cleanup")),
        None,
    )
    assert cleanup_log, "「清除日志」操作应产生日志记录（修复缺失）"
    assert cleanup_log["resource"] == "log", f"resource 应为 log，实际：{cleanup_log['resource']!r}"
    assert cleanup_log["action"] == "cleanup", f"action 应为 cleanup，实际：{cleanup_log['action']!r}"
    assert cleanup_log["target"] == "清理 180 天前的日志", (
        f"target 应展示清理范围，实际：{cleanup_log['target']!r}"
    )
    # 操作人已记录（admin）。
    assert cleanup_log["operator_name"] == "admin"
