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

    # 是否启用 Redis 缓存；默认 false 使用进程内字典缓存。
    REDIS_ENABLED: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"

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


# 全局唯一配置实例（模块级单例）。
settings = Settings()


def _enforce_production_security() -> None:
    """生产环境安全基线校验：在导入期即失败，避免带弱密钥上线。

    开发/测试环境仅对默认弱密钥打印告警，不阻断启动。
    """
    if settings.ENVIRONMENT.lower() != "production":
        if settings.SECRET_KEY == "change-me-in-prod-rackvisio-secret-key":
            import sys

            print(
                "[warn] 使用默认弱 SECRET_KEY，仅限开发环境；"
                "生产请通过环境变量 SECRET_KEY 设置强随机密钥。",
                file=sys.stderr,
            )
        return
    weak_keys = {"", "change-me-in-prod-rackvisio-secret-key"}
    if settings.SECRET_KEY in weak_keys:
        raise RuntimeError(
            "生产环境必须通过环境变量 SECRET_KEY 设置强随机密钥，禁止使用默认/空值。"
        )
    if settings.INITIAL_ADMIN_PASSWORD == "admin123":
        raise RuntimeError(
            "生产环境必须修改 INITIAL_ADMIN_PASSWORD，禁止使用默认密码 admin123。"
        )


_enforce_production_security()
