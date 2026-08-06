"""类型/分类手动排序回归测试（sort_order 持久化）。

覆盖：
- 类型 reorder：按传入顺序持久化，重新进入（重新 GET）仍保持自定义顺序。
- 分类 reorder：同类型内按传入顺序持久化。
- 耗材与硬件两个模块均生效。
"""

from __future__ import annotations


async def _types(ac, prefix):
    resp = await ac.get(f"/api/v1/{prefix}/types")
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _cats(ac, prefix, type_id):
    resp = await ac.get(f"/api/v1/{prefix}/types/{type_id}/categories")
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def test_hardware_type_reorder_persisted(client):
    """硬件类型 reorder 后重新拉取顺序保持（持久化）。"""
    types = await _types(client, "hardwares")
    assert len(types) >= 3, "预置类型应 >= 3"
    ids = [t["id"] for t in types]
    reversed_ids = list(reversed(ids))

    resp = await client.post("/api/v1/hardwares/types/reorder", json={"ids": reversed_ids})
    assert resp.status_code == 200, resp.text

    # 重新拉取（模拟重新进入页面）→ 顺序保持为逆序。
    after = await _types(client, "hardwares")
    assert [t["id"] for t in after] == reversed_ids, (
        f"reorder 应持久化，重新拉取后顺序应保持逆序"
    )

    # 恢复原序（避免影响其他用例）。
    assert (await client.post("/api/v1/hardwares/types/reorder", json={"ids": ids})).status_code == 200


async def test_consumable_type_reorder_persisted(client):
    """耗材类型 reorder 持久化。"""
    types = await _types(client, "consumables")
    assert len(types) >= 2
    ids = [t["id"] for t in types]
    reversed_ids = list(reversed(ids))

    resp = await client.post("/api/v1/consumables/types/reorder", json={"ids": reversed_ids})
    assert resp.status_code == 200, resp.text

    after = await _types(client, "consumables")
    assert [t["id"] for t in after] == reversed_ids
    # 恢复原序。
    assert (await client.post("/api/v1/consumables/types/reorder", json={"ids": ids})).status_code == 200


async def test_category_reorder_persisted(client):
    """分类 reorder：类型内按传入顺序持久化（耗材 + 硬件）。"""
    # 硬件：取首个类型（预置分类）。
    htypes = await _types(client, "hardwares")
    hcats = await _cats(client, "hardwares", htypes[0]["id"])
    assert len(hcats) >= 2, "硬件预置类型应有 >= 2 个分类"
    cat_ids = [c["id"] for c in hcats]
    reversed_cats = list(reversed(cat_ids))
    resp = await client.post(
        f"/api/v1/hardwares/types/{htypes[0]['id']}/categories/reorder",
        json={"ids": reversed_cats},
    )
    assert resp.status_code == 200, resp.text
    after = await _cats(client, "hardwares", htypes[0]["id"])
    assert [c["id"] for c in after] == reversed_cats, "分类 reorder 应持久化"
    # 恢复原序。
    assert (
        await client.post(
            f"/api/v1/hardwares/types/{htypes[0]['id']}/categories/reorder",
            json={"ids": cat_ids},
        )
    ).status_code == 200

    # 耗材：取首个类型。
    ctypes = await _types(client, "consumables")
    ccats = await _cats(client, "consumables", ctypes[0]["id"])
    assert len(ccats) >= 2
    ccids = [c["id"] for c in ccats]
    resp = await client.post(
        f"/api/v1/consumables/types/{ctypes[0]['id']}/categories/reorder",
        json={"ids": list(reversed(ccids))},
    )
    assert resp.status_code == 200, resp.text
    after = await _cats(client, "consumables", ctypes[0]["id"])
    assert [c["id"] for c in after] == list(reversed(ccids))
