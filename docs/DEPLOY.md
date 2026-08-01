# RackVisio Docker 部署指南

本文档说明如何使用 Docker Compose 将 RackVisio（机柜 3D 可视化平台）以
**PostgreSQL + Redis + 后端 API + 前端 Nginx** 的四容器架构部署到服务器（含内网环境）。

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
│                                ├─▶ db:5432（业务数据）       │
│                                └─▶ redis:6379（缓存层）     │
│                                          │                  │
│                                [ db 容器 ]                   │
│                                PostgreSQL 16                │
│                                pgdata 持久化卷               │
│                                                              │
│                                [ redis 容器 ]                │
│                                redis:7.4-alpine             │
│                                redisdata 持久化卷            │
└─────────────────────────────────────────────────────────────┘
        四者通过自定义桥接网络 appnet 互通；db/backend/redis 不对外暴露端口。
```

| 服务     | 镜像                | 端口（容器内） | 对外暴露        | 作用                                   |
| -------- | ------------------- | -------------- | --------------- | -------------------------------------- |
| `db`     | postgres:16.4-alpine | 5432           | 否（仅内网）    | 持久化存储所有业务数据                 |
| `redis`  | redis:7.4-alpine    | 6379           | 否（仅内网）    | 看板/统计缓存层（AOF 持久化）          |
| `backend`| 本地构建（Python）  | 8000           | 否（nginx 反代）| 提供 `/api/v1` REST 接口 + JWT 鉴权    |
| `frontend`| 本地构建（Nginx）  | 80             | 是（`HTTP_PORT`）| 托管前端 + 反代 API                    |

---

## 二、文件清单与镜像构建详解

| 文件                       | 说明                                              |
| -------------------------- | ------------------------------------------------- |
| `docker-compose.yml`       | 四服务编排（db/redis/backend/frontend，含健康检查、依赖顺序、数据卷） |
| `backend/Dockerfile`       | 后端镜像：Python 3.12-slim + uv 锁版本构建 + uvicorn |
| `backend/.dockerignore`    | 排除 `.venv` / `*.db` 等无需入镜的内容            |
| `frontend/Dockerfile`      | 前端镜像：Node 24 构建 → Nginx 托管（多阶段）     |
| `frontend/nginx.conf`      | Nginx：SPA 回退 + `/api` 反代后端                  |
| `frontend/.dockerignore`   | 排除 `node_modules` / `dist` 等                   |
| `.env.example`             | 环境变量模板（复制为 `.env` 后修改）              |

### 后端镜像（backend/Dockerfile）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
# 关闭字节码写入与输出缓冲；指定清华 PyPI 镜像（国内加速，可换官方源）
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_NO_CACHE=1
# uv 按 uv.lock 建 .venv，PATH 提前指向 /app/.venv/bin 确保 uvicorn 可被找到
ENV PATH="/app/.venv/bin:$PATH"
# 先拷依赖清单，利用层缓存（仅 uv.lock 变更才重装）
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project \
    && uv cache clean
# 复制源码（.venv/*.db 已被 .dockerignore 排除）
COPY . .
# 降权：用非 root 的 appuser 运行
RUN useradd -m -s /usr/sbin/nologin appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
# 单 worker：缓存已走 Redis（共享），多 worker 也保持一致；单 worker 足以覆盖轻量场景
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", 8000]
```

要点：
- **层缓存**：依赖安装单独成层，改代码不改 `uv.lock` 时秒过；
- **国内加速**：默认走清华 PyPI 源，海外服务器可把 `PIP_INDEX_URL` 改回 `https://pypi.org/simple`；
- **非 root**：以 `appuser` 运行，缩小容器被攻破时的权限面；
- **单 worker**：当前缓存已走 Redis（见第八节），多 worker 同样共享缓存、保持一致；默认单 worker 足以覆盖轻量场景。

### 前端镜像（frontend/Dockerfile，多阶段）

