# syntax=docker/dockerfile:1

# RackVisio 前端镜像（多阶段构建）
# 阶段 1：用 Node 构建 Vite 静态产物
FROM node:24-alpine AS build
WORKDIR /app

# 国内服务器构建加速：使用阿里 npmmirror 镜像源安装依赖。
# 如需切回官方源，构建时传 --build-arg NPM_REGISTRY=https://registry.npmjs.org
ARG NPM_REGISTRY=https://registry.npmmirror.com
ENV npm_config_registry=$NPM_REGISTRY

# ---- 构建缓存策略：依赖锁文件先拷贝、再安装依赖 ----
# package-lock.json 未变化时，这一层（npm ci 全量依赖）直接命中构建缓存；
# 源码变更不影响本层，大幅缩短「只改代码」时的重复构建时间。
COPY package*.json ./

# npm ci 会严格按 package-lock.json 中的 resolved URL 拉包，环境变量 npm_config_registry
# 覆盖不了它；因此必须把锁文件里写死的官方源 URL 批量替换为镜像源，否则仍连
# registry.npmjs.org 超时。如需切回官方源：--build-arg NPM_REGISTRY=https://registry.npmjs.org
RUN sed -i "s#https://registry.npmjs.org#${NPM_REGISTRY}#g" package-lock.json \
    && npm ci

COPY . .
RUN npm run build

# 阶段 2：Nginx 托管 dist 并反代 API 到后端（仅含 Nginx + dist，无 Node/构建工具）
FROM nginx:1.27-alpine

# 非 root 运行：Nginx 官方镜像默认以 root 启动 master 进程，切到内置 nginx 用户（uid 101）。
# 需保证非 root 可写的运行时路径：
#   1) pid 文件：官方 nginx.conf 的 pid 指令指向 /run/nginx.pid（旧版为 /var/run/nginx.pid，
#      /var/run 是 /run 的符号链接），/run 是 root 所有的 tmpfs，非 root 写不了 → 改到 /tmp/nginx.pid
#      （/tmp 1777 世界可写）。
#   2) "user nginx;" 指令：master 进程已非 root 时该指令无效并产生 warn，直接删除。
#   3) /var/cache/nginx：客户端 body 临时文件 / 代理缓存目录，chown 给 nginx 用户。
# sed 用宽松匹配 ^pid ... nginx.pid; 同时兼容 /run 与 /var/run 两种写法；
# 注意 alpine 是 busybox sed（非 GNU），不支持 \s / \+ 扩展正则，必须用 POSIX 写法
# [ [:space:] ] 字符类 + .* 通配（GNU 与 busybox 通用）。
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i \
      -e 's|^pid[[:space:]][[:space:]]*.*nginx\.pid;|pid /tmp/nginx.pid;|' \
      -e '/^[[:space:]]*user[[:space:]][[:space:]]*nginx;/d' \
      /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /var/cache/nginx /usr/share/nginx/html
USER nginx

EXPOSE 80
