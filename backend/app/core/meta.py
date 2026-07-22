"""界面展示元数据单一数据源（标签 / 颜色 / 阈值）。

历史问题：设备状态、设备类型、机柜状态的中文标签与颜色在前后端各维护一份
（后端 ``stats_service.py`` + 前端 ``utils/constants.js``），新增 / 调整易双端不一致。
本模块作为后端唯一权威源；前端通过 ``GET /api/v1/meta`` 拉取后渲染，
``constants.js`` 仅作离线兜底。

机柜使用率阈值（warn/crit）同样在此定义，经 ``/meta`` 下发，消除前端
Dashboard / RackList / StatsPanel 中硬编码的 30 / 80 魔法数字（审查报告 #347）。
"""

from __future__ import annotations

# 设备资产生命周期状态（在库 / 已上架 / 已下架 / 待报废 / 借出）。
# 颜色与前端 utils/constants.js 的 DEVICE_STATUS_COLORS 保持一致。
DEVICE_STATUS_META: dict[str, dict] = {
    "在库": {"label": "在库", "color": "#909399"},
    "已上架": {"label": "已上架", "color": "#67C23A"},
    "已下架": {"label": "已下架", "color": "#E6A23C"},
    "待报废": {"label": "待报废", "color": "#F56C6C"},
    "借出": {"label": "借出", "color": "#8b5cf6"},
}

# 设备类型（8 类，取值与后端 DeviceType 枚举一致）。
# 颜色与前端 utils/constants.js 的 DEVICE_TYPE_COLORS 保持一致。
DEVICE_TYPE_META: dict[str, dict] = {
    "server": {"label": "服务器", "color": "#409EFF"},
    "switch": {"label": "交换机", "color": "#67C23A"},
    "firewall": {"label": "防火墙", "color": "#F97316"},
    "router": {"label": "路由器", "color": "#13C2C2"},
    "waf": {"label": "WAF", "color": "#EB4895"},
    "security": {"label": "安全设备", "color": "#E6A23C"},
    "other": {"label": "其他", "color": "#909399"},
}

# 机柜业务状态（用户维护枚举，支持后续扩展）。
# 颜色与前端 utils/constants.js 的 RACK_STATUS_COLORS 保持一致。
RACK_STATUS_META: dict[str, dict] = {
    "可用": {"label": "可用", "color": "#22c55e"},
    "空闲": {"label": "空闲", "color": "#67c23a"},
    "维护中": {"label": "维护中", "color": "#e6a23c"},
    "空调柜": {"label": "空调柜", "color": "#38bdf8"},
    "电柜": {"label": "电柜", "color": "#f59e0b"},
}

# 机柜使用率阈值（%）：低于 warn 绿、warn~crit 黄、高于 crit 红。
# 同时消除前端 Dashboard / RackList / StatsPanel 中硬编码的 30 / 80 魔法数字。
USAGE_WARN = 30
USAGE_CRIT = 80

# 机柜使用率配色三档（与阈值配套，消除前端内联 `>0.8?'#F56C6C':...` 魔法色，审查报告#347/#352）。
# ok=绿（低于 warn）、warn=黄（warn~crit）、crit=红（高于 crit）。
USAGE_COLORS = {"ok": "#67C23A", "warn": "#E6A23C", "crit": "#F56C6C"}
