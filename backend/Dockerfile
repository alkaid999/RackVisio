# syntax=docker/dockerfile:1

# RackVisio 后端镜像
# 基础镜像：Python 3.12-slim（轻量 Debian，含基础编译工具链）
FROM python:3.12-slim

WORKDIR /app

# 关闭字节码写入与输出缓冲，便于容器日志实时刷新
# 同时指定清华 PyPI 镜像，避免国内服务器拉取官方源超时（可改为官方源 https://pypi.org/simple）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn \
    UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_NO_CACHE=1

# uv 官方 Docker 范式：建独立 venv 并把依赖按锁版本装进去。
# 设置 VIRTUAL_ENV + PATH 后，后续 uv / uvicorn 都走该 venv，运行行为与原来（系统 Python）一致，
# 仅多了一层隔离，镜像更干净、可被 uv 精确管理。
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 基于 uv.lock 精确锁版本安装运行依赖（--frozen 禁止浮动，与本地 uv sync 完全一致、可复现）。
# --no-install-project：只装第三方依赖、不装项目自身（镜像从 /app 直接跑 uvicorn，无需 editable 安装）。
# --no-dev：不装 test 等开发依赖，保持镜像精简（与原 requirements.txt 行为一致）。
# 仅当 uv.lock 或 pyproject.toml 变更时才重装，充分利用层缓存。
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project \
    && uv cache clean

# 复制应用源码（node_modules / .venv / *.db 已被 .dockerignore 排除）
COPY . .

# 使用非 root 用户运行，降低容器被攻破时的影响面
RUN useradd -m -s /usr/sbin/nologin appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 生产启动：单 worker。
# 说明：当前缓存为进程内字典，多 worker 会导致缓存不一致；
# 如需水平扩展（多 worker / 多实例），请先将 REDIS_ENABLED 置 true 并修复 RedisCache 序列化，
# 再追加 --workers N。详见 DEPLOY.md。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
