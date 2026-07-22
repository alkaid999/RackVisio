"""RackVisio 机柜 3D 可视化平台后端兼容入口。

真实应用定义在 ``app/main.py``（含鉴权中间件 AuthMiddleware、全部 v1 路由、
默认管理员种子）。本文件仅做薄再导出，确保无论以 ``uvicorn main:app``
还是 ``uvicorn app.main:app`` 启动，都指向同一个（已启用鉴权的）app 实例，
避免历史上顶层 ``main.py`` 与 ``app/main.py`` 分叉导致鉴权失效。

注意：不要再在本文件里重复 include_router / 加中间件，唯一真相在 ``app/main.py``。
"""

from app.main import app

__all__ = ["app"]
