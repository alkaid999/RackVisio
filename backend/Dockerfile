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
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# 先装依赖：利用层缓存，仅当 requirements.txt 变更时才重装
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

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
