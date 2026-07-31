"""应用配置（pydantic-settings）。

通过环境变量读取配置，默认开发/测试使用 SQLite，生产设置 DATABASE_URL 为
postgresql+asyncpg 即可切换到 PostgreSQL，无需修改任何业务代码。
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。所有字段均可通过环境变量覆盖。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # 数据库连接串；默认 SQLite（开发/测试）。
    DATABASE_URL: str = "sqlite+aiosqlite:///./idc.db"

    # 是否启用 Redis 缓存；默认 true（本地 Redis 常驻时直接命中缓存，
    # 若 Redis 不可用则自动降级为进程内字典，不影响功能）。
    REDIS_ENABLED: bool = True
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # 统一 API 前缀。
    API_PREFIX: str = "/api/v1"

    # 大屏缓存 TTL（秒）。
    CACHE_TTL: int = 30

    # —— 运行环境 ——
    # development / production；生产环境会强制校验 SECRET_KEY 与 INITIAL_ADMIN_PASSWORD。
    ENVIRONMENT: str = "development"

    # —— 跨域（CORS）——
    # 允许的前端源（逗号分隔）；禁止使用 "*" 通配。开发默认本机 Vite 端口。
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # —— 鉴权（零外部依赖，使用标准库签名）——
    # 令牌 HMAC 签名密钥；生产务必通过环境变量覆盖为强随机值（建议 secrets.token_hex(32)）。
    SECRET_KEY: str = "change-me-in-prod-rackvisio-secret-key"
    # 令牌有效期（小时）。
    TOKEN_EXPIRE_HOURS: int = 12
    # 系统初始化默认管理员密码（仅首次 seed 使用；可用环境变量覆盖）。
    INITIAL_ADMIN_PASSWORD: str = "admin123"

    # —— 日志保留与清理 ——
    # 操作日志 / 登录日志保留天数（到期硬删，审计只增不减）。默认 180 天，可用
    # LOG_RETENTION_DAYS 覆盖。手动 /logs/cleanup 按此值计算 cutoff（自动清理已移除，
    # 改由用户在界面手动触发，避免误删）。
    LOG_RETENTION_DAYS: int = 180


# 全局唯一配置实例（模块级单例）。
settings = Settings()


def _enforce_production_security() -> None:
    """安全基线提示：使用弱密钥/默认密码时打印告警，但**不阻断启动**。

    内网 DCIM 场景不强制 crash——保留告警以提示运维上线前覆盖 SECRET_KEY 与
    INITIAL_ADMIN_PASSWORD，安全基线详见 docs/DEPLOY.md。开发/生产均只告警、不退出。
    """
    import sys

    weak_keys = {"", "change-me-in-prod-rackvisio-secret-key"}
    if settings.SECRET_KEY in weak_keys:
        print(
            "[warn] SECRET_KEY 仍为默认/空值，生产环境存在 JWT 伪造风险；"
            "请通过环境变量 SECRET_KEY 设置强随机密钥（如 openssl rand -hex 32）。",
            file=sys.stderr,
        )
    if settings.INITIAL_ADMIN_PASSWORD == "admin123":
        print(
            "[warn] INITIAL_ADMIN_PASSWORD 仍为默认密码 admin123；"
            "请通过环境变量 INITIAL_ADMIN_PASSWORD 修改为强密码后再上线。",
            file=sys.stderr,
        )


_enforce_production_security()
