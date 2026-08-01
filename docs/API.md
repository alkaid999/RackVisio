# RackVisio REST API 接口速查

> 本文档按模块列出 RackVisio 后端（FastAPI）的全部 REST 端点，含参数说明、返回示例与错误码定义，供离线速查与集成参考。
> 完整、可交互的文档以 OpenAPI 为准：
> - **本地开发**：启动后端后访问 `http://localhost:8000/docs`（Swagger UI）或 `/redoc`。
> - **Docker 部署**：Nginx 仅反代 `/api/*`，`/docs`、`/redoc`、`/openapi.json` 不对外暴露；需进容器查看：`docker compose exec backend curl -s http://localhost:8000/openapi.json`。

---

## 目录

- [通用约定](#通用约定)
- [错误码定义](#错误码定义)
- [auth（认证）](#auth认证)
- [accounts（账号）](#accounts账号)
- [rooms（机房）](#rooms机房)
- [racks（机柜）](#racks机柜)
- [devices（设备）](#devices设备)
- [interfaces（接口或端口）](#interfaces接口或端口)
- [mount-records（上架记录）](#mount-records上架记录)
- [links（链路）](#links链路)
- [consumables（耗材）](#consumables耗材)
- [logs（日志）](#logs日志)
- [stats（统计）](#stats统计)
- [meta（展示元数据）](#meta展示元数据)

---

## 通用约定

- **Base URL**：所有接口挂在 `/api/v1` 之下（生产由前端 Nginx 反代 `/api/*` 至后端）。
- **鉴权**：除 `POST /auth/login` 外，所有接口需在请求头携带 `Authorization: Bearer <token>`。
- **权限（RBAC）**：接口按 `module:view` / `module:edit` 粒度守护（`require_permission(...)`）；无权限返回 403。
- **响应信封**：成功返回 `{ "code": 0, "message": "ok", "data": ... }`；分页返回 `{ "code": 0, "data": { "items": [...], "total": N, "page": 1, "size": 20 } }`。
- **主键**：路径参数 `{id}` 均为服务端生成的资源主键（自增 id）。
- **时区**：时间字段存储与展示遵循「UTC 存储、上海时区（UTC+8）展示」，日志类查询参数 `start_time/end_time` 按 `YYYY-MM-DD` 传入。

---

## 错误码定义

| 状态码 | 业务语义 | 说明 |
| --- | --- | --- |
| `0` | 成功 | 信封中的 `code` 字段，HTTP 200 |
| `400` | 请求错误 | 参数格式 / 业务约束不满足（如重复上架） |
| `401` | 未认证 | 未携带 / 携带无效或过期 token；登录失败 |
| `403` | 无权限 | token 有效但无该模块 `view`/`edit` 权限；账号被禁用 |
| `404` | 资源不存在 | 目标 id 不存在 |
| `409` | 冲突 | 唯一性冲突（如设备 SN / IP 重复、U 位已被占用） |
| `422` | 参数校验失败 | Pydantic 校验不通过，信封 `{ "code": 422, "message": "参数校验失败", "data": null }` |
| `429` | 请求过于频繁 | 登录限流或全站限流（默认 600 次 / 分 / IP） |
| `500` | 服务器错误 | 未捕获异常 |

> 登录失败的 `401` 与账号不存在的 `401` 统一返回「用户名或密码错误」，避免账号枚举（用户枚举防护）。

---

## auth（认证）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | 公开 | 登录，获取 JWT |
| GET | `/api/v1/auth/me` | 登录 | 获取当前登录用户信息 |
| POST | `/api/v1/auth/change-password` | 登录 | 修改当前用户密码（须验旧密码） |
| POST | `/api/v1/auth/refresh` | 登录 | 刷新令牌 |
| POST | `/api/v1/auth/logout` | 登录 | 注销（写登录日志） |

### POST /api/v1/auth/login

**请求体**

```json
{ "username": "admin", "password": "admin123" }
```

**返回示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": { "id": 1, "username": "admin", "role": "admin", "must_change_password": true }
  }
}
```

> 初始管理员首次登录 `must_change_password=true`，须先调用 `change-password` 改密后方可进入业务页面。

### POST /api/v1/auth/change-password

**请求体**

```json
{ "old_password": "admin123", "new_password": "新密码(≥6位)" }
```

---

## accounts（账号）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/accounts` | `account:view` | 账号列表 |
| POST | `/api/v1/accounts` | `account:edit` | 创建账号 |
| PUT | `/api/v1/accounts/{account_id}` | `account:edit` | 更新账号 |
| DELETE | `/api/v1/accounts/{account_id}` | `account:edit` | 删除账号 |

### POST /api/v1/accounts

**请求体**（创建账号）

```json
{
  "username": "ops01",
  "password": "initPass123",
  "display_name": "运维一号",
  "role": "operator",
  "disabled": false,
  "permissions": {
    "room": { "view": true, "edit": false },
    "device": { "view": true, "edit": true }
  }
}
```

**权限结构说明**：`permissions` 为 `{ 模块: { view, edit } }` 嵌套对象；`role` 决定权限模板基线（admin / operator / viewer），`permissions` 可覆盖细粒度。

---

## rooms（机房）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/rooms` | `room:view` | 机房列表（分页 + 筛选） |
| POST | `/api/v1/rooms` | `room:edit` | 新建机房 |
| GET | `/api/v1/rooms/export` | `room:view` | 导出机房列表（全量 CSV） |
| POST | `/api/v1/rooms/import` | `room:edit` | 批量导入机房 |
| GET | `/api/v1/rooms/{room_id}` | `room:view` | 机房详情 |
| PUT | `/api/v1/rooms/{room_id}` | `room:edit` | 更新机房 |
| DELETE | `/api/v1/rooms/{room_id}` | `room:edit` | 删除机房（级联删除机柜 / 上架记录） |
| GET | `/api/v1/rooms/{room_id}/stats` | `room:view` | 机房统计 |
| GET | `/api/v1/rooms/{room_id}/racks` | `room:view` | 机房下机柜列表 |
| POST | `/api/v1/rooms/{room_id}/racks` | `rack:edit` | 机房下新建机柜 |
| GET | `/api/v1/rooms/{room_id}/devices` | `room:view` | 机房下设备列表 |
| GET | `/api/v1/rooms/{room_id}/dashboard` | `room:view` | 机房仪表盘数据 |

### GET /api/v1/rooms（列表）

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | int | 否 | 页码（默认 1） |
| `size` | int | 否 | 每页条数（默认 20，最大 200） |
| `keyword` | str | 否 | 名称 / 编号模糊搜索 |
| `area` | str | 否 | 区域筛选 |
| `status` | str | 否 | 状态（active / inactive） |

**返回示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      { "id": 1, "name": "核心机房A", "code": "RM-A1", "area": "一号楼", "status": "active" }
    ],
    "total": 1,
    "page": 1,
    "size": 20
  }
}
```

---

## racks（机柜）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/racks` | `rack:view` | 机柜列表（按机房 / 关键字 / 状态过滤） |
| POST | `/api/v1/racks/positions` | `rack:edit` | 批量更新机柜网格坐标（2D 平面图拖拽持久化） |
| POST | `/api/v1/racks` | `rack:edit` | 新建机柜 |
| POST | `/api/v1/racks/batch` | `rack:edit` | 批量创建机柜 |
| GET | `/api/v1/racks/export` | `rack:view` | 导出机柜列表 |
| POST | `/api/v1/racks/import` | `rack:edit` | 批量导入机柜 |
| GET | `/api/v1/racks/{rack_id}` | `rack:view` | 机柜详情 |
| PUT | `/api/v1/racks/{rack_id}` | `rack:edit` | 更新机柜 |
| DELETE | `/api/v1/racks/{rack_id}` | `rack:edit` | 删除机柜 |
| GET | `/api/v1/racks/{rack_id}/devices` | `rack:view` | 机柜内设备列表 |
| GET | `/api/v1/racks/{rack_id}/u-map` | `rack:view` | 机柜 U 位占用图（自底向上，U=1 在最底） |
| POST | `/api/v1/racks/{rack_id}/check-u` | `rack:view` | 检查指定 U 位是否可上架 |
| POST | `/api/v1/racks/{rack_id}/mount` | `rack:edit` | 上架设备到指定 U 位（写记录并同步设备状态） |
| POST | `/api/v1/racks/{rack_id}/unmount` | `rack:edit` | 下架设备（有效记录置已下架） |
| GET | `/api/v1/racks/{rack_id}/candidate-devices` | `rack:view` | 候选上架设备（未挂载设备池） |

### POST /api/v1/racks/{rack_id}/mount（上架）

**请求体**

```json
{ "device_id": 10, "start_u": 1, "u_height": 2, "mounted_by": "张三" }
```

**返回示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": 88,
    "rack_id": 3,
    "device_id": 10,
    "start_u": 1,
    "occupied_u": 2,
    "status": "mounted"
  }
}
```

> 上架会校验 U 位区间是否被占用（冲突返回 409）；下架 `POST /unmount` 无需请求体。

### POST /api/v1/racks/positions（批量更新坐标）

**请求体**

```json
{ "positions": [ { "rack_id": 3, "col": 2, "row": 1 }, { "rack_id": 4, "col": 2, "row": 2 } ] }
```

---

## devices（设备）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/devices` | `device:view` | 设备列表（分页 + 多维筛选） |
| POST | `/api/v1/devices` | `device:edit` | 创建设备 |
| GET | `/api/v1/devices/export` | `device:view` | 导出设备列表（全量 CSV） |
| POST | `/api/v1/devices/import` | `device:edit` | 批量导入设备 |
| GET | `/api/v1/devices/{device_id}` | `device:view` | 设备详情 |
| PUT | `/api/v1/devices/{device_id}` | `device:edit` | 更新设备 |
| DELETE | `/api/v1/devices/{device_id}` | `device:edit` | 删除设备 |
| GET | `/api/v1/devices/{device_id}/mount-history` | `device:view` | 设备上架历史 |

### GET /api/v1/devices（列表）

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` | int | 否 | 页码（默认 1） |
| `size` | int | 否 | 每页条数（默认 50，最大 1000） |
| `room_id` | int | 否 | 机房筛选 |
| `rack_id` | int | 否 | 机柜筛选 |
| `device_type` | str | 否 | 设备类型（server / switch / firewall / storage 等，以 `/meta` 返回为准） |
| `status` | str | 否 | 状态（在库 / 已上架 / 待报废 / 借出 / 已下架） |
| `keyword` | str | 否 | 名称 / SN / IP 模糊搜索 |
| `is_asset` | bool | 否 | 仅资产（默认 true；`false` 时含设施） |

> **唯一性约束**：设备三字段唯一——SN、业务 IP（`ip_address`）、带外管理 IP（`oob_ip`）；冲突返回 409。

### POST /api/v1/devices（创建设备）

**请求体**

```json
{
  "name": "核心交换机-01",
  "device_type": "switch",
  "status": "在库",
  "sn": "SN-2024-0001",
  "ip_address": "192.168.10.1",
  "oob_ip": "192.168.100.1",
  "u_height": 2,
  "model": "H3C S6850",
  "is_asset": true
}
```

**返回示例**

```json
{ "code": 0, "message": "ok", "data": { "id": 10, "name": "核心交换机-01", "status": "在库", "is_asset": true } }
```

---

## interfaces（接口或端口）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/interfaces` | `device:view` | 全部接口列表（分页） |
| GET | `/api/v1/interfaces/unlinked` | `device:view` | 未连线接口（孤儿口）列表 |
| GET | `/api/v1/devices/{device_id}/interfaces` | `device:view` | 设备接口列表 |
| POST | `/api/v1/devices/{device_id}/interfaces` | `device:edit` | 创建设备接口 |
| POST | `/api/v1/devices/{device_id}/interfaces/batch` | `device:edit` | 批量创建设备接口 |
| PUT | `/api/v1/interfaces/{interface_id}` | `device:edit` | 更新接口 |
| DELETE | `/api/v1/interfaces/{interface_id}` | `device:edit` | 删除接口 |

### POST /api/v1/devices/{device_id}/interfaces（创建接口）

**请求体**

```json
{
  "name": "GE1/0/1",
  "interface_type": "rj45",
  "speed": "1G",
  "role": "data"
}
```

**批量创建**（`/batch`）：请求体为数组 `[{...接口字段}, ...]`，逐条校验，单条非法不影响其他条。

---

## mount-records（上架记录）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/mount-records` | `device:view` | 上架记录列表（多维过滤 + `export=true` 全量导出） |
| PATCH | `/api/v1/mount-records/{record_id}` | `device:edit` | 编辑上架记录（上架人 / 下架人） |
| DELETE | `/api/v1/mount-records/{record_id}` | `device:edit` | 删除上架记录 |

### GET /api/v1/mount-records（列表）

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` / `size` | int | 否 | 分页（默认 1 / 20，size 最大 200） |
| `export` | bool | 否 | `true` 时忽略分页返回全量（前端 Excel 导出用） |
| `device_name` / `device_code` | str | 否 | 设备名 / 编码过滤 |
| `op_type` | str | 否 | 操作类型（上架 / 下架） |
| `start_time` / `end_time` | str | 否 | 时间范围 `YYYY-MM-DD` |

---

## links（链路）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/links` | `link:view` | 链路列表（分页 + 筛选） |
| POST | `/api/v1/links` | `link:edit` | 创建链路 |
| GET | `/api/v1/links/by-interface/{interface_id}` | `link:view` | 按接口查询链路 |
| GET | `/api/v1/links/by-device/{device_id}` | `link:view` | 设备视角链路（本端 / 对端，含对端信息） |
| PUT | `/api/v1/links/{link_id}` | `link:edit` | 更新链路 |
| DELETE | `/api/v1/links/{link_id}` | `link:edit` | 删除链路（断开） |

### POST /api/v1/links（创建链路）

**请求体**

```json
{
  "source_interface_id": 12,
  "target_interface_id": 45,
  "medium": "fiber",
  "connector_type": "lc",
  "cable_length": "12m",
  "remark": "核心-汇聚互联"
}
```

> 对端可为系统外端点（`target_external` 模式）或系统内接口（`target_interface_id`），二选一。链路实体的真实外键是接口（`source_interface_id` / `target_interface_id`）而非设备。

### GET /api/v1/links（列表）

**查询参数**：`page` / `size`（默认 1 / 50，最大 1000）、`keyword`（设备名 / 接口名）、`medium`（介质）、`connector_type`（连接器）。

---

## consumables（耗材）

### 类型（types）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/consumables/types` | `consumable:view` | 耗材类型列表 |
| POST | `/api/v1/consumables/types` | `consumable:edit` | 新建耗材类型 |
| GET | `/api/v1/consumables/types/{type_id}` | `consumable:view` | 类型详情 |
| PUT | `/api/v1/consumables/types/{type_id}` | `consumable:edit` | 更新类型 |
| DELETE | `/api/v1/consumables/types/{type_id}` | `consumable:edit` | 删除类型 |

### 分类（categories）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/consumables/types/{type_id}/categories` | `consumable:view` | 类型下分类列表 |
| POST | `/api/v1/consumables/types/{type_id}/categories` | `consumable:edit` | 新建分类 |
| GET | `/api/v1/consumables/categories/{category_id}` | `consumable:view` | 分类详情 |
| PUT | `/api/v1/consumables/categories/{category_id}` | `consumable:edit` | 更新分类 |
| DELETE | `/api/v1/consumables/categories/{category_id}` | `consumable:edit` | 删除分类 |

### 条目（items）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/consumables/items` | `consumable:view` | 耗材条目列表 |
| POST | `/api/v1/consumables/items` | `consumable:edit` | 新建耗材条目 |
| GET | `/api/v1/consumables/items/{item_id}` | `consumable:view` | 条目详情 |
| PUT | `/api/v1/consumables/items/{item_id}` | `consumable:edit` | 更新条目 |
| DELETE | `/api/v1/consumables/items/{item_id}` | `consumable:edit` | 删除条目 |
| POST | `/api/v1/consumables/items/{item_id}/adjust` | `consumable:edit` | 库存变动（入库 / 出库，写变动记录） |
| GET | `/api/v1/consumables/items/{item_id}/records` | `consumable:view` | 条目变动记录 |
| GET | `/api/v1/consumables/records` | `consumable:view` | 全部耗材变动记录 |

### POST /api/v1/consumables/items/{item_id}/adjust（库存变动）

**请求体**

```json
{ "operation_type": "入库", "quantity": 10, "operator": "张三" }
```

> `operation_type` 支持：入库 / 领用 / 报废 / 盘点等（以 `/meta` 返回为准）；领用与报废扣减库存，入库增加。

---

## logs（日志）

> 由请求级中间件自动记录，端点零侵入；GET 请求不记操作日志。

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/logs/operations` | `account:view` | 操作日志列表 |
| GET | `/api/v1/logs/logins` | `account:view` | 登录日志列表 |
| POST | `/api/v1/logs/cleanup` | `account:view` | 手动清理超过保留期的日志 |

### GET /api/v1/logs/operations

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `page` / `size` | int | 否 | 分页（默认 1 / 20，size 最大 200） |
| `action` | str | 否 | 动作（create / update / delete） |
| `keyword` | str | 否 | 操作人 / 目标模糊搜索 |
| `status_code` | int | 否 | HTTP 状态码过滤 |
| `start_time` / `end_time` | str | 否 | 时间范围 `YYYY-MM-DD`（按上海展示时区） |

**返回示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": 100,
        "operator_id": 1,
        "operator_name": "admin",
        "method": "POST",
        "path": "/api/v1/racks/3/mount",
        "status_code": 200,
        "action": "create",
        "resource": "mount-record",
        "target": "核心交换机-01 → 机柜A(1U)",
        "ip": "192.168.1.10",
        "detail": { "data": { "device_id": 10, "start_u": 1 } },
        "created_at": "2026-08-01T10:30:00"
      }
    ],
    "total": 1,
    "page": 1,
    "size": 20
  }
}
```

### POST /api/v1/logs/cleanup

**请求体**

```json
{ "days": 180 }
```

> `days` 可选（≥1）：覆盖默认保留期 `LOG_RETENTION_DAYS`（默认 180 天）计算 cutoff，硬删两表（operation_logs / login_logs）早于 cutoff 的记录；返回删除条数。

---

## stats（统计）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/stats/overview` | 任一模块 view | 全局统计总览 |

**返回示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "room_count": 2,
    "rack_count": 12,
    "device_count": 30,
    "used_u": 86,
    "total_u": 504,
    "overall_utilization": 17,
    "device_status": [ { "status": "已上架", "count": 22 } ],
    "device_type_distribution": [ { "type": "switch", "count": 8 } ],
    "link_count": 15,
    "power_rated": 24000,
    "power_used": 5600
  }
}
```

> 权限要求：拥有 `room:view` / `rack:view` / `device:view` / `link:view` / `account:view` 任一即可。该接口走 Redis 缓存（键 `dashboard:overview`）。

---

## meta（展示元数据）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/meta` | 任一模块 view | 状态 / 类型中文标签与颜色、使用率阈值、可选值枚举 |

**返回示例**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "device_status": [ { "value": "在库", "label": "在库", "color": "#909399" } ],
    "rack_status": [ { "value": "active", "label": "正常" } ],
    "device_types": [ { "value": "server", "label": "服务器" } ],
    "link_mediums": [ { "value": "fiber", "label": "光纤" } ],
    "connector_types": [ { "value": "lc", "label": "LC" } ],
    "usage_thresholds": { "warn": 70, "crit": 85 }
  }
}
```

> `/meta` 是前端展示元数据的**单一数据源**（`stores/meta.js` → `utils/constants.js`），不缓存。前端所有下拉选项、状态标签、状态颜色均从此接口拉取；后端 `app/core/meta.py` 与前端 `utils/constants.js` 三处同步维护。

---

## 快速验证（curl 示例）

登录并调用受保护接口：

```bash
# 1. 登录获取 token（jq 提取）
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.data.token')

# 2. 携带 token 查询机房列表
curl -s http://localhost:8000/api/v1/rooms?page=1\&size=10 \
  -H "Authorization: Bearer $TOKEN" | jq

# 3. 查看 OpenAPI 定义
curl -s http://localhost:8000/openapi.json | jq '.paths | keys'
```

---

> 字段级约束（必填、长度、枚举值）以 `/docs` 中 Pydantic Schema 为准；本文档聚焦端点形态与调用方式。文档版本：2026-08-01。
