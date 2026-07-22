"""端到端集成冒烟（严过关）。

独立验证全栈串联：后台启动真实 uvicorn（backend.main:app，端口 8001，使用临时 SQLite），
用 httpx 异步客户端按 PRD 主链路依次断言：

① 创建机房 -> ② 机房下创建机柜(记 rack_id/total_u) -> ③ 机柜合法 U 位创建设备 A
-> ④ 用与 A 重叠的 U 位创建设备(冲突) -> 期望 409 且 message 说明冲突 U 位
   （注：冲突设备被拒，为完成链路串联另以合法 U 位创建设备 B 继续）
-> ⑤ 给 A、B 各建端口 -> ⑥ 用 A、B 端口建链路 -> ⑦ 拓扑(按 room) 含 A/B 与链路
-> ⑧ 机房大屏 KPI(rack_count>=1 / device 计数 / utilization 合理)

打印每条断言结果；任一步失败则进程退出码非 0。脚本不作为 pytest 用例（文件名非 test_ 前缀）。
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time

import httpx

PORT = 8001
BASE = f"http://127.0.0.1:{PORT}"
PY = r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
ROOT = r"D:\pythonProject\RackVisio"

_results: list[tuple[str, bool, str]] = []


def check(step: str, cond: bool, detail: str = "") -> None:
    _results.append((step, cond, detail))
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {step}" + (f" -- {detail}" if detail else ""))


async def wait_health(client: httpx.AsyncClient, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = await client.get("/health")
            if r.status_code == 200 and r.json().get("data", {}).get("status") == "up":
                return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


async def main() -> int:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["REDIS_ENABLED"] = "false"

    log_path = os.path.join(ROOT, "backend", "tests", "e2e_uvicorn.log")
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
    )
    print(f"uvicorn 已启动 (pid={proc.pid})，日志: {log_path}")

    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=20.0) as client:
            # 等待服务就绪
            ready = await wait_health(client)
            check("服务启动 /health", ready)
            if not ready:
                return 1

            # ① 创建机房
            r = await client.post(
                "/api/v1/rooms",
                json={
                    "name": "E2E机房",
                    "code": "ROOM-E2E",
                    "location": "3F",
                    "category": "T2",
                    "rows": 1,
                    "cols": 1,
                },
            )
            check("① 创建机房", r.status_code == 200, f"status={r.status_code}")
            if r.status_code != 200:
                return 1
            room_id = r.json()["data"]["id"]

            # ② 机房下创建机柜
            r = await client.post(
                f"/api/v1/rooms/{room_id}/racks",
                json={
                    "name": "E2E机柜",
                    "code": "RACK-E2E",
                    "row_num": 0,
                    "col_num": 0,
                    "total_u": 10,
                },
            )
            check("② 创建机柜", r.status_code == 200, f"status={r.status_code}")
            if r.status_code != 200:
                return 1
            rack = r.json()["data"]
            rack_id = rack["id"]
            total_u = rack["total_u"]

            # ③ 合法 U 位创建设备 A（U1-5）
            r = await client.post(
                "/api/v1/devices",
                json={
                    "rack_id": rack_id,
                    "name": "E2E-A",
                    "device_type": "server",
                    "start_u": 1,
                    "size_u": 5,
                },
            )
            check("③ 创建设备A(合法U)", r.status_code == 201, f"status={r.status_code}")
            if r.status_code != 201:
                return 1
            A = r.json()["data"]["id"]

            # ④ 重叠 U 位创建设备（冲突） -> 期望 409
            r = await client.post(
                "/api/v1/devices",
                json={
                    "rack_id": rack_id,
                    "name": "E2E-B-conflict",
                    "device_type": "server",
                    "start_u": 1,
                    "size_u": 5,
                },
            )
            ok_conflict = r.status_code == 409 and "冲突" in r.json().get("message", "")
            check("④ 重叠U创建设备->409", ok_conflict, f"status={r.status_code} msg={r.json().get('message','') if r.status_code!=200 else ''}")

            # ④b 为完成链路，以合法 U 位（U6-10）创建设备 B
            r = await client.post(
                "/api/v1/devices",
                json={
                    "rack_id": rack_id,
                    "name": "E2E-B",
                    "device_type": "switch",
                    "start_u": 6,
                    "size_u": 5,
                },
            )
            check("④b 创建设备B(合法U)", r.status_code == 201, f"status={r.status_code}")
            if r.status_code != 201:
                return 1
            B = r.json()["data"]["id"]

            # ⑤ 给 A、B 各建接口
            ra = await client.post(
                f"/api/v1/devices/{A}/interfaces",
                json={"name": "a1", "interface_type": "electrical", "speed": "10G"},
            )
            rb = await client.post(
                f"/api/v1/devices/{B}/interfaces",
                json={"name": "b1", "interface_type": "optical", "speed": "10G"},
            )
            check("⑤ 创建设备A接口", ra.status_code == 201, f"status={ra.status_code}")
            check("⑤ 创建设备B接口", rb.status_code == 201, f"status={rb.status_code}")
            if ra.status_code != 201 or rb.status_code != 201:
                return 1
            pa = ra.json()["data"]["id"]
            pb = rb.json()["data"]["id"]

            # ⑥ 用 A、B 接口建链路
            r = await client.post(
                "/api/v1/links",
                json={
                    "source_interface_id": pa,
                    "target_interface_id": pb,
                    "medium": "tp",
                    "connector_type": "cat5e",
                },
            )
            check("⑥ 创建链路", r.status_code == 201, f"status={r.status_code}")
            if r.status_code != 201:
                return 1
            link_id = r.json()["data"]["id"]

            # ⑦ 拓扑(按 room) 应含 A、B 与链路
            r = await client.get("/api/v1/topology", params={"room_id": room_id})
            check("⑦ 获取拓扑", r.status_code == 200, f"status={r.status_code}")
            if r.status_code != 200:
                return 1
            topo = r.json()["data"]
            node_ids = {n["id"] for n in topo["nodes"]}
            has_a_b = A in node_ids and B in node_ids
            edge_pairs = {(e["source"], e["target"]) for e in topo["edges"]}
            link_in_topo = (A, B) in edge_pairs or (B, A) in edge_pairs
            check("⑦ 拓扑含设备A与B", has_a_b, f"nodes={len(topo['nodes'])}")
            check("⑦ 拓扑含链路", link_in_topo, f"edges={len(topo['edges'])} link_id={link_id}")

            # ⑧ 机房大屏 KPI
            r = await client.get(f"/api/v1/rooms/{room_id}/dashboard")
            check("⑧ 获取大屏", r.status_code == 200, f"status={r.status_code}")
            if r.status_code != 200:
                return 1
            kpi = r.json()["data"]["kpi"]
            rack_ok = isinstance(kpi.get("rack_count"), int) and kpi["rack_count"] >= 1
            dev_ok = isinstance(kpi.get("device_count"), int) and kpi["device_count"] >= 2
            util = kpi.get("utilization")
            util_ok = isinstance(util, (int, float)) and 0.0 <= util <= 100.0
            check("⑧ KPI.rack_count>=1", rack_ok, f"rack_count={kpi.get('rack_count')}")
            check("⑧ KPI.device_count>=2", dev_ok, f"device_count={kpi.get('device_count')}")
            check("⑧ KPI.utilization∈[0,100]", util_ok, f"utilization={util}")

        failed = [s for s, ok, _ in _results if not ok]
        print("\n==== E2E 汇总 ====")
        print(f"总断言: {len(_results)}  通过: {len(_results) - len(failed)}  失败: {len(failed)}")
        return 1 if failed else 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        logf.close()
        try:
            os.remove(db_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