```dockerfile
# 阶段 1：用 Node 构建 Vite 静态产物
FROM node:24-alpine AS build
WORKDIR /app
# 国内加速：阿里 npmmirror（可用 --build-arg NPM_REGISTRY=官方源 切回）
ARG NPM_REGISTRY=https://registry.npmmirror.com
ENV npm_config_registry=$NPM_REGISTRY
COPY package*.json ./
# npm ci 严格按锁文件 resolved URL 拉包，环境变量盖不住 → 需 sed 替换锁文件里的源
RUN sed -i "s#https://registry.npmjs.org#${NPM_REGISTRY}#g" package-lock.json \
    && npm ci
COPY . .
RUN npm run build
# 阶段 2：Nginx 托管 dist 并反代 API
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

要点：
- **多阶段构建**：最终镜像只含 Nginx + `dist`，不含 Node/构建工具，体积更小、攻击面更小；
- **锁文件坑**：`npm ci` 会按 `package-lock.json` 里写死的源拉包，光设 `npm_config_registry` 不够，所以先 `sed` 把锁文件里的 `registry.npmjs.org` 替换成镜像源；
- **可切官方源**：`docker compose build --build-arg NPM_REGISTRY=https://registry.npmjs.org frontend`；
- 构建基础镜像固定为 `node:24-alpine`（与 README「Node ≥ 24（配套 Vite 8）」一致，锁定 24 以保证可复现）。

### 前端反代（frontend/nginx.conf）

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
    # SPA 历史路由：刷新子路由（如 /devices）不 404
    location / {
        try_files $uri $uri/ /index.html;
    }
    # 反代 /api/* 到 compose 内网服务名 backend:8000
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

要点：
- **SPA 回退**：`try_files ... /index.html` 让 Vue Router（history 模式）刷新子路由不 404；
- **相对路径反代**：前端请求用相对路径 `/api/v1/*`，由 Nginx 转发到 `backend:8000`（compose 内网服务名，无需暴露后端端口）；
- 外层如需 HTTPS，在更外层 Nginx / Traefik 终止 TLS 即可，本配置已透传 `X-Forwarded-Proto`。

### 编排（docker-compose.yml）

三容器通过自定义桥接网络 `appnet` 互通，`db` / `backend` 不暴露宿主机端口，仅 `frontend` 映射 `HTTP_PORT:80`：

| 服务 | 镜像 | 关键点 |
| --- | --- | --- |
| `db` | postgres:16.4-alpine | 数据卷 `pgdata` 持久化；`healthcheck` 用 `pg_isready` 探活，供 `backend` 的 `depends_on: condition: service_healthy` 等待就绪 |
| `backend` | 本地构建 | `DATABASE_URL` 由 `.env` 的 `POSTGRES_*` 自动拼为 `postgres://db:5432/...`；`depends_on: db.service_healthy`；`expose 8000`（仅内网） |
| `frontend` | 本地构建 | `depends_on: backend.service_healthy`；`ports: HTTP_PORT:80` |

> 📌 **代码是打进镜像的**：改了后端 / 前端源码后，必须 `docker compose up -d --build`（或单独 `build backend` / `build frontend`）重新构建镜像，光 `restart` 不会生效。

---

## 三、快速开始

### 0. 获取源码（GitHub 或国内 Gitee 二选一）

```bash
# GitHub
git clone https://github.com/alkaid999/RackVisio.git
# 国内加速（Gitee 镜像）
git clone https://gitee.com/alkaid_yang/RackVisio.git

cd RackVisio
```

