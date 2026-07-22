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
import os
import secrets
import time
from typing import Any

from app.core.config import settings

# 令牌结构版本（保留扩展空间）。
_TOKEN_VERSION = "1"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


# ——— 密码哈希 ———
def hash_password(password: str) -> tuple[str, str]:
    """返回 (password_hash, salt)，均为 hex 字符串。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """恒定时间比对，防时序攻击。"""
    try:
        salt_bytes = bytes.fromhex(salt)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 100_000)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), password_hash)


# ——— 令牌签发 / 校验 ———
def _sign(header_b64: str, payload_b64: str) -> str:
    msg = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).digest()
    return _b64url_encode(sig)


def create_token(*, sub: str, username: str, role: str) -> str:
    """签发无状态令牌。payload 含 sub/user_name/role/exp。"""
    header = {"alg": "HS256", "typ": "JWT", "v": _TOKEN_VERSION}
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "user_name": username,
        "role": role,
        "iat": now,
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
