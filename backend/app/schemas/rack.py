"""机柜相关 Schema。

面向政企 / IDC 租用场景：机柜以「列编号(column_code) + 机柜编号(code)」定位。
- 列编号：同一机房内唯一。
- 机柜编号：同一列内唯一。
- 机柜分组(rack_group)：所属用户 / 公司 / 部门，选填。
- 机柜状态(status)：业务枚举（可用/已占用/维护中/已下架/空调/电源），选填，默认「可用」。
- used_u 由后端重算，不可由前端写入。
已移除原「行列坐标(row_num/col_num)」与平面图耦合。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import RackBizStatus


class RackCreate(BaseModel):
    """创建机柜请求。room_id 在「机房下创建机柜」时由路径提供，故可选。"""

    room_id: Optional[str] = None
    # 名称选填：留空时由后端按「列编号-机柜编号」自动生成。
    name: Optional[str] = Field(default=None, max_length=255)
    # 机柜编号：同一列内唯一（如 01、02）。
    code: str = Field(..., min_length=1, max_length=64)
    # 列编号：同一机房内唯一（如 A1、B2）。
    column_code: str = Field(..., min_length=1, max_length=32)
    # 机柜 U 数：可用 U 位高度。
    total_u: int = Field(default=42, ge=1, le=60)
    # 机柜分组：所属用户 / 公司 / 部门。
    rack_group: Optional[str] = Field(default=None, max_length=128)
    # 机柜状态：业务枚举，选填。
    status: RackBizStatus = RackBizStatus.AVAILABLE
    # 平面图网格坐标（2D 平面图 + 3D 联动）。缺省时由后端按列编号/编号自动分配。
    grid_row: Optional[int] = None
    grid_col: Optional[int] = None


class RackUpdate(BaseModel):
    """更新机柜请求（全部可选）。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, min_length=1, max_length=64)
    column_code: Optional[str] = Field(default=None, min_length=1, max_length=32)
    total_u: Optional[int] = Field(default=None, ge=1, le=60)
    rack_group: Optional[str] = Field(default=None, max_length=128)
    status: Optional[RackBizStatus] = None
    grid_row: Optional[int] = None
    grid_col: Optional[int] = None


class RackOut(BaseModel):
    """机柜响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    room_id: str
    name: str
    code: str
    column_code: str
    total_u: int
    used_u: int
    rack_group: Optional[str] = None
    status: str
    grid_row: Optional[int] = None
    grid_col: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RackUMapSlot(BaseModel):
    """U 位占用槽位（自底向上，U=1 在最底部）。"""

    u: int
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None


class RackUMap(BaseModel):
    """机柜 U 位占用图数据。"""

    rack_id: str
    total_u: int
    used_u: int
    status: str
    slots: list[RackUMapSlot] = []


class RackCheckURequest(BaseModel):
    """U 位冲突检查请求体（rack_id 来自路径）。"""

    start_u: int
    size_u: int
    exclude_device_id: Optional[str] = None  # 更新设备时排除自身


class RackCheckU(BaseModel):
    """U 位冲突检查结果。"""

    rack_id: str
    start_u: int
    size_u: int
    conflict: bool = False
    conflict_u: list[int] = []
    conflict_device: Optional[str] = None
    error: Optional[str] = None


class RackMountRequest(BaseModel):
    """上架设备请求：将某台设备挂载到指定 U 位。

    上架人由后端根据当前登录用户自动填充（见 racks.py mount_device）。
    """

    device_id: str
    start_u: int = Field(..., ge=1, description="起始 U 位（1 基，自底向上）")


class RackUnmountRequest(BaseModel):
    """下架设备请求：将某台设备从机柜移出。

    下架人由后端根据当前登录用户自动填充（见 racks.py unmount_device）。
    """

    device_id: str


class RackListItem(BaseModel):
    """机柜列表项（含所属机房编号/名称，便于全局机柜管理列表展示）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    room_id: str
    room_code: Optional[str] = None
    room_name: Optional[str] = None
    name: str
    code: str
    column_code: str
    total_u: int
    used_u: int
    rack_group: Optional[str] = None
    status: str
    grid_row: Optional[int] = None
    grid_col: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RackPositionUpdate(BaseModel):
    """单个机柜网格坐标更新。"""

    id: str
    grid_row: int = Field(ge=0)
    grid_col: int = Field(ge=0)


class RackPositionsUpdate(BaseModel):
    """批量更新机柜网格坐标（2D 平面图拖拽持久化）。"""

    positions: list[RackPositionUpdate]