> 进入项目根目录（含 `docker-compose.yml`）后再继续后续步骤。

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
#   SECRET_KEY         —— JWT 签名密钥（openssl rand -hex 32，production 下为默认值会拒绝启动）
#   INITIAL_ADMIN_PASSWORD —— 管理员初始密码（可选，S-02 强制改密兜底，默认 admin123 可直接用）
```

> ⚠️ **安全基线建议（production 环境）**：Docker 部署默认 `ENVIRONMENT=production`，后端启动时会
> **强制校验 `SECRET_KEY`**——仍为默认值（`change-me-in-prod-rackvisio-secret-key`）会**拒绝启动**，
> 必须在 `.env` 用强随机值覆盖后再 `up`：
> ```bash
> SECRET_KEY=$(openssl rand -hex 32)            # 写入 .env 的 SECRET_KEY
> ```
> `INITIAL_ADMIN_PASSWORD` 不拦截：初始管理员首次登录被**强制修改密码**（S-02 must_change_password），
> 默认值 `admin123` 不会长期生效；如需自定义初始密码可在 `.env` 覆盖。
> 仅本地开发可设 `ENVIRONMENT=development` 使用默认值（SECRET_KEY 仅打印告警不拦截）。

### 3. 构建并启动
```bash
docker compose up -d --build
```
首次运行会拉取基础镜像并构建 `backend` / `frontend` 两个本地镜像，随后按顺序启动：
`db`（健康后）→ `backend`（建表+种子）→ `frontend`。

### 4. 访问与登录
- 浏览器打开 `http://<服务器IP>:8080`（端口由 `.env` 的 `HTTP_PORT` 控制，默认 8080）。
- 登录账号：`admin` / 你在 `.env` 中设置的 `INITIAL_ADMIN_PASSWORD`（默认 `admin123`）。
- **初始管理员首次登录后系统会强制要求修改密码**（改密完成前无法进入其他页面）。

### 5. 更新已部署的项目（重新拉取并重启）

代码在构建时打进镜像，因此更新部署 = **拉取最新源码 → 重新构建并启动**，整个过程**无需删除数据库卷、也无需从备份恢复**：

```bash
git pull                             # 拉取最新代码（Gitee 镜像同理）
docker compose up -d --build         # 重新构建 backend / frontend 镜像并启动
```

- `up -d --build` 会复用已有的 `pgdata` 卷，机房 / 机柜 / 设备 / 审计等全部数据原样保留。
- 仅拉取镜像仓库新镜像时用 `docker compose pull && docker compose up -d`；本项目镜像由源码本地构建，通常走 `git pull` + `--build`。
- ⚠️ 不要用 `docker compose down -v` 来「更新」——`-v` 会删除数据卷，所有数据将被清空（那属于「重置整个系统」，见下方第四节）。
- 修改 `.env` 后必须 `docker compose down && docker compose up -d --build` 才能重新加载。

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
| `ENVIRONMENT`           | `production`（Docker）           | 运行环境。`production` 下后端启动时**强制校验** `SECRET_KEY`，仍为默认值**拒绝启动**（fail-closed）；`INITIAL_ADMIN_PASSWORD` 不校验（S-02 强制改密兜底）。本地开发可改为 `development`（SECRET_KEY 仅告警不拦截）。 |
| `SECRET_KEY`            | `change-me-in-prod-...`          | JWT HMAC 签名密钥。**生产必须改为强随机值**（如 `openssl rand -hex 32`）；保持默认值时 production 启动将失败并提示覆盖。 |
| `TOKEN_EXPIRE_HOURS`    | `12`                              | 登录令牌有效期（小时）                            |
| `INITIAL_ADMIN_PASSWORD`| `admin123`                        | 首次 seed 的默认管理员密码（用户名固定 `admin`）。初始管理员首次登录**强制改密**（S-02），默认值可直接使用；如需自定义初始密码可覆盖本项。 |
| `CACHE_TTL`             | `30`                              | 机房统计/看板缓存 TTL（秒）                       |
| `REDIS_ENABLED`         | `true`（Docker）/ `false`（本地） | 是否启用 Redis 缓存层；Docker 部署已开启          |
| `REDIS_URL`             | `redis://redis:6379/0`            | Redis 连接串（`REDIS_ENABLED=true` 时生效）       |

### 前端 / 访问
| 变量         | 默认    | 说明                                  |
| ------------ | ------- | ------------------------------------- |
| `HTTP_PORT`  | `8080`  | 宿主机映射端口（容器内固定 80）       |

---

## 六、数据持久化与备份

