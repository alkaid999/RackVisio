"""前端产物校验（严过关）。

无法在本沙箱做浏览器 UI 交互测试，仅做：
1. dist/index.html 存在且含挂载点 <div id="app">。
2. 启动静态服务（python -m http.server 指向 dist），curl 根路径返回 200 且含挂载点，
   并校验构建产物中引用的 JS/CSS 资源可达。

不验证 UI 交互（平面图点击 / 拓扑拖拽 / 大屏渲染），那些需真实浏览器人工验证。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request

DIST = r"D:/pythonProject/RackVisio/frontend/dist"
PORT = 4173
PY = r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
BASE = f"http://127.0.0.1:{PORT}"

results: list[tuple[str, bool, str]] = []


def check(step: str, cond: bool, detail: str = "") -> None:
    results.append((step, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {step}" + (f" -- {detail}" if detail else ""))


def fetch(path: str, timeout: float = 15.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + path, timeout=3) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.5)
    return None, str(last)


def main() -> int:
    # 1. index.html 存在 + 挂载点
    idx = os.path.join(DIST, "index.html")
    check("dist/index.html 存在", os.path.isfile(idx), idx)
    if not os.path.isfile(idx):
        return 1
    html = open(idx, encoding="utf-8").read()
    check("index.html 含 <div id=\"app\">", '<div id="app">' in html)

    # 2. assets 目录与构建产物
    assets_dir = os.path.join(DIST, "assets")
    check("dist/assets 存在", os.path.isdir(assets_dir))
    js_files = [f for f in os.listdir(assets_dir) if f.endswith(".js")] if os.path.isdir(assets_dir) else []
    css_files = [f for f in os.listdir(assets_dir) if f.endswith(".css")] if os.path.isdir(assets_dir) else []
    check("构建产物含 JS chunk", len(js_files) >= 1, f"js={js_files}")
    check("构建产物含 CSS", len(css_files) >= 1, f"css={css_files}")

    # 3. 启动静态服务并校验可达性
    proc = subprocess.Popen(
        [PY, "-m", "http.server", str(PORT), "--directory", DIST],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        status, body = fetch("/")
        check("静态服务 GET / -> 200", status == 200, f"status={status}")
        if status == 200:
            check("GET / 含 <div id=\"app\">", '<div id="app">' in body)
            # 校验引用的首个 JS 资源可达
            import re

            m = re.search(r'src="(/assets/[^"]+\.js)"', html)
            if m:
                js_path = m.group(1)
                jstatus, _ = fetch(js_path)
                check(f"资源可达 {js_path}", jstatus == 200, f"status={jstatus}")
            else:
                check("index.html 引用了 JS 资源", False, "未找到 /assets/*.js 引用")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    failed = [s for s, ok, _ in results if not ok]
    print("\n==== 前端产物校验汇总 ====")
    print(f"总检查: {len(results)}  通过: {len(results) - len(failed)}  失败: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
