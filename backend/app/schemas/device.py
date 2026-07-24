"""设备相关 Schema。

设备表仅含固有属性，不含位置字段；当前位置（机房/机柜/起始 U 位）由
``mount_records`` 中状态为「有效」的最新记录推导，作为只读派生字段随响应返回。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import DevicePowerStatus, DeviceStatus, DeviceType


class DeviceCreate(BaseModel):
    """创建设备请求。

    仅登记设备固有属性；位置（上架）在独立的 mount 流程中完成。
    ``device_code`` 选填，留空由服务层生成全局唯一编号。
    ``u_height`` 必有且 ≥ 1（设备物理高度，决定上架占用 U 位）。
    """

    device_code: Optional[str] = Field(default=None, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    device_type: DeviceType = DeviceType.SERVER
    u_height: int = Field(default=1, ge=1, le=60, description="设备 U 数（物理高度，≥1）")
    model: Optional[str] = Field(default=None, max_length=128)
    sn: Optional[str] = Field(default=None, max_length=128)
    ip_address: Optional[str] = Field(default=None, max_length=64)
    warranty_expire: Optional[date] = None
    remark: Optional[str] = Field(default=None, max_length=512)
    # 创建时状态默认「在库」；仅允许在库 / 待报废 / 借出（已上架/已下架由 mount 流程驱动）。
    status: DeviceStatus = DeviceStatus.IN_STOCK
    # 开关机状态：仅对「在架」设备有意义，默认「开机」。
    power_status: DevicePowerStatus = DevicePowerStatus.ON
    # 是否计入资产；设施（patch/odf/other_facility）由服务层强制为 False，默认 True（资产）。
    is_asset: bool = True


class DeviceUpdate(BaseModel):
    """更新设备请求（全部可选，仅固有属性）。

    位置（机房/机柜/U 位）不在此修改，须走 mount/unmount 流程。
    """

    device_code: Optional[str] = Field(default=None, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    device_type: Optional[DeviceType] = None
    u_height: Optional[int] = Field(default=None, ge=1, le=60)
    model: Optional[str] = Field(default=None, max_length=128)
    sn: Optional[str] = Field(default=None, max_length=128)
    ip_address: Optional[str] = Field(default=None, max_length=64)
    warranty_expire: Optional[date] = None
    remark: Optional[str] = Field(default=None, max_length=512)
    status: Optional[DeviceStatus] = None
    power_status: Optional[DevicePowerStatus] = None
    # 是否计入资产（可选更新）；设施类型更新时由服务层强制为 False。
    is_asset: Optional[bool] = None


class DeviceOut(BaseModel):
    """设备响应（含派生当前位置）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    device_code: Optional[str] = None
    name: str
    device_type: str
    u_height: int
    model: Optional[str] = None
    sn: Optional[str] = None
    ip_address: Optional[str] = None
    warranty_expire: Optional[date] = None
    remark: Optional[str] = None
    status: str
    power_status: str = "开机"
    # 是否计入资产（默认 True）。设施恒为 False。
    is_asset: bool = True
    # —— 派生：当前有效上架记录的位置（无有效记录时为 None）——
    current_room_id: Optional[str] = None
    current_room_name: Optional[str] = None
    current_rack_id: Optional[str] = None
    current_rack_name: Optional[str] = None
    current_start_u: Optional[int] = None
    # —— 派生：接口总数（链路资格判定：已上架且含接口方可建链）——
    interface_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
