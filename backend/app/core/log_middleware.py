"""请求级操作日志中间件（原生方案）。

对所有落在 ``settings.API_PREFIX`` 下的写请求（POST/PUT/PATCH/DELETE）自动落一条
``operation_logs``：谁 / 何时 / 方法 / 资源类型 / 路径 / 状态码 / 来源 IP / **操作详情**。

设计要点：
- 零业务侵入：端点无需任何审计代码，新增模块天然覆盖。
- 资源类型（resource）：按「资源关键字优先」从路径解析归一化键
  （room/rack/device/interface/link/account/consumable/mount-record），落库后支撑
  按资源类型精确筛选。嵌套路径（如 ``/devices/{id}/interfaces``）也能正确归为
  ``interface``，而非误判 ``device``；``links`` 归为「链路」而非「连接」。
- 操作详情（detail）：结构升级为
  ``{data, old, names, old_names, diff}``：
  - ``data``：请求体（新值），敏感字段（password/password_hash/salt）递归遮蔽为
    ``"******"``，杜绝明文密码泄漏；
  - ``old``：PUT/PATCH/DELETE 在 ``call_next`` **之前**用独立会话快照的旧实体字段
    （创建类 POST 无旧值，为 null）；
  - ``names`` / ``old_names``：新值 / 旧值两侧外键 ID 解析出的可读名称；
  - ``diff``：修改类操作自动算出的「字段级变更」（field/old/new），前端据此渲染
    「原值 → 新值」对比（如修改机房地址：地址：旧值 → 新值），彻底解决「无详情」。
- 认证类端点（/auth/*）不记操作日志——登录 / 注销由 ``login_logs`` 单独记录；
  令牌刷新是登录态派生事件、无业务语义。
- 导入 / 导出（路径含 /import、/export）不记操作日志（业务决策：导入导出不审计，
  且请求体可能极大）；非 JSON 请求体（如文件上传）不抓 detail。
- 日志写入用独立会话（``async_session_factory``），任何异常静默吞掉，
  绝不影响业务响应（见「写操作 500 反模式」教训：commit 后副作用必须降级）。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.consumable import ConsumableCategory, ConsumableItem, ConsumableType
from app.models.device import Device
from app.models.interface import DeviceInterface
from app.models.link import DeviceLink
from app.models.mount_record import MountRecord
from app.models.operation_log import OperationLog
from app.models.rack import Rack
from app.models.room import Room
from app.models.user import User

logger = logging.getLogger("oplog")

# 需要记录的写方法（GET/HEAD/OPTIONS 等读请求不记）。
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# 不记操作日志的路径前缀：认证域由 login_logs 单独负责。
_EXEMPT_PREFIX = f"{settings.API_PREFIX}/auth"
# 导入 / 导出不审计（业务决策），且请求体可能极大，直接跳过整条日志。
# check-u 是只读查询（但用 POST），无业务写语义，不审计。
# cleanup 是日志自清理，由服务器访问日志可追溯，不写入审计表避免递归。
_SKIP_HINTS = ("/import", "/export", "/check-u", "/cleanup")
# 请求体抓取上限（字节），超过不抓 detail（如超大 payload）。
# Q-03：收敛到 Settings.LOG_BODY_SIZE_LIMIT（可 .env 覆盖）。
_BODY_SIZE_LIMIT = settings.LOG_BODY_SIZE_LIMIT

# 敏感字段：请求体里出现即递归遮蔽为 "******"，绝不落库明文。
_SENSITIVE = ("password", "password_hash", "salt")

# ID 字段 → (模型, [候选展示列])：把外键解析成可读名称。
# 优先取第一个非空候选列；机架/机房允许 name 或 code。
_ID_RESOLVERS = {
    "device_id": (Device, ["name"]),
    "source_device_id": (Device, ["name"]),
    "target_device_id": (Device, ["name"]),
    "owner_device_id": (Device, ["name"]),
    "rack_id": (Rack, ["name", "code"]),
    "room_id": (Room, ["name", "code"]),
    "consumable_type_id": (ConsumableType, ["name"]),
    "category_id": (ConsumableCategory, ["name"]),
    "consumable_id": (ConsumableItem, ["name"]),
    "source_interface_id": (DeviceInterface, ["name"]),
    "target_interface_id": (DeviceInterface, ["name"]),
}

# 单实体展示名解析用的列（供 _name_of 复用，与 _ID_RESOLVERS 同源）。
_NAME_COLS = {
    Device: ["name"],
    Rack: ["name", "code"],
    Room: ["name", "code"],
    ConsumableItem: ["name"],
    ConsumableType: ["name"],
    ConsumableCategory: ["name"],
    DeviceInterface: ["name"],
}


def _clip(value: str | None, limit: int) -> str | None:
    """按列长度上限截断字符串，超长尾部用省略号标记。

    必须做：``target`` 列为 ``String(255)``，而链路对象拼接后可达
    ``设备名(255)/接口名(64) → 设备名(255)/接口名(64)`` ≈ 640 字符。
    SQLite 不强制长度（测试环境无感），但 PostgreSQL 会抛
    ``StringDataRightTruncation`` → 整条日志写入失败并被外层 except 静默吞掉，
    表现为「该操作完全没有留痕」。故所有变长列写库前一律裁剪。
    """
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def client_ip(request: Request) -> str | None:
    """解析来源 IP：优先 X-Forwarded-For（反代场景），否则取直连地址。"""
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


async def _capture_body(request: Request) -> dict | None:
    """抓取写请求的 JSON 请求体（转为 dict）；非 JSON / 过大 / 读取失败返回 None。"""
    if request.method == "DELETE":
        # DELETE 一般无 body，改从路径末段取被删资源 id。
        seg = request.url.path.rstrip("/").split("/")[-1]
        return {"id": seg}
    if request.method not in ("POST", "PUT", "PATCH"):
        return None
    if "application/json" not in request.headers.get("content-type", ""):
        return None
    try:
        raw = await request.body()
    except Exception:
        return None
    if not raw or len(raw) > _BODY_SIZE_LIMIT:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, (dict, list)) else None


def _mask_sensitive(obj):
    """递归遮蔽敏感字段（password/password_hash/salt）→ "******"。

    防止账号创建/改密时明文密码落库到 operation_logs.detail。
    """
    if isinstance(obj, dict):
        return {
            k: ("******" if k in _SENSITIVE else _mask_sensitive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_mask_sensitive(x) for x in obj]
    return obj


def _jsonable(v):
    """把 ORM 值转成 JSON 安全原语（datetime → 字符串）。"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, dict | list):
        return v
    return v


