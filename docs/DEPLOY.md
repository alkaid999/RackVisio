# RackVisio Docker 部署指南

本文档说明如何使用 Docker Compose 将 RackVisio（机柜 3D 可视化平台）以
**PostgreSQL + 后端 API + 前端 Nginx** 的三容器架构部署到服务器（含内网环境）。

---

## 一、部署架构

```
┌─────────────────────────────────────────────────────────────┐
│  宿主机                                                      │
│                                                              │
│   :8080 ──► [ frontend 容器 ]                               │
│                Nginx (80)                                    │
│                ├─ 托管 dist 静态资源（Vue SPA）              │
│                └─ 反代 /api/* ──► backend:8000              │
│                                          │                  │
│                                [ backend 容器 ]              │
│                                FastAPI + uvicorn (8000)      │
│                                          │                  │
│                                [ db 容器 ]                   │
│                                PostgreSQL 16                │
│                                pgdata 持久化卷               │
└─────────────────────────────────────────────────────────────┘
        三者通过自定义桥接网络 appnet 互通；db/backend 不对外暴露端口。
```

| 服务     | 镜像                | 端口（容器内） | 对外暴露        | 作用                                   |
| -------- | ------------------- | -------------- | --------------- | -------------------------------------- |
| `db`     | postgres:16-alpine  | 5432           | 否（仅内网）    | 持久化存储所有业务数据                 |
| `backend`| 本地构建（Python）  | 8000           | 否（nginx 反代）| 提供 `/api/v1` REST 接口 + JWT 鉴权    |
| `frontend`| 本地构建（Nginx）  | 80             | 是（`HTTP_PORT`）| 托管前端 + 反代 API                    |

---

## 二、文件清单

| 文件                       | 说明                                              |
| -------------------------- | ------------------------------------------------- |
| `docker-compose.yml`       | 三服务编排（含健康检查、依赖顺序、数据卷）        |
| `backend/Dockerfile`       | 后端镜像：Python 3.12-slim + uvicorn             |
| `backend/.dockerignore`    | 排除 `.venv` / `*.db` 等无需入镜的内容            |
| `frontend/Dockerfile`      | 前端镜像：Node 构建 → Nginx 托管（多阶段）        |
| `frontend/nginx.conf`      | Nginx：SPA 回退 + `/api` 反代后端                  |
| `frontend/.dockerignore`   | 排除 `node_modules` / `dist` 等                   |
| `.env.example`             | 环境变量模板（复制为 `.env` 后修改）              |

---

## 三、快速开始

### 1. 前置条件
- 服务器已安装 **Docker Engine** 与 **Docker Compose v2**（`docker compose` 子命令）。
  ```bash
  docker --version
  docker compose version
  ```

### 2. 准备环境变量
```bash
cp .env.example .env
# 编辑 .env，至少修改：
#   POSTGRES_PASSWORD  —— 数据库密码（强密码）
#   SECRET_KEY         —— JWT 签名密钥（openssl rand -hex 32）
#   INITIAL_ADMIN_PASSWORD —— 管理员初始密码
```

### 3. 构建并启动
```bash
docker compose up -d --build
```
首次运行会拉取基础镜像并构建 `backend` / `frontend` 两个本地镜像，随后按顺序启动：
`db`（健康后）→ `backend`（建表+种子）→ `frontend`。

### 4. 访问与登录
- 浏览器打开 `http://<服务器IP>:8080`（端口由 `.env` 的 `HTTP_PORT` 控制，默认 8080）。
- 登录账号：`admin` / 你在 `.env` 中设置的 `INITIAL_ADMIN_PASSWORD`（默认 `admin123`）。
- **首次登录后请立即修改管理员密码**（系统设置 → 账号）。

---

## 四、常用命令

> 以下命令均在项目根目录（含 `docker-compose.yml`）执行。

| 目的                 | 命令                                                |
| -------------------- | --------------------------------------------------- |
| 构建镜像             | `docker compose build`                             |
| 后台启动             | `docker compose up -d`                             |
| 构建并后台启动       | `docker compose up -d --build`                     |
| 查看运行状态         | `docker compose ps`                                |
| 实时查看日志         | `docker compose logs -f`                           |
| 仅看某服务日志       | `docker compose logs -f backend`                   |
| 重启某服务           | `docker compose restart backend`                   |
| 停止（保留数据卷）   | `docker compose down`                              |
| 停止并删除数据卷     | `docker compose down -v` （⚠️ 数据将清空）         |
| 停止并删镜像         | `docker compose down --rmi local`                  |
| 进入后端容器排错     | `docker compose exec backend sh`                   |
| 进入数据库命令行     | `docker compose exec db psql -U rackvisio -d rackvisio` |
| 重新拉取/重建        | `docker compose up -d --force-recreate`            |

**重置整个系统（清空所有数据重新 seed）：**
```bash
docker compose down -v
docker compose up -d --build
```

---

## 五、环境变量配置说明

`.env` 中的变量由 `docker-compose.yml` 读取，并注入到对应容器。

### 数据库（PostgreSQL）
| 变量                | 默认          | 说明                                              |
| ------------------- | ------------- | ------------------------------------------------- |
| `POSTGRES_DB`       | `rackvisio`   | 数据库名；同时用于拼出后端 `DATABASE_URL`         |
| `POSTGRES_USER`     | `rackvisio`   | 数据库用户名                                      |
| `POSTGRES_PASSWORD` | `rackvisio_pass` | 数据库密码（**生产务必修改**）                  |

