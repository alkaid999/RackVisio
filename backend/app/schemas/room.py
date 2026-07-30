"""机房相关 Schema。

面向政企 / IDC 租用场景：机房以「编号」全局唯一标识，记录别名、区域、楼宇、楼层、地址等。
已移除机房等级(category) 与网格(rows/cols) / 平面图(floor-plan) 相关结构。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# 机房编号：仅允许数字 + 英文字母 + 连字符 / 下划线（如 DC-01）。
ROOM_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class RoomCreate(BaseModel):
    """创建机房请求。"""

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=64, pattern=ROOM_CODE_PATTERN)
    alias: Optional[str] = Field(default=None, max_length=255)
    area: Optional[str] = Field(default=None, max_length=64)
    building: Optional[str] = Field(default=None, max_length=64)
    floor: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = Field(default=None, max_length=255)


class RoomUpdate(BaseModel):
    """更新机房请求（全部可选）。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, min_length=1, max_length=64, pattern=ROOM_CODE_PATTERN)
    alias: Optional[str] = Field(default=None, max_length=255)
    area: Optional[str] = Field(default=None, max_length=64)
    building: Optional[str] = Field(default=None, max_length=64)
    floor: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(
        default=None,
        description="机房状态：active=启用 / disabled=停用。删除机房本质即软删（置 disabled）。",
    )


class RoomOut(BaseModel):
    """机房响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    alias: Optional[str] = None
    area: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    address: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RoomStats(BaseModel):
    """机房容量统计。"""

    rack_count: int = 0
    total_u: int = 0
    used_u: int = 0
    utilization: float = 0.0


class RackStatusDistribution(BaseModel):
    """机柜容量状态分布（按 used_u/total_u 计算，仅用于大屏利用率概览）。"""

    empty: int = 0
    partial: int = 0
    full: int = 0


class DeviceStatusDistribution(BaseModel):
    """设备状态分布（按真实 DeviceStatus 枚举统计）。

    枚举取值见 ``app.core.enums.DeviceStatus``：在库 / 已上架 / 已下架 / 待报废 / 借出。
    旧 schema 的 running/offline/fault/maintenance 为历史遗留、与真实枚举无对应，已移除。
    """

    in_stock: int = 0    # 在库
    mounted: int = 0     # 已上架
    unmounted: int = 0   # 已下架（历史遗留，仅用于兼容统计分类）
    scrapped: int = 0    # 待报废
    lent: int = 0        # 借出


class DashboardKPI(BaseModel):
    """大屏核心 KPI。"""

    rack_count: int = 0
    device_count: int = 0
    utilization: float = 0.0


class RoomDashboard(BaseModel):
    """机房大屏聚合数据。"""

    room_id: str
    room_name: str
    kpi: DashboardKPI
    rack_status_distribution: RackStatusDistribution
    device_status_distribution: DeviceStatusDistribution
    utilization: float = 0.0


class RoomImportItem(BaseModel):
    """机房导入单条（字段与 RoomCreate 对齐，全部可选以容忍空单元格；

    必填校验（名称 / 编号）与格式校验在服务层完成，失败时返回逐行中文错误。
    ``status`` 接受 active / disabled（或 启用 / 停用），缺省视为 active。
    """

    name: Optional[str] = Field(default=None, max_length=255)
    code: Optional[str] = Field(default=None, max_length=64)
    alias: Optional[str] = Field(default=None, max_length=255)
    area: Optional[str] = Field(default=None, max_length=64)
    building: Optional[str] = Field(default=None, max_length=64)
    floor: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default=None, max_length=32)


class RoomImportRowsRequest(BaseModel):
    """机房批量导入请求体：前端解析文件为行后，以 JSON 数组提交。

    注：items 声明为 list[dict]，将逐行校验下沉到 room_service.import_rooms，
    单行非法仅计入 failures，不触发整批 422。
    """

    items: list[dict] = Field(
        ..., min_length=1, max_length=500, description="机房数据行，单次最多 500 条"
    )