def _norm(v):
    """用于变更对比的归一化：None 与空串视为等价，字符串去首尾空白。"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return v


def _fmt(v):
    """diff 展示用：None → 破折号，datetime → 字符串，其余 str()。"""
    if v is None:
        return "—"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, dict | list):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _classify(path: str) -> tuple[str | None, type | None, int]:
    """按「资源关键字优先」解析路径 → (resource 键, 快照模型, 实体 id 末段偏移)。

    优先匹配 interfaces / links 等嵌套关键字（修复 ``/devices/{id}/interfaces``
    误判为 device 的 bug），再 fallback 到首段。快照模型为 PUT/PATCH/DELETE
    时读取旧实体用；POST 创建无需快照（返回模型仍可用于 resource 归类）。
    """
    clean = path.replace(f"{settings.API_PREFIX}/", "").strip("/")
    segs = [s for s in clean.split("/") if s]
    if "interfaces" in segs:
        return "interface", DeviceInterface, 0
    if "links" in segs:
        return "link", DeviceLink, 0
    if "mount" in segs or "unmount" in segs:
        return "mount-record", MountRecord, 0
    if "mount-records" in segs:
        return "mount-record", MountRecord, 0
    if "accounts" in segs:
        return "account", User, 0
    if "consumables" in segs:
        # 耗材子路径细分布局：条目/类型/分类；resource 键统一 consumable。
        if "items" in segs:
            return "consumable", ConsumableItem, 0
        if "types" in segs:
            return "consumable", ConsumableType, 0
        if "categories" in segs:
            return "consumable", ConsumableCategory, 0
        return "consumable", ConsumableItem, 0
    if "racks" in segs:
        return "rack", Rack, 0
    if "devices" in segs:
        return "device", Device, 0
    if "rooms" in segs:
        return "room", Room, 0
    if "meta" in segs:
        return "meta", None, 0
    return None, None, 0


def _extract_id(path: str, id_idx: int = 0) -> str | None:
    """从路径末段按偏移取实体 id（0=末段）。"""
    segs = [s for s in path.split("/") if s]
    if not segs:
        return None
    try:
        return segs[-(id_idx + 1)]
    except IndexError:
        return None


async def _resolve_names(session, body: dict) -> dict:
    """best-effort 把 body 中的外键 ID 解析为可读名称；任一失败静默跳过。"""
    names: dict = {}
    if not isinstance(body, dict):
        return names
    for field, (model, cols) in _ID_RESOLVERS.items():
        val = body.get(field)
        if val is None:
            continue
        try:
            stmt = select(*[getattr(model, c) for c in cols]).where(model.id == val)
            row = (await session.execute(stmt)).first()
            if row:
                display = next((v for v in row if v is not None), None)
                if display is not None:
                    names[field] = str(display)
        except Exception:
            continue
    return names


async def _snapshot_old(entity_id: str, model) -> tuple[dict | None, dict]:
    """在 call_next 之前用独立会话快照旧实体字段（旧值），并解析外键可读名称。

    返回 (old_dict, old_names)；实体不存在返回 (None, {})。任何异常静默降级。
    """
    try:
        async with async_session_factory() as session:
            inst = (
                await session.execute(select(model).where(model.id == entity_id))
            ).scalar_one_or_none()
            if inst is None:
                return None, {}
            old_dict: dict = {}
            for col in model.__table__.columns:
                if col.name in ("id", "created_at", "updated_at"):
                    continue
                old_dict[col.name] = _jsonable(getattr(inst, col.name))
            try:
                old_names = await _resolve_names(session, old_dict)
            except Exception:
                old_names = {}
            return old_dict, old_names
    except Exception:
        return None, {}


def _build_diff(old_dict: dict, new_data: dict, old_names: dict, new_names: dict) -> list:
    """字段级变更：遍历新值，对照旧值，输出 [{field, old, new}]。

    仅记录真正变化的字段（含外键名称）；敏感字段已遮蔽，不在此重复出现。
    """
    diff: list = []
    if not isinstance(new_data, dict):
        return diff
    for key, new_val in new_data.items():
        if key in _SENSITIVE:
            # 敏感字段（密码等）：仅记录「已变更」，不泄漏明文。
            # masked_data 中非空敏感字段已被遮蔽为 "******"，出现即代表用户提交了新值。
            if new_val == "******":
                diff.append({"field": key, "old": "******", "new": "******"})
            continue
        if key not in old_dict:
            # 实体无此列（关系/计算字段）：仅在提供有意义新值时记一笔「设为」。
            if new_val not in (None, "", [], {}):
                diff.append({"field": key, "old": "—", "new": _fmt(new_val)})
            continue
        old_val = old_dict.get(key)
        old_disp = old_names.get(key, _fmt(old_val))
        new_disp = new_names.get(key, _fmt(new_val))
        if _norm(old_val) != _norm(new_val):
            diff.append({"field": key, "old": old_disp, "new": new_disp})
    return diff


# HTTP 方法 → 操作动作归一化键（前端「操作」列据此展示）。
_ACTION_MAP = {"POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}

# 路径段 → 语义动作映射表：POST 请求中若路径包含以下段，
# 用对应的业务动作替代泛化的 "create"。新增操作只需加一行配置。
_PATH_ACTION_OVERRIDES: dict[str, str] = {
    "mount": "mount",        # 设备上架
    "unmount": "unmount",    # 设备下架
    "adjust": "adjust",      # 耗材库存调整
}


def _device_id_from_path(path: str) -> str | None:
    """从嵌套路径取父设备 id：/devices/{id}/interfaces。"""
    segs = [s for s in path.split("/") if s]
    for i, s in enumerate(segs):
        if s == "devices" and i + 1 < len(segs):
            return segs[i + 1]
    return None


def _extract_parent_id(path: str, key: str) -> str | None:
    """从嵌套路径取父级 id：/consumables/types/{id}/categories → 取 types 后那段。"""
    segs = [s for s in path.split("/") if s]
    for i, s in enumerate(segs):
        if s == key and i + 1 < len(segs):
            return segs[i + 1]
    return None


def _fmt_qty(qty) -> str:
    if isinstance(qty, int):
        return f"{qty:+d}"
    if isinstance(qty, float):
        return f"{qty:+g}"
    return str(qty)


async def _name_of(session, model, id_val) -> str | None:
    """解析单个实体展示名（优先 name，机架/机房回退 code）。失败静默返回 None。"""
    if id_val is None:
        return None
    cols = _NAME_COLS.get(model)
    if not cols:
        return None
    try:
        row = (
            await session.execute(
                select(*[getattr(model, c) for c in cols]).where(model.id == id_val)
            )
        ).first()
        if row:
            return next((str(v) for v in row if v is not None), None)
    except Exception:
        return None
    return None


async def _link_endpoints(session, src_if, dst_if) -> tuple[str | None, str | None]:
    """把链路两端的接口 id 解析成『设备名/接口名』，用于操作对象展示。"""
    async def _ep(iface_id):
        if not iface_id:
            return None
        try:
            row = (
                await session.execute(
                    select(DeviceInterface.name, Device.name)
                    .join(Device, DeviceInterface.device_id == Device.id)
                    .where(DeviceInterface.id == iface_id)
                )
            ).first()
            if row:
                iface_name, dev_name = row
                return f"{dev_name}/{iface_name}" if iface_name else dev_name
        except Exception:
            return None
        return None
    return await _ep(src_if), await _ep(dst_if)


async def _resolve_target(
    resource_key: str | None,
    body: object,
    old_dict: dict | None,
    names: dict,
    old_names: dict,
    session,
    path: str,
) -> str | None:
    """解析「操作对象」可读名称，落到 operation_logs.target 列。

    - link：源接口 → 目标接口，解析成「设备名/接口名」两端，确认具体设备。
    - interface：设备名 / 接口名（父设备取自 body.device_id 或路径 /devices/{id}/interfaces）。
    - consumable：明细调整（/adjust）id 在路径，解析耗材条目名并附操作类型+数量；
      类型/分类创建用 body.name；分类创建可带父类型「类型 / 分类」。
    - mount-record：设备 @ 机柜。
    - 通用资源：请求体 name → 旧快照 name/code → 首个外键可读名。
    """
    def s(v):
        return str(v) if v is not None else None

    all_names: dict = dict(old_names or {})
    all_names.update(names or {})
    body_d = body if isinstance(body, dict) else {}
    old_d = old_dict if isinstance(old_dict, dict) else {}

    if resource_key == "link":
        src_if = body_d.get("source_interface_id") or old_d.get("source_interface_id")
        dst_if = body_d.get("target_interface_id") or old_d.get("target_interface_id")
        if src_if or dst_if:
            src_ep, dst_ep = await _link_endpoints(session, src_if, dst_if)
            if src_ep or dst_ep:
                return f"{src_ep or '?'} → {dst_ep or '?'}"

    if resource_key == "interface":
        iface_name = body_d.get("name") or old_d.get("name")
        dev_id = body_d.get("device_id") or _device_id_from_path(path)
        dev_name = all_names.get("device_id")
        if not dev_name and dev_id:
            dev_name = await _name_of(session, Device, dev_id)
        if iface_name and dev_name:
            return f"{dev_name} / {iface_name}"
        return s(iface_name) or s(dev_name)

    if resource_key == "consumable":
        item_id = body_d.get("consumable_id")
        if not item_id and "/items/" in path and path.rstrip("/").endswith("/adjust"):
            item_id = _extract_id(path, 1)
        if item_id:
            name = await _name_of(session, ConsumableItem, item_id)
            if name:
                op = body_d.get("operation_type")
                qty = body_d.get("quantity")
                suffix = ""
                if op:
                    suffix += f" {op}"
                if qty is not None:
                    suffix += f" {_fmt_qty(qty)}"
                return name + suffix
        nm = body_d.get("name") or old_d.get("name")
        if nm:
            return s(nm)
        parent_type_id = _extract_parent_id(path, "types")
        if parent_type_id:
            pname = await _name_of(session, ConsumableType, parent_type_id)
            if pname and nm:
                return f"{pname} / {nm}"
        for v in all_names.values():
            if v is not None:
                return s(v)
        return None

    if resource_key == "mount-record":
        dev = all_names.get("device_id")
        rack = all_names.get("rack_id")
        # 上架/下架路径 /racks/{rack_id}/mount|unmount：body 不含 rack_id，从路径提取。
        if not rack:
            path_segs = [seg for seg in path.split("/") if seg]
            for i, seg in enumerate(path_segs):
                if seg == "racks" and i + 1 < len(path_segs):
                    rack = await _name_of(session, Rack, path_segs[i + 1])
                    break
        if dev or rack:
            # 补充 U 位信息，让操作对象更完整（如「服务器A @ 机柜B U5-U6」）。
            u_info = ""
            start_u = body_d.get("start_u") or old_d.get("start_u")
            occ_u = body_d.get("occupied_u") or old_d.get("occupied_u")
            if start_u is not None:
                u_info = f" U{start_u}"
                if occ_u and int(occ_u) > 1:
                    u_info = f" U{start_u}-U{int(start_u) + int(occ_u) - 1}"
            return f"{dev or '?'} @ {rack or '?'}{u_info}"

    if resource_key == "account":
        # User 模型无 name 字段，用 display_name 或 username 作为操作对象。
        uname = body_d.get("display_name") or body_d.get("username")
        if not uname:
            uname = old_d.get("display_name") or old_d.get("username")
        if uname:
            return s(uname)

    if resource_key == "rack" and "/positions" in path:
        # 机柜平面图坐标更新：按位置数组里的机柜 id 解析可读机柜名（含编号），
        # 多个机柜时折叠展示「A 等 N 个机柜」。无 id（新增场景）无法解析，回退通用逻辑。
        positions = body_d.get("positions")
        if isinstance(positions, list):
            rack_names = []
            for p in positions:
                pid = p.get("id") if isinstance(p, dict) else None
                if pid:
                    nm = await _name_of(session, Rack, pid)
                    if nm:
                        rack_names.append(nm)
            if rack_names:
                if len(rack_names) == 1:
                    return s(rack_names[0])
                return f"{rack_names[0]} 等 {len(rack_names)} 个机柜"

    if body_d.get("name"):
        return s(body_d["name"])
    if old_d.get("name"):
        return s(old_d["name"])
    if old_d.get("code"):
        return s(old_d["code"])
    for v in all_names.values():
        if v is not None:
            return s(v)
    return None


class OperationLogMiddleware(BaseHTTPMiddleware):
    """写请求自动留痕。注册须位于 AuthMiddleware 之内层，以拿到 ``request.state.user``。"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        is_write = (
            request.method in _WRITE_METHODS
            and path.startswith(settings.API_PREFIX)
            and not path.startswith(_EXEMPT_PREFIX)
            and not any(hint in path for hint in _SKIP_HINTS)
        )
        # 必须在 call_next 之前抓取请求体。BaseHTTPMiddleware 的内层应用（路由端点）
        # 会消费掉请求体流，若等 call_next 返回后再 await request.body() 在部分
        # Starlette 版本里拿不到任何字节，导致 detail.data 恒为 None（之前所有编辑
        # 的「详情」都是空的，根因在此）。提前读取会把 body 缓存进 request._body，
        # 内层应用与日志中间件读的是同一份缓存，互不干扰。
        data = None
        # 资源类型 + 旧实体快照：写请求统一解析；PUT/PATCH/DELETE 需快照旧值以算 diff。
        resource_key: str | None = None
        old_snapshot: tuple[dict | None, dict] | None = None
        if is_write:
            try:
                data = await _capture_body(request)
            except Exception:
                data = None
            try:
                resource_key, snapshot_model, id_idx = _classify(path)
                if snapshot_model is not None and request.method in ("PUT", "PATCH", "DELETE"):
                    entity_id = _extract_id(path, id_idx)
                    if entity_id:
                        old_snapshot = await _snapshot_old(entity_id, snapshot_model)
            except Exception:
                old_snapshot = None

        response = await call_next(request)
        try:
            if is_write:
                user = getattr(request.state, "user", None) or {}
                masked_data = _mask_sensitive(data)
                old_dict, old_names = old_snapshot or (None, {})
                # 旧值快照中的敏感字段（password_hash/salt）同样遮蔽，不落库明文哈希。
                if old_dict:
                    old_dict = _mask_sensitive(old_dict)
                detail = {
                    "data": masked_data,
                    "old": old_dict,
                    "names": {},
                    "old_names": old_names,
                    "diff": [],
                }
                async with async_session_factory() as session:
                    if isinstance(masked_data, dict):
                        try:
                            detail["names"] = await _resolve_names(session, masked_data)
                        except Exception:
                            detail["names"] = {}
                    # 修改类操作：对照旧实体算 diff（外键用解析后的可读名称）。
                    # 仅 PUT/PATCH 计算 diff；DELETE 只展示操作前快照（detail.data 仅含 id）。
                    if (
                        old_dict is not None
                        and isinstance(masked_data, dict)
                        and request.method in ("PUT", "PATCH")
                    ):
                        detail["diff"] = _build_diff(
                            old_dict, masked_data, old_names, detail["names"]
                        )
                    # 操作动作：先按 HTTP 方法取默认值，再用路径语义映射表覆盖。
                    action = _ACTION_MAP.get(request.method)
                    clean_segs = [seg for seg in path.split("/") if seg]
                    for seg, override_action in _PATH_ACTION_OVERRIDES.items():
                        if seg in clean_segs:
                            action = override_action
                            break
                    # 机柜平面图坐标批量更新（POST /racks/positions）：请求体带 id 走更新、
                    # 不带 id 走新增。此前机械按 HTTP 方法把 POST 记为 create，导致平面移动
                    # 被误记为「新增」，此处按请求体是否含 id 纠正动作，与后端 update_positions
                    # 的实际行为（按 id 更新、无 id 新增）保持一致。
                    if path.rstrip("/").endswith("/racks/positions") and isinstance(masked_data, dict):
                        positions = masked_data.get("positions")
                        if isinstance(positions, list) and positions:
                            action = (
                                "update"
                                if any(isinstance(p, dict) and p.get("id") for p in positions)
                                else "create"
                            )
                    # DELETE 操作：把旧实体快照的可读摘要写入 detail，
                    # 让前端能展示「删除了什么」而非只有一个 UUID。
                    if request.method == "DELETE" and old_dict:
                        detail["old_names"] = old_names
                    target = await _resolve_target(
                        resource_key, masked_data, old_dict, detail["names"], old_names, session, path
                    )
                    session.add(
                        OperationLog(
                            operator_id=_clip(user.get("sub"), 36),
                            operator_name=_clip(user.get("user_name"), 64),
                            method=request.method,
                            path=_clip(path, 255),
                            resource=_clip(resource_key, 32),
                            action=_clip(action, 16),
                            # 必须裁剪：链路两端拼接后可远超 255（见 _clip 文档）。
                            target=_clip(target, 255),
                            status_code=response.status_code,
                            ip=_clip(client_ip(request), 64),
                            detail=json.dumps(detail, ensure_ascii=False, default=str),
                        )
                    )
                    await session.commit()
        except Exception:
            # 日志失败绝不影响业务响应；但审计完整性受损必须显式告警（S-08：
            # 静默吞掉会掩盖「关键操作无留痕」——如 PostgreSQL 列宽截断等生产事故）。
            logger.error("操作日志写入失败（审计完整性受影响）", exc_info=True)
        return response
