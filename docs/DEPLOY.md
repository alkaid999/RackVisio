# RackVisio 部署与运维指南（运维学习笔记）

> 本文档面向**运维人员**，以「学习笔记 + 操作手册」的方式讲解 RackVisio 的部署与日常运维。
> 适合正在学习 Docker / DevOps 的同学边操作边理解：每一步都附带「为什么这么做」的讲解。
> 文中命令均在项目根目录（含 `docker-compose.yml`）执行。

---

## 目录

- [一、部署架构（先看懂全貌）](#一部署架构先看懂全貌)
- [二、环境要求与前置检查](#二环境要求与前置检查)
- [三、配置文件详解](#三配置文件详解)
- [四、启动流程（一步步来）](#四启动流程一步步来)
- [五、日常运维命令速查](#五日常运维命令速查)
- [六、数据持久化与备份恢复](#六数据持久化与备份恢复)
- [七、Redis 缓存层运维](#七redis-缓存层运维)
- [八、常见问题排查（排障手册）](#八常见问题排查排障手册)
- [九、安全基线（上线前必读）](#九安全基线上线前必读)
- [十、学习路径（从部署到深入）](#十学习路径从部署到深入)

---

## 一、部署架构（先看懂全貌）

### 1.1 架构图

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
│                                PostgreSQL 16 (pgdata 卷)     │
│                                [ redis 容器 ]                │
│                                redis:7.4-alpine (redisdata 卷)│
└─────────────────────────────────────────────────────────────┘
        四者通过自定义桥接网络 appnet 互通；db/backend/redis 不对外暴露端口。
```

### 1.2 服务职责一览

| 服务 | 镜像 | 容器内端口 | 对外暴露 | 职责 |
| --- | --- | --- | --- | --- |
| `db` | postgres:16.4-alpine | 5432 | ❌ 仅内网 | 持久化存储**全部业务数据** |
| `redis` | redis:7.4-alpine | 6379 | ❌ 仅内网 | 看板 / 统计缓存层（AOF 持久化） |
| `backend` | 本地构建（Python 3.12） | 8000 | ❌ nginx 反代 | `/api/v1` REST 接口 + JWT 鉴权 |
| `frontend` | 本地构建（Nginx 1.27） | 80 | ✅ `HTTP_PORT` | 托管前端静态资源 + 反代 API |

### 1.3 三个「为什么」（运维必懂）

1. **为什么只有 frontend 暴露端口？** 安全最小面原则——业务请求只经 Nginx 进入，数据库 / 后端 / Redis 不出内网，即使容器被攻破也无法直接从外部触达数据库。
2. **为什么有 healthcheck + depends_on？** 容器启动有先后依赖：backend 要等 db 就绪（`service_healthy`）再建表，否则会因「连不上数据库」反复重启；frontend 要等 backend 就绪，否则首个请求 502。这是容器编排里最常见的启动竞态问题。
3. **为什么数据要放卷（volume）里？** 容器是**无状态**的——`docker compose down` 或容器重建会丢失容器内文件。数据卷（`pgdata` / `redisdata`）由 Docker 管理、独立于容器生命周期，容器删了数据还在。

---

## 二、环境要求与前置检查

### 2.1 环境要求

| 项 | 要求 | 说明 |
| --- | --- | --- |
| 操作系统 | Linux 服务器（推荐） / Windows / macOS | 需支持 Docker Engine |
| Docker Engine | ≥ 20.10 | `docker --version` 查看 |
| Docker Compose | v2（`docker compose` 子命令） | `docker compose version` 查看 |
| 磁盘 | ≥ 5GB 可用 | 镜像（后端 ~800MB + 前端 ~80MB + PG/Redis）+ 数据卷 |
| 内存 | ≥ 2GB | PG 与后端各占数百 MB；`shm_size` 已按 256mb 配置 |

### 2.2 前置检查（动手前先跑一遍）

```bash
docker --version            # Docker Engine 版本
docker compose version      # Compose v2 确认
docker info                 # 确认 daemon 运行中（输出 Server Version 即正常）
docker compose config       # 校验 docker-compose.yml 语法与变量引用（不启动）
```

> 💡 运维笔记：`docker compose config` 是最佳「改完配置先自检」手段——它会解析 `.env` 并展开所有 `${VAR}` 引用，写错变量名或缩进语法会立刻报错，不用等到 up 才炸。

---

## 三、配置文件详解

### 3.1 涉及的文件

| 文件 | 作用 | 备注 |
| --- | --- | --- |
| `.env.example` | 环境变量模板 | 复制为 `.env` 后修改；`.env` 已被 gitignore，不会入库 |
| `.env` | 实际配置（密码 / 密钥 / 端口） | **机密文件，务必单独备份，勿提交 Git** |
| `docker-compose.yml` | 四服务编排 | 读 `.env` 中的 `${VAR:-默认值}` |
| `backend/Dockerfile` | 后端镜像 | Python 3.12-slim + uv 锁版本 |
| `frontend/Dockerfile` | 前端镜像 | 多阶段：Node 24 构建 → Nginx 托管 |
| `frontend/nginx.conf` | Nginx 配置 | SPA 回退 + `/api` 反代 |

### 3.2 环境变量说明

**数据库（PostgreSQL）**

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `POSTGRES_DB` | `rackvisio` | 数据库名；同时用于拼出后端 `DATABASE_URL` |
| `POSTGRES_USER` | `rackvisio` | 数据库用户名 |
| `POSTGRES_PASSWORD` | `rackvisio_pass` | 数据库密码（**生产务必修改**） |

> 后端 `DATABASE_URL` 由 compose 自动拼为 `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}`，无需手动设置。若密码含 `@`、`:`、`/` 等特殊字符，请使用 URL 编码。

**后端**

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ENVIRONMENT` | `production`（Docker） | `production` 下强制校验 `SECRET_KEY`，默认值**拒绝启动**（fail-closed）；`development` 仅告警 |
| `SECRET_KEY` | `change-me-in-prod-...` | JWT 签名密钥。**生产必须改为强随机值**（`openssl rand -hex 32`），否则启动失败 |
| `TOKEN_EXPIRE_HOURS` | `12` | 登录令牌有效期（小时） |
| `INITIAL_ADMIN_PASSWORD` | `admin123` | 首次 seed 的管理员密码（用户名固定 `admin`）。初始管理员首次登录**强制改密**（S-02），默认值可直接用 |
| `CACHE_TTL` | `30` | 机房统计 / 看板缓存 TTL（秒） |
| `REDIS_ENABLED` | `true` | 是否启用 Redis 缓存层；Docker 已开启 |
| `REDIS_URL` | `redis://redis:6379/0` | Redis 连接串 |

**前端 / 访问**

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HTTP_PORT` | `8080` | 宿主机映射端口（容器内固定 80） |

### 3.3 配置修改后的生效规则（高频坑）

```bash
# ✅ 正确做法：先停再启（down 会重建容器，up 才会重新读 .env）
docker compose down && docker compose up -d --build

# ❌ 错误做法：只 restart —— 容器环境变量不会重新注入
docker compose restart    # 改 .env 后无效！
```

> 💡 运维笔记：容器创建时环境变量就已「烙」进容器。`restart` 只是重启同一容器，`.env` 的改动必须 `down` 删容器 + `up` 重建才会生效。

---

## 四、启动流程（一步步来）

### 步骤 0：获取源码

```bash
# GitHub
git clone https://github.com/alkaid999/RackVisio.git
# 国内加速（Gitee 镜像）
git clone https://gitee.com/alkaid_yang/RackVisio.git
cd RackVisio
```

### 步骤 1：准备环境变量

```bash
cp .env.example .env
# 编辑 .env，至少修改两处：
#   1) POSTGRES_PASSWORD —— 数据库密码
#   2) SECRET_KEY        —— JWT 密钥（生成命令见下）
```

```bash
# 生成强随机密钥（写入 .env 的 SECRET_KEY 行）
openssl rand -hex 32
```

> ⚠️ 用默认 `SECRET_KEY` 直接 `up`，backend 会因 fail-closed 起不来——这是**特性**不是 bug（安全基线 S-01），逼你在上线前换掉弱密钥。日志里会看到 `RuntimeError: 生产环境安全校验失败，拒绝启动`。

### 步骤 2：构建并启动

```bash
docker compose up -d --build
```

首次运行会拉取基础镜像并构建 `backend` / `frontend` 两个本地镜像，随后按依赖顺序启动：

```
db（健康）→ redis（健康）→ backend（建表+种子）→ frontend
```

### 步骤 3：确认启动成功

```bash
docker compose ps                    # 四个服务都应为 Up (healthy)
docker compose logs backend | head   # 应看到缓存状态 + 建表 + seed 日志
```

**启动成功标志**（backend 日志尾部）：

```
INFO  Cache backend: Redis 已连接 (redis://redis:6379/0)
INFO  ... init_models ... migrate ... seed_data 完成
```

### 步骤 4：访问与登录

- 浏览器打开 `http://<服务器IP>:8080`（端口由 `HTTP_PORT` 控制）。
- 登录账号：`admin` / 你在 `.env` 中设置的 `INITIAL_ADMIN_PASSWORD`（默认 `admin123`）。
- **初始管理员首次登录后系统强制要求修改密码**（改密完成前无法进入其他页面）。

### 步骤 5：健康检查（运维常规动作）

```bash
curl -s http://localhost:8080/api/v1/auth/me -H "Authorization: Bearer <token>"   # API 层
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').status)"  # 容器内
```

> `health` 端点由 compose 的 backend healthcheck 使用，返回 200 即进程存活 + 应用可服务。

---

## 五、日常运维命令速查

> 以下命令均在项目根目录（含 `docker-compose.yml`）执行。

| 目的 | 命令 | 说明 |
| --- | --- | --- |
| 构建镜像 | `docker compose build` | 只构建不启动 |
| 后台启动 | `docker compose up -d` | 用现有镜像启动 |
| 构建并启动 | `docker compose up -d --build` | 代码变更后最常用 |
| 查看状态 | `docker compose ps` | 关注 STATUS 是否 `Up (healthy)` |
| 实时日志 | `docker compose logs -f` | 四服务合并输出 |
| 单服务日志 | `docker compose logs -f backend` | 只看后端 |
| 重启服务 | `docker compose restart backend` | 不重建容器（.env 变更无效） |
| 停止（保数据） | `docker compose down` | 容器删除，卷保留 |
| 停止并清数据 | `docker compose down -v` | ⚠️ **卷一并删除，数据清空** |
| 停止并删本地镜像 | `docker compose down --rmi local` | 释放磁盘 |
| 进后端容器 | `docker compose exec backend sh` | 排错 / 看环境 |
| 进数据库 CLI | `docker compose exec db psql -U rackvisio -d rackvisio` | SQL 直查 |
| 进 Redis CLI | `docker compose exec redis redis-cli` | 缓存排错 |
| 强制重建 | `docker compose up -d --force-recreate` | 忽略缓存强制重建容器 |
| 校验配置 | `docker compose config` | 改完 yml 先自检 |

### 更新已部署的项目

代码在构建时打进镜像，更新部署 = **拉代码 → 重新构建**：

```bash
git pull
docker compose up -d --build
```

- `up -d --build` 会复用已有的 `pgdata` 卷，数据原样保留。
- ⚠️ **绝不要**用 `docker compose down -v` 来「更新」——`-v` 删数据卷 = 清空所有数据。

### 重置整个系统（清空所有数据重新 seed）

```bash
docker compose down -v
docker compose up -d --build
```

> 💡 这是「出厂重置」：删掉数据库卷后 backend 首次启动会自动建表 + seed 默认管理员，相当于全新安装。

---

## 六、数据持久化与备份恢复

### 6.1 需要备份什么？

| 对象 | 是否必备份 | 说明 |
| --- | --- | --- |
| **数据库（`pgdata` 卷）** | ✅ **唯一必须** | 机房 / 机柜 / 设备 / 账号 / 日志等全部业务数据 |
| **`.env` 文件** | ✅ 强烈建议 | 含密码与 `SECRET_KEY`，丢了恢复后令牌/密码失效 |
| 前端构建产物 | ❌ | 每次 `build` 由源码生成 |
| 后端代码 | ❌ | 由 Git 管理 |
| 上传文件 | ❌ | 当前版本无文件上传功能 |

### 6.2 方式 A：逻辑备份（pg_dump，推荐）

跨 PG 大版本也可恢复，适合常规备份：

```bash
# 备份（生成 rackvisio_2026-08-01.sql）
docker compose exec db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > rackvisio_$(date +%F).sql

# 恢复
docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB" < rackvisio_2026-08-01.sql
```

> 💡 运维笔记：`pg_dump` 是逻辑备份（导出 SQL 语句），与 PostgreSQL 版本强相关度低；恢复时注意 `-T`（禁用 TTY），否则管道重定向会报错。

### 6.3 方式 B：物理备份（卷打包）

需停服且同版本 PG，适合整机迁移：

```bash
docker compose stop db
docker run --rm -v rackvisio_pgdata:/var/lib/postgresql/data -v "$PWD":/backup alpine \
  tar czf /backup/pgdata_$(date +%F).tar.gz -C /var/lib/postgresql/data .
docker compose start db
```

> 卷名 `rackvisio_pgdata` = compose 项目名（`name: rackvisio`）+ 卷名 `pgdata`。改过项目名请用 `docker volume ls` 确认实际卷名。

### 6.4 `.env` 备份

```bash
cp .env .env.bak_$(date +%F)   # 与数据库备份放在同一处妥善保管
```

---

## 七、Redis 缓存层运维

### 7.1 缓存机制速览

- 后端统一通过 `app/core/cache.py` 的 `Cache` 门面读写缓存。
- `REDIS_ENABLED=true` → 使用 Redis（`redis.asyncio`，RESP2 协议）；`false` 或不可达 → 自动降级**进程内字典**（零依赖，接口照常返回）。
- 缓存值 JSON 序列化，跨进程可读；Redis 读写异常被静默捕获 → 回源数据库（缓存 miss），**不会 500**。
- **缓存内容**：看板与统计聚合（键 `dashboard:overview`、`room_stats:{room_id}`、`racks:layout:{room_id}` 等），TTL 由 `CACHE_TTL` 控制（默认 30s）；写操作自动失效对应缓存前缀；明细列表与 `/meta` 不缓存。

### 7.2 确认缓存是否命中

```bash
# 1. 看后端启动日志（首行即缓存状态）
docker compose logs backend | head -5
#   期望：INFO Cache backend: Redis 已连接 (redis://redis:6379/0)
#   若为「内存模式」说明 Redis 没连上（降级中，功能不受影响但跨进程缓存失效）

# 2. 实时观察 Redis 键读写
docker compose exec redis redis-cli monitor

# 3. 手动查键
docker compose exec redis redis-cli keys 'dashboard:*'
```

### 7.3 运维常用操作

```bash
# 查看所有缓存键
docker compose exec redis redis-cli keys '*'

# 立即清空缓存（开发环境；生产慎用——只是缓存，清了会自动重建）
docker compose exec redis redis-cli flushall
```

> 💡 排错口诀：**「接口正常但看板偏慢」→ 先看日志首行缓存状态；「数据改了看板没变」→ 等 TTL（≤30s）或手动 flushall**。缓存问题都不是「数据丢了」，只是「还没刷新」。

### 7.4 Redis 版本钉选（血泪教训）

`docker-compose.yml` 将 redis 镜像**钉选到 `redis:7.4-alpine`**（而非 `latest`），原因：

- `redisdata` 卷内的 AOF 由 7.4 写入；**降级**到更低版本时，旧版 redis 无法加载新版 AOF → 启动失败。
- 升级前务必先备份 `redisdata` 卷（或至少 `SAVE` 一次）。

---

## 八、常见问题排查（排障手册）

| 现象 | 可能原因 / 处理 |
| --- | --- |
| 后端一直重启 / 日志报连不上 db | 等 `db` 健康检查通过；确认 `POSTGRES_*` 与拼出的 `DATABASE_URL` 一致；`docker compose logs db` 看 PG 是否正常 |
| 启动报 `RuntimeError: 生产环境安全校验失败` | `SECRET_KEY` 仍是默认值。在 `.env` 设强随机值后 `down && up -d --build` |
| 前端页面白屏 / 刷新子路由 404 | 确认 `frontend/nginx.conf` 含 SPA 回退 `try_files $uri $uri/ /index.html`（首次构建后不会缺） |
| 接口 401 / 登录失败 | `SECRET_KEY` 变更后旧令牌失效，重新登录即可；`INITIAL_ADMIN_PASSWORD` 仅首次 seed 生效，之后改密码要走系统改密 |
| 修改 `.env` 不生效 | `docker compose restart` 不会重新注入环境变量！必须 `down && up -d --build` |
| 看板/统计偏慢、疑似未命中缓存 | 看后端日志首行 `Cache backend:` 是否「内存模式」；`docker compose exec redis redis-cli monitor` 观察 `GET dashboard:*` |
| 修改数据后看板未立即刷新 | TTL 内（默认 30s）为预期；写操作已自动失效对应缓存；急用可 `flushall`（开发环境） |
| 想清空数据重来 | `docker compose down -v && docker compose up -d --build` |
| 端口 8080 被占用 | 改 `.env` 的 `HTTP_PORT`（如 `8081` 或 `80`） |
| Redis 容器起不来 | 多为版本降级导致 AOF 不兼容；备份卷后重建，或清掉 `redisdata` 卷重来 |
| 首次登录后无法进页面 | 初始管理员被**强制改密**（S-02）：先去改密码页完成改密再操作 |

### 排查方法论（运维三板斧）

1. **看状态**：`docker compose ps` —— 哪个服务没起来？状态是 Exited 还是 Restarting？
2. **看日志**：`docker compose logs -f <服务>` —— 日志是定位问题的最快路径（后端启动失败会打印具体 RuntimeError / 数据库连接异常）。
3. **进容器验证**：`docker compose exec backend sh` 后手动跑 `curl localhost:8000/health`、`python -c "import app.main"` 复现错误。

---

## 九、安全基线（上线前必读）

| 项 | 要求 | 实现方式 |
| --- | --- | --- |
| `SECRET_KEY` | **必须**改强随机值 | 默认值 + `ENVIRONMENT=production` → 后端**拒绝启动**（fail-closed，S-01） |
| 数据库密码 | **必须**改 | `POSTGRES_PASSWORD`，避免弱口令 |
| 初始管理员密码 | 首次登录强制改密 | S-02：`must_change_password` 兜底，默认密码不会长期生效 |
| 数据库端口 | 不暴露宿主机 | `db` 仅内网 `expose`，不可从外部直连 |
| HTTPS | 建议外层反代终止 TLS | 本配置已透传 `X-Forwarded-Proto`，外层 Nginx / Traefik 可直接挂证书 |
| CORS | 收敛白名单 | 默认仅允许本地开发源（`CORS_ORIGINS` 可配）；公网部署改为具体域名 |
| 定期备份 | 见第六节 | `pg_dump` 定时任务（cron） |
| 登录限流 | 内置 | 滑动窗口限流（5 次失败 / 300s）+ 全站限流（600 次/分/IP），防暴力破解 |

---

## 十、学习路径（从部署到深入）

如果你正在学运维 / Docker，建议按这个顺序把本文档和项目当教材：

1. **理解容器编排**：`docker-compose.yml` 里每个 `depends_on`、`healthcheck`、`volume` 是什么意思？对照第一节「三个为什么」。
2. **动手部署**：按第四节完整走一遍，遇到问题用第八节三板斧排查。
3. **数据管理**：练习第六节的 `pg_dump` 备份 / 恢复（在测试环境来回倒一遍）。
4. **缓存排错**：关掉 Redis（`REDIS_ENABLED=false`）观察系统行为差异，再开回来——体会「缓存降级」设计。
5. **镜像优化**：读 `backend/Dockerfile`（uv 锁版本 + 层缓存 + 非 root）与 `frontend/Dockerfile`（多阶段构建），这是容器最佳实践的范本。
6. **进阶**：加外层 HTTPS 反代、配置 cron 定时备份、接入监控（`docker stats` 起步）。

---

> 文档版本：2026-08-01 ｜ 适用架构：PostgreSQL + Redis + FastAPI + Nginx（Docker Compose 四容器）
> 相关文档：[`README.md`](../README.md)（项目简介 / 本地开发）｜ [`API.md`](./API.md)（REST 接口速查）
