# syntax=docker/dockerfile:1

# RackVisio 前端镜像（多阶段构建）
# 阶段 1：用 Node 构建 Vite 静态产物
FROM node:20-alpine AS build
WORKDIR /app

# 国内服务器构建加速：使用阿里 npmmirror 镜像源安装依赖。
# 如需切回官方源，构建时传 --build-arg NPM_REGISTRY=https://registry.npmjs.org
ARG NPM_REGISTRY=https://registry.npmmirror.com
ENV npm_config_registry=$NPM_REGISTRY

# 依赖锁文件先拷贝，利用层缓存
COPY package*.json ./

# npm ci 会严格按 package-lock.json 中的 resolved URL 拉包，环境变量 npm_config_registry
# 覆盖不了它；因此必须把锁文件里写死的官方源 URL 批量替换为镜像源，否则仍连
# registry.npmjs.org 超时。如需切回官方源：--build-arg NPM_REGISTRY=https://registry.npmjs.org
RUN sed -i "s#https://registry.npmjs.org#${NPM_REGISTRY}#g" package-lock.json \
    && npm ci

COPY . .
RUN npm run build

# 阶段 2：Nginx 托管 dist 并反代 API 到后端
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
