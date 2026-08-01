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
    # 安全兜底（S-02 决策）：初始管理员首次登录**强制改密**（must_change_password），
    # 故默认 admin123 可直接使用、无需在 .env 预置强密码——首次登录后立即被替换，
    # 默认值不会长期生效。运维如需自定义初始密码仍可覆盖。
    INITIAL_ADMIN_PASSWORD: str = "admin123"

    # —— 日志保留与清理 ——
    # 操作日志 / 登录日志保留天数（到期硬删，审计只增不减）。默认 180 天，可用
    # LOG_RETENTION_DAYS 覆盖。手动 /logs/cleanup 按此值计算 cutoff（自动清理已移除，
    # 改由用户在界面手动触发，避免误删）。
    LOG_RETENTION_DAYS: int = 180

    # —— 安全与限流阈值（Q-03：原为各模块硬编码魔法数字，统一收口可 .env 覆盖）——
    # 登录滑动窗口限流：同一「IP+用户名」在窗口内失败次数超阈值即临时锁定。
    LOGIN_RATE_WINDOW: int = 300  # 统计窗口（秒）
    LOGIN_MAX_FAILS: int = 5  # 窗口内最大失败次数
    # 禁用账号态缓存 TTL（秒）：仅缓存「已禁用」结果，启用态实时查库。
    USER_DISABLED_CACHE_TTL: int = 60
    # 慢请求告警阈值（毫秒）：超过则请求日志降为 WARNING。
    SLOW_REQUEST_MS: int = 1000
    # 全站通用限流（按 IP 固定窗口）：每分钟上限与窗口秒数。
    RATE_LIMIT_PER_MIN: int = 600
    RATE_LIMIT_WINDOW: int = 60
    # 操作日志请求体抓取上限（字节）：超过不抓 detail（避免超大 payload）。
    LOG_BODY_SIZE_LIMIT: int = 4096


# 全局唯一配置实例（模块级单例）。
settings = Settings()


def _enforce_production_security() -> None:
    """安全基线校验（S-01）：production 环境强制 fail-closed，弱签名密钥**拒绝启动**。

    - production：检测到默认/空 SECRET_KEY → 抛 ``RuntimeError`` 阻断启动，
      逼运维在 .env 显式覆盖后才允许上线（JWT 伪造风险无其他兜底）。
    - development / test：仅打印告警不阻断（本地开发体验不受阻，默认值可直接跑通）。

    ``INITIAL_ADMIN_PASSWORD`` 默认值不在此拦截（S-02 决策）：初始管理员首次登录
    强制改密（must_change_password）已兜底，默认密码不会长期生效，无需在 env 预置强密码；
    运维自定义初始密码仍可通过环境变量覆盖。
    """
    import sys

    weak_keys = {"", "change-me-in-prod-rackvisio-secret-key"}
    problems: list[str] = []
    if settings.SECRET_KEY in weak_keys:
        problems.append(
            "SECRET_KEY 仍为默认/空值，存在 JWT 伪造风险；"
            "请通过环境变量 SECRET_KEY 设置强随机密钥（如 openssl rand -hex 32）"
        )
    if settings.ENVIRONMENT == "production" and problems:
        raise RuntimeError(
            "生产环境安全校验失败，拒绝启动（fail-closed）：\n  - " + "\n  - ".join(problems)
        )
    for p in problems:
        print(f"[warn] {p}", file=sys.stderr)


_enforce_production_security()