> 后端 `DATABASE_URL` 由 compose 自动拼为：
> `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}`
> 无需手动设置。若密码含 `@`、`:`、`/` 等特殊字符，请使用 URL 编码。

### 后端
| 变量                    | 默认                              | 说明                                              |
| ----------------------- | --------------------------------- | ------------------------------------------------- |
| `SECRET_KEY`            | `change-me-in-prod-...`          | JWT HMAC 签名密钥，**生产必须改为强随机值**       |
| `TOKEN_EXPIRE_HOURS`    | `12`                              | 登录令牌有效期（小时）                            |
| `INITIAL_ADMIN_PASSWORD`| `admin123`                        | 首次 seed 的默认管理员密码（用户名固定 `admin`）  |
| `CACHE_TTL`             | `30`                              | 机房统计/看板缓存 TTL（秒）                       |
| `REDIS_ENABLED`         | `false`                           | 是否启用 Redis 缓存（见下方「扩展说明」）         |

### 前端 / 访问
| 变量         | 默认    | 说明                                  |
| ------------ | ------- | ------------------------------------- |
| `HTTP_PORT`  | `8080`  | 宿主机映射端口（容器内固定 80）       |

---

## 六、数据持久化与备份

- 数据库数据保存在命名卷 `pgdata` 中（`docker compose down` 不带 `-v` 不会删除）。
- **备份：**
  ```bash
  docker compose exec db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > rackvisio_$(date +%F).sql
  ```
- **恢复：**
  ```bash
  docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB" < rackvisio_2026-01-01.sql
  ```

---

## 七、从 SQLite 切换到 PostgreSQL 的必要改动（已实现）

原项目默认使用 SQLite（`sqlite+aiosqlite`）。`app/core/config.py` 已支持通过
`DATABASE_URL` 切换到 PostgreSQL，但存在一个阻碍 PostgreSQL 启动的方言专属导入，
本次部署已修复：

- **`backend/app/models/user.py`**：
  将 `from sqlalchemy.dialects.sqlite import CHAR`
  改为通用 `from sqlalchemy import CHAR`。
  原因：`sqlalchemy.dialects.sqlite.CHAR` 是 SQLite 专属类型，在 PostgreSQL 上导入/建表会失败；
  通用 `sqlalchemy.CHAR` 在 SQLite 与 PostgreSQL 下均可用，改动对原 SQLite 开发环境完全兼容。

其余连接层（`app/core/database.py` 的 `_create_engine`）、建表层（`Base.metadata.create_all`）、
启动 seed（`lifespan` 中的 `init_models` → `migrate` → `seed_data`）均已方言无关，
无需额外修改即可在 PostgreSQL 上运行。

---

## 八、扩展说明与注意事项

### 1. 缓存与多实例
当前缓存为**进程内字典**。后端以**单 worker** 启动时完全一致；
若需水平扩展（多 worker：`--workers N`，或多后端实例 + 负载均衡），进程内缓存会出现
跨进程不一致，此时应启用 Redis（`REDIS_ENABLED=true`）。
> ⚠️ 注意：当前 `RedisCache` 直接存储 Python 字典（未序列化），启用前需先补 `pickle/json`
> 序列化处理，否则写入缓存会报错。该改动不在本次部署范围内。
>
> 📌 `docker-compose.yml` 已预置一个**默认注释掉的 `redis` 服务段**（及其 `redisdata` 卷）。
> 轻量单实例部署无需启用；将来需多实例时，取消该段注释、在 `.env` 设
> `REDIS_ENABLED=true` 与 `REDIS_URL=redis://redis:6379/0` 即可，无需重写编排。

### 2. CORS
`backend/app/main.py` 的 `CORSMiddleware` 当前为 `allow_origins=["*"]`（含 `allow_credentials=True`）。
内网可接受；若需公网或跨域前端，请收敛为具体的白名单域名。

### 3. 端口冲突
若宿主机 8080 被占用，修改 `.env` 的 `HTTP_PORT`（如 `HTTP_PORT=80` 或 `9000`）。

### 4. 安全基线建议（生产）
- 修改 `.env` 中所有默认密码与 `SECRET_KEY`；
- 通过反向代理（如外层 Nginx / Traefik）增加 HTTPS；
- 数据库 `db` 服务不暴露宿主机端口（当前默认如此），仅内网互通；
- 定期备份 `pgdata` 卷或执行 `pg_dump`。

---

## 九、故障排查

| 现象                              | 可能原因 / 处理                                   |
| --------------------------------- | ------------------------------------------------- |
| 后端一直重启 / 日志报连不上 db    | 等待 `db` 健康检查通过；确认 `POSTGRES_*` 与 `DATABASE_URL` 一致 |
| 启动报 `CHAR` / dialect 相关错误  | 确认已应用 `user.py` 的 `sqlalchemy.CHAR` 改动    |
| 前端页面白屏 / 刷新子路由 404     | 确认 `frontend/nginx.conf` 已正确 COPY 且含 SPA 回退 `try_files` |
| 接口 401 / 登录失败               | 检查 `SECRET_KEY` 是否变更（变更后旧令牌失效，重新登录）；`INITIAL_ADMIN_PASSWORD` 仅首次 seed 生效 |
| 修改 `.env` 不生效                | `docker compose down` 后 `up -d --build` 重新加载 |
| 想清空数据重来                    | `docker compose down -v && docker compose up -d --build` |

---

> 文档版本：2026-07-19 ｜ 适用架构：PostgreSQL + FastAPI + Nginx（Docker Compose）
