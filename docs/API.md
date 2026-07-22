# RackVisio REST API 接口速查

> 本文档按模块列出 RackVisio 后端（`FastAPI`）的全部 REST 端点，供离线速查。
> 完整、可交互的文档以 OpenAPI 为准：启动后端后访问 `http://localhost:8000/docs`（Swagger UI）或 `/redoc`。

## 通用约定

- **Base URL**：所有接口挂在 `/api/v1` 之下（生产由前端 Nginx 反代 `/api/*`）。
- **鉴权**：除 `POST /auth/login` 外，所有接口需在请求头携带 `Authorization: Bearer <token>`。
  - 登录：`POST /api/v1/auth/login`，请求体 `{ "username": "...", "password": "..." }`，返回 `data.token`。
  - 当前用户：`GET /api/v1/auth/me`。
- **权限（RBAC）**：接口按 `module:view` / `module:edit` 粒度守护（`require_permission(...)`）。
- **响应信封**：成功返回 `{ "code": 0, "message": "...", "data": ... }`；分页返回 `{ "code": 0, "data": { "items": [...], "total": N, "page": 1, "page_size": 20 } }`；校验失败返回 `{ "code": 422, "message": "参数校验失败", "data": null }`。

---

## auth（认证）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | 登录，获取 JWT（body: `{username, password}`） |
| GET | `/api/v1/auth/me` | 获取当前登录用户信息 |

## accounts（账号）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/accounts` | 账号列表 |
| POST | `/api/v1/accounts` | 创建账号 |
| PUT | `/api/v1/accounts/{account_id}` | 更新账号 |
| DELETE | `/api/v1/accounts/{account_id}` | 删除账号 |

## rooms（机房）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/rooms` | 机房列表 |
| POST | `/api/v1/rooms` | 新建机房 |
| GET | `/api/v1/rooms/{room_id}` | 机房详情 |
| PUT | `/api/v1/rooms/{room_id}` | 更新机房 |
| DELETE | `/api/v1/rooms/{room_id}` | 删除机房 |
| GET | `/api/v1/rooms/{room_id}/stats` | 机房统计 |
| GET | `/api/v1/rooms/{room_id}/racks` | 机房下机柜列表 |
| POST | `/api/v1/rooms/{room_id}/racks` | 机房下新建机柜 |
| GET | `/api/v1/rooms/{room_id}/dashboard` | 机房仪表盘数据 |

## racks（机柜）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/racks` | 机柜列表（支持按机房 / 关键字 / 状态过滤） |
| POST | `/api/v1/racks` | 新建机柜 |
| POST | `/api/v1/racks/positions` | 批量更新机柜网格坐标（2D 平面图拖拽持久化） |
| GET | `/api/v1/racks/{rack_id}` | 机柜详情 |
| PUT | `/api/v1/racks/{rack_id}` | 更新机柜 |
| DELETE | `/api/v1/racks/{rack_id}` | 删除机柜 |
| GET | `/api/v1/racks/{rack_id}/devices` | 机柜内设备列表 |
| GET | `/api/v1/racks/{rack_id}/u-map` | 机柜 U 位占用图（自底向上，U=1 在最底） |
| POST | `/api/v1/racks/{rack_id}/check-u` | 检查指定 U 位是否可上架 |
| POST | `/api/v1/racks/{rack_id}/mount` | 上架设备到指定 U 位（写记录并同步设备状态） |
| POST | `/api/v1/racks/{rack_id}/unmount` | 下架设备（有效记录置已下架） |
| GET | `/api/v1/racks/{rack_id}/candidate-devices` | 候选上架设备（未挂载设备池） |

## devices（设备）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/devices` | 设备列表 |
| POST | `/api/v1/devices` | 创建设备 |
| GET | `/api/v1/devices/{device_id}` | 设备详情 |
| PUT | `/api/v1/devices/{device_id}` | 更新设备 |
| DELETE | `/api/v1/devices/{device_id}` | 删除设备 |
| GET | `/api/v1/devices/{device_id}/mount-history` | 设备上架历史 |

## interfaces（接口 / 端口）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/devices/{device_id}/interfaces` | 设备接口列表 |
| POST | `/api/v1/devices/{device_id}/interfaces` | 创建设备接口 |
| POST | `/api/v1/devices/{device_id}/interfaces/batch` | 批量创建设备接口 |
| PUT | `/api/v1/interfaces/{interface_id}` | 更新接口 |
| DELETE | `/api/v1/interfaces/{interface_id}` | 删除接口 |

## mount-records（上架记录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| PATCH | `/api/v1/mount-records/{record_id}` | 编辑上架记录（上架人 / 下架人） |
| DELETE | `/api/v1/mount-records/{record_id}` | 删除上架记录 |

## links（链路）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/links` | 链路列表 |
| POST | `/api/v1/links` | 创建链路 |
| GET | `/api/v1/links/by-interface/{interface_id}` | 按接口查询链路 |
| PUT | `/api/v1/links/{link_id}` | 更新链路 |
| DELETE | `/api/v1/links/{link_id}` | 删除链路 |

## consumables（耗材）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/consumables/types` | 耗材类型列表 |
| POST | `/api/v1/consumables/types` | 新建耗材类型 |
| GET | `/api/v1/consumables/types/{type_id}` | 类型详情 |
| PUT | `/api/v1/consumables/types/{type_id}` | 更新类型 |
| DELETE | `/api/v1/consumables/types/{type_id}` | 删除类型 |
| GET | `/api/v1/consumables/types/{type_id}/categories` | 类型下分类列表 |
| POST | `/api/v1/consumables/types/{type_id}/categories` | 新建分类 |
| GET | `/api/v1/consumables/categories/{category_id}` | 分类详情 |
| PUT | `/api/v1/consumables/categories/{category_id}` | 更新分类 |
| DELETE | `/api/v1/consumables/categories/{category_id}` | 删除分类 |
| GET | `/api/v1/consumables/items` | 耗材条目列表 |
| POST | `/api/v1/consumables/items` | 新建耗材条目 |
| GET | `/api/v1/consumables/items/{item_id}` | 条目详情 |
| PUT | `/api/v1/consumables/items/{item_id}` | 更新条目 |
| DELETE | `/api/v1/consumables/items/{item_id}` | 删除条目 |
| POST | `/api/v1/consumables/items/{item_id}/adjust` | 库存变动（入库 / 出库，写变动记录） |
| GET | `/api/v1/consumables/items/{item_id}/records` | 条目变动记录 |
| GET | `/api/v1/consumables/records` | 全部耗材变动记录 |

## stats（统计）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/stats/overview` | 全局统计总览（机房 / 机柜 / 设备 / 使用率 / 链路 / 耗材等） |

## meta（展示元数据单一源）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/meta` | 状态 / 类型中文标签与颜色、使用率阈值（前端统一从此拉取） |

## topology（拓扑）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/topology` | 链路拓扑（全量节点与边） |
| GET | `/api/v1/topology/device/{device_id}` | 指定设备的拓扑 |

---

> 提示：`{id}` 类路径参数均为服务端生成的资源主键（UUID / 自增 id）。批量录入数据时可结合本表直接调用对应 `POST` 接口；字段约束以 `/docs` 中 Pydantic Schema 为准。
