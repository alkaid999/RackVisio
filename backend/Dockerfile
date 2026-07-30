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

# 使用 uv 按 uv.lock 锁版本管理依赖：uv sync 默认在 /app/.venv 建虚拟环境，
# PATH 提前指向 /app/.venv/bin，确保 uvicorn 等可执行文件可被正确找到。
ENV PATH="/app/.venv/bin:$PATH"

# --frozen：严格按 uv.lock 安装、禁止浮动，构建可复现
# --no-install-project：只装第三方依赖、不装项目自身（镜像从 /app 直接跑 uvicorn）
# --no-dev：不装测试等开发依赖，保持镜像精简
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
# --timeout-graceful-shutdown 30：收到 SIGTERM 后最多等待 30s 让在途请求优雅结束，
# 配合 lifespan 关闭时 engine.dispose()/cache.close() 释放连接，避免强杀导致连接泄漏。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]
