"""审计「字段级变更」摘要生成。

把更新操作的「修改前 / 后」做字段级 diff，生成人类可读的中文摘要，
写入 ``AuditLog.detail``，便于在审计列表里直接看到改了哪些字段。

用法（端点层）：

    before = await svc.get_device(id)          # DeviceOut（修改前）
    after  = await svc.update_device(id, data) # DeviceOut（修改后）
    detail = build_update_detail(before, after, DEVICE_FIELD_LABELS)

也可在「创建」场景用于罗列初始关键属性（fields 指定要列出的字段即可）。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping


def _fmt(value: Any) -> str:
    """把字段值格式化为可读字符串。"""
    if value is None:
        return "（空）"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (datetime, date)):
        return value.isoformat()[:10]
    # pydantic 通常已把枚举序列化为 value；此处兜底处理仍是枚举对象的情况。
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


# 哨兵：空值（None 或纯空白字符串）统一归并，使「None → ""」不误判为变更。
_EMPTY = object()


def _norm(value: Any) -> Any:
    """把「无值」归一：None 与纯空白字符串都视为同一空哨兵。

    解决前端提交表单时把未填字段发成空字符串 ``""``（DB 中为 ``None``），
    导致 ``None != ""`` 被 ``build_update_detail`` 误判为「字段变更」而出现
    ``型号：（空） → `` 这类噪音。
    """
    if value is None:
        return _EMPTY
    if isinstance(value, str) and not value.strip():
        return _EMPTY
    return value


def build_update_detail(
    old: Any,
    new: Any,
    labels: Mapping[str, str],
    fields: Iterable[str] | None = None,
    *,
    max_len: int = 500,
) -> str:
    """对比 ``old`` / ``new`` 的指定字段，返回形如 ``名称：a → b；IP地址：（空） → 10.0.0.5/24`` 的摘要。

    - ``labels``: 字段名 -> 中文标签。
    - ``fields``: 仅比较这些字段（默认比较 ``labels`` 的全部键）；以旧/新值不一致判定「发生变更」。
    - 空值归一（``None`` / ``""`` 视为同一值），未真正变化的字段不进入摘要。
    - 无字段变化时返回 ``"无字段变更"``。
    - 超过 ``max_len`` 时截断并追加 ``…``，避免超出 ``AuditLog.detail``(String(512))。
    """
    check = list(fields) if fields is not None else list(labels.keys())
    changes: list[str] = []
    for f in check:
        old_val = getattr(old, f, None)
        new_val = getattr(new, f, None)
        if _norm(old_val) != _norm(new_val):
            changes.append(f"{labels.get(f, f)}：{_fmt(old_val)} → {_fmt(new_val)}")
    if not changes:
        return "无字段变更"
    text = "；".join(changes)
    if len(text) > max_len:
        text = text[:max_len].rstrip("；") + "…"
    return text


def build_create_detail(
    obj: Any,
    labels: Mapping[str, str],
    fields: Iterable[str] | None = None,
    *,
    max_len: int = 500,
) -> str:
    """罗列「创建」对象的初始关键属性，生成 ``编号：X；类型：Y`` 形式的中文摘要。

    与 ``build_update_detail`` 不同，这里只列「有值」的字段（空值自动跳过），
    避免 ``（空）`` 噪音；适用于在审计列表的「创建」卡片里直接展示初始属性。

    - ``labels``: 字段名 -> 中文标签。
    - ``fields``: 仅列出这些字段（默认列 ``labels`` 的全部键）。
    - 全部字段皆空时返回 ``"（无附加信息）"``，保证卡片有兜底文案。
    """
    check = list(fields) if fields is not None else list(labels.keys())
    parts: list[str] = []
    for f in check:
        val = getattr(obj, f, None)
        if _norm(val) is _EMPTY:
            continue
        parts.append(f"{labels.get(f, f)}：{_fmt(val)}")
    if not parts:
        return "（无附加信息）"
    text = "；".join(parts)
    if len(text) > max_len:
        text = text[:max_len].rstrip("；") + "…"
    return text