### 需要备份什么？

RackVisio 的**全部业务数据都落在数据库里**，前端与后端本身不存储任何用户数据：

- ✅ **数据库（唯一必须备份）**：机房、机柜、设备、账号、审计等所有数据。
- ✅ **`.env` 文件（建议一并备份）**：内含数据库密码、`SECRET_KEY`（JWT 签名密钥）、
  `INITIAL_ADMIN_PASSWORD`（管理员初始密码）。它是配置而非业务数据，可凭 `.env.example`
  重建，但保留原文件可避免恢复后管理员密码 / 旧令牌失效。`.env` 已被 gitignore，不会随
  代码入库，需单独留存。
- ❌ **前端（构建产物 / 静态资源）**：每次 `docker compose build` 由源码重新生成，无需备份。
- ❌ **后端（代码）**：无状态，数据全在数据库；源码由 Git 管理，无需单独备份。
- ❌ **上传文件**：当前版本无文件上传功能，磁盘上不存在需要持久化的用户文件。

### Docker（PostgreSQL）备份与恢复

数据库数据保存在命名卷 `pgdata` 中（`docker compose down` 不带 `-v` 不会删除）。

**方式 A：逻辑备份（推荐，跨版本可恢复）**

- 备份：
  ```bash
  docker compose exec db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > rackvisio_$(date +%F).sql
  ```
- 恢复：
  ```bash
  docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB" < rackvisio_2026-01-01.sql
  ```

**方式 B：直接备份数据卷（物理备份，需停服且同版本 PG）**

```bash
docker compose stop db
docker run --rm -v rackvisio_pgdata:/var/lib/postgresql/data -v "$PWD":/backup alpine \
  tar czf /backup/pgdata_$(date +%F).tar.gz -C /var/lib/postgresql/data .
docker compose start db
```

> 卷名 `rackvisio_pgdata` 由 compose 项目名（默认目录名 `rackvisio`）+ 卷名 `pgdata` 组合而成，
> 若改过项目名请用 `docker volume ls` 确认实际卷名。

### 本地开发（SQLite）备份

本地开发默认使用 `backend/idc.db`（SQLite 文件），直接复制该文件即可：

```bash
cp backend/idc.db backend/idc.db.bak_$(date +%F)
```

### `.env` 备份建议

```bash
cp .env .env.bak_$(date +%F)   # 与数据库备份放在同一处妥善保管
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

### PostgreSQL 方言兼容注意事项

除 `CHAR` 外，迁移中还出现过**布尔列使用整数字面量**导致 PostgreSQL 启动崩溃的问题：

- `init_db.py` 的设施迁移原写 `UPDATE devices SET is_asset=1 ...`，PostgreSQL 的 `BOOLEAN`
  是独立类型，`1` 被当作整数 → `DatatypeMismatchError: column "is_asset" is of type boolean
  but expression is of type integer`。已改为绑定参数 `{val: True}`（SQLAlchemy 按值的类型
  推断为 Boolean，PG 收到 `true` / SQLite 收到 `1`）。
- `models/device.py` 的 `is_asset` 列 `server_default="1"` 在全新 PG 库 `create_all` 时同样会
  因 `DEFAULT 1` 崩溃，已改为 `server_default=true()`（方言感知：PG→`true` / SQLite→`1`）。

📌 经验：**任何布尔列都不要用 `0/1` 整数字面量**，统一走 ORM / 绑定参数 / `true()`，
  这样 SQLite 与 PostgreSQL 才能通吃。

---

## 八、扩展说明与注意事项

### 1. Redis 缓存（默认开启）

后端统一通过 `app/core/cache.py` 的 `Cache` 门面读写缓存：

- `REDIS_ENABLED=true` → 使用 **Redis**（`RedisCache`，`redis.asyncio` 驱动，RESP2 协议）。
- `REDIS_ENABLED=false`（或 Redis 不可达）→ 自动降级为**进程内字典**（`InMemoryCache`），零依赖，接口正常返回。

缓存值采用 JSON 序列化，确保跨进程可读；任何 Redis 读写异常都会被静默捕获并降级为回源数据库（缓存 miss），不会出现 500。

**Docker 部署默认已启用 Redis**：`docker-compose.yml` 的 `redis` 服务段（及其 `redisdata` 持久化卷）已就绪，后端 `REDIS_ENABLED=true`、`REDIS_URL=redis://redis:6379/0`，并以 `depends_on: redis: condition: service_healthy` 保证启动顺序。本地开发在 `.env` 设 `REDIS_ENABLED=true` 并填 `REDIS_URL=redis://127.0.0.1:6379/0` 即可。

