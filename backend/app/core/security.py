"""安全工具：密码哈希与无状态令牌（零外部依赖，全部使用标准库）。

设计取舍：
- 本环境会周期性删除文件并重装依赖，引入 PyJWT / bcrypt 会增加运维脆弱性；
  因此密码哈希用 ``hashlib.pbkdf2_hmac``、令牌用 ``hmac`` 自签名，均无需安装任何包。
- 令牌为三段式 ``header.payload.signature``（base64url 编码），``signature`` 由服务端
  密钥 HMAC-SHA256 签署，校验时重算比对，防篡改。无状态，后端无需存储会话。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any

from app.core.cache import cache
from app.core.config import settings

logger = logging.getLogger(__name__)

# 令牌结构版本（保留扩展空间）。
_TOKEN_VERSION = "1"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


# ——— 密码哈希 ———
# OWASP 2023 建议 PBKDF2-HMAC-SHA256 至少 600,000 次迭代（旧默认值 100,000 偏弱）。
# 已存在的账户可能仍用 100,000 次哈希，verify_password 兼容新旧两种，迁移期无需改库。
PBKDF2_ITERATIONS = 600_000
_LEGACY_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> tuple[str, str]:
    """返回 (password_hash, salt)，均为 hex 字符串（使用当前推荐迭代次数）。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return dk.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """恒定时间比对，防时序攻击；兼容新旧迭代次数（迁移期透明验证）。"""
    try:
        salt_bytes = bytes.fromhex(salt)
    except (ValueError, TypeError):
        return False
    # 先按当前推荐次数校验；不匹配再尝试旧次数（历史账户），任一通过即视为有效。
    for iterations in (PBKDF2_ITERATIONS, _LEGACY_PBKDF2_ITERATIONS):
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
        if hmac.compare_digest(dk.hex(), password_hash):
            return True
    return False


# ——— 令牌签发 / 校验 ———
def _sign(header_b64: str, payload_b64: str) -> str:
    msg = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_token(*, sub: str, username: str, role: str) -> str:
    """签发无状态令牌。payload 含 sub/user_name/role/exp/iat/jti。

    ``jti`` 为每次签发随机生成的令牌唯一标识，供「注销吊销（黑名单）」与
    「刷新轮换」识别具体令牌。
    """
    header = {"alg": "HS256", "typ": "JWT", "v": _TOKEN_VERSION}
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "user_name": username,
        "role": role,
        "iat": now,
        "jti": secrets.token_hex(16),
        "exp": now + settings.TOKEN_EXPIRE_HOURS * 3600,
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _sign(header_b64, payload_b64)
    return f"{header_b64}.{payload_b64}.{sig}"


class TokenError(Exception):
    """令牌无效（格式/签名/过期）。"""


def verify_token(token: str) -> dict[str, Any]:
    """校验令牌并返回 payload；失败抛 ``TokenError``。"""
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("令牌格式错误")
    header_b64, payload_b64, sig = parts
    expected = _sign(header_b64, payload_b64)
    # 恒定时间比对签名。
    if not hmac.compare_digest(sig, expected):
        raise TokenError("令牌签名无效")
    try:
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, TypeError):
        raise TokenError("令牌载荷解析失败")
    exp = payload.get("exp")
    if exp is None or int(time.time()) > int(exp):
        raise TokenError("令牌已过期")
    if not payload.get("sub"):
        raise TokenError("令牌缺少主体")
    return payload


def gen_secret_key() -> str:
    """生成随机密钥（用于初始化 .env 时的占位，非运行时调用）。"""
    return secrets.token_hex(32)


def token_remaining_ttl(payload: dict[str, Any]) -> int:
    """返回令牌剩余有效秒数（<=0 表示已过期）。"""
    exp = payload.get("exp")
    if not exp:
        return 0
    return int(exp) - int(time.time())


async def is_token_revoked(payload: dict[str, Any]) -> bool:
    """判断令牌是否已被注销（黑名单）。

    通过缓存门面（Redis / 内存）查询；查询异常时 fail-open（视为未吊销），
    避免 Redis 抖动导致全站 401。仅当 payload 含 jti 时参与吊销判定。
    """
    jti = payload.get("jti")
    if not jti:
        return False
    try:
        return bool(await cache.get(f"token:blacklist:{jti}"))
    except Exception:
        logger.warning("令牌黑名单查询失败（视为未吊销）", exc_info=True)
        return False


async def revoke_token(payload: dict[str, Any]) -> None:
    """将令牌加入黑名单（注销），TTL 至其原过期时刻。幂等、非关键操作。"""
    jti = payload.get("jti")
    if not jti:
        return
    ttl = token_remaining_ttl(payload)
    if ttl <= 0:
        return
    try:
        await cache.set(f"token:blacklist:{jti}", "1", ttl=ttl)
    except Exception:
        logger.warning("令牌注销失败（已忽略）", exc_info=True)
