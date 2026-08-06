"""硬件导入/导出回归测试（与机柜/机房导入一致的能力）。

覆盖：
- GET /hardwares/export：按筛选导出全量（响应含 data 数组）。
- POST /hardwares/import：类型/分类按名称定位；单行非法仅计入 failures；
  SN 重复/类型不存在/分类不匹配均失败隔离；成功行落「建档入库」留痕。
"""

from __future__ import annotations


async def _login(ac):
    resp = await ac.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    ac.headers["Authorization"] = f"Bearer {resp.json()['data']['token']}"


async def test_hardware_export(client):
    """导出：响应结构与 ok() 一致，data 为行数组（含类型/分类名称字段）。"""
    resp = await client.get("/api/v1/hardwares/export")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["code"] == 0
    assert isinstance(payload["data"], list)
    if payload["data"]:
        row = payload["data"][0]
        # 导出列应含名称/类型/分类（供回导）。
        assert "name" in row and "type_name" in row and "category_name" in row
    # 筛选参数生效（类型筛选不报错）。
    types = (await client.get("/api/v1/hardwares/types")).json()["data"]
    if types:
        r2 = await client.get("/api/v1/hardwares/export", params={"type_id": types[0]["id"]})
        assert r2.status_code == 200, r2.text


async def test_hardware_import_ok_and_failures_isolated(client):
    """导入：成功行创建 + 留痕；失败行（缺类型/SN 重复/类型不存在）隔离计 failures。"""
    types = (await client.get("/api/v1/hardwares/types")).json()["data"]
    assert types, "应有预置硬件类型"
    t = types[0]
    cats = (await client.get(f"/api/v1/hardwares/types/{t['id']}/categories")).json()["data"]
    assert cats, "类型下应有分类"
    cat = cats[0]
    sn = "IMPORT-TEST-SN-001"
    payload = {
        "items": [
            {"name": "导入-测试硬件1", "type_name": t["name"], "category_name": cat["name"], "brand": "Test", "sn": sn, "spec": "32GB"},
            {"name": "导入-类型不存在", "type_name": "不存在的类型", "category_name": "x"},
            {"name": "导入-分类不匹配", "type_name": t["name"], "category_name": "不存在的分类"},
            {"name": "导入-重复SN", "type_name": t["name"], "category_name": cat["name"], "sn": sn},
        ]
    }
    resp = await client.post("/api/v1/hardwares/import", json=payload)
    assert resp.status_code == 200, resp.text
    result = resp.json()["data"]
    assert result["created"] == 1, f"应成功导入 1 行：{result}"
    assert len(result["failures"]) == 3, f"应 3 行失败：{result}"
    msgs = " | ".join(e for f in result["failures"] for e in f["errors"])
    assert "不存在" in msgs, f"类型不存在应报错：{msgs}"
    assert "SN" in msgs, f"SN 重复应报错：{msgs}"

    # 成功行的「建档入库」留痕：查该硬件变动历史。
    items = (await client.get("/api/v1/hardwares/items", params={"keyword": "导入-测试硬件1"})).json()["data"]["items"]
    assert items, "导入的硬件应可检索到"
    hw = items[0]
    assert hw["sn"] == sn and hw["type_name"] == t["name"]
    records = (await client.get(f"/api/v1/hardwares/items/{hw['id']}/records")).json()["data"]["items"]
    assert any(r.get("operation_type") == "新增" or r.get("operation_type") == "NEW" for r in records), "应有建档入库记录"


async def test_hardware_import_requires_fields(client):
    """导入：缺必填（name/type_name/category_name）行计失败，不整批 422。"""
    resp = await client.post("/api/v1/hardwares/import", json={"items": [{"name": ""}]})
    assert resp.status_code == 200, resp.text
    result = resp.json()["data"]
    assert result["created"] == 0
    assert result["failures"], "缺必填应计失败"