**缓存内容**：看板与统计类聚合结果，键名形如 `dashboard:overview`、`dashboard:{room_id}`、`room_stats:{room_id}`、`racks:layout:{room_id}`，TTL 由 `CACHE_TTL`（默认 30 秒，环境变量可调）控制。任意写操作（增删改机房 / 机柜 / 设备）都会自动失效对应机房的上述缓存前缀，保证数据新鲜；明细列表与常量接口（`/meta`）不缓存。

### 2. CORS
`backend/app/main.py` 的 `CORSMiddleware` 当前为 `allow_origins=["*"]`（含 `allow_credentials=True`）。
内网可接受；若需公网或跨域前端，请收敛为具体的白名单域名。

### 3. 端口冲突
若宿主机 8080 被占用，修改 `.env` 的 `HTTP_PORT`（如 `HTTP_PORT=80` 或 `9000`）。

### 4. 安全基线建议（生产）
- 修改 `.env` 中所有默认密码与 `SECRET_KEY`（**production 环境会打印安全告警提示，强烈建议上线前覆盖**，未改也能启动）；
- 通过反向代理（如外层 Nginx / Traefik）增加 HTTPS；
- 数据库 `db` 服务不暴露宿主机端口（当前默认如此），仅内网互通；
- 定期备份 `pgdata` 卷或执行 `pg_dump`。

---

## 九、故障排查

| 现象                              | 可能原因 / 处理                                   |
| --------------------------------- | ------------------------------------------------- |
| 后端一直重启 / 日志报连不上 db    | 等待 `db` 健康检查通过；确认 `POSTGRES_*` 与 `DATABASE_URL` 一致 |
| 启动报 `CHAR` / dialect 相关错误  | 确认已应用 `user.py` 的 `sqlalchemy.CHAR` 改动    |
| 启动报 `DatatypeMismatchError: column "is_asset" is of type boolean but expression is of type integer` | 布尔列被赋了整数；确认已应用提交 `331c4dc`（`is_asset` 改用布尔绑定参数 / `true()`），并重新 `docker compose build backend` |
| 前端页面白屏 / 刷新子路由 404     | 确认 `frontend/nginx.conf` 已正确 COPY 且含 SPA 回退 `try_files` |
| 接口 401 / 登录失败               | 检查 `SECRET_KEY` 是否变更（变更后旧令牌失效，重新登录）；`INITIAL_ADMIN_PASSWORD` 仅首次 seed 生效 |
| 修改 `.env` 不生效                | `docker compose down` 后 `up -d --build` 重新加载 |
| 看板/统计接口响应偏慢、疑似未命中缓存 | 确认 `REDIS_ENABLED=true` 且 `REDIS_URL` 可达；查看后端启动日志首行 `Cache backend:` 状态；用 `docker compose exec redis redis-cli monitor` 观察是否有 `SET/GET dashboard:*` |
| 修改数据后看板未立即刷新          | 缓存 TTL 内（默认 30 秒）为预期行为；写操作会自动失效对应机房缓存，最多 30 秒后生效；如需立即刷新：`docker compose exec redis redis-cli flushall`（开发环境） |
| 想清空数据重来                    | `docker compose down -v && docker compose up -d --build` |

---

> 文档版本：2026-07-30 ｜ 适用架构：PostgreSQL + FastAPI + Nginx（Docker Compose）
