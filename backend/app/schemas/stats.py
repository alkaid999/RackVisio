"""全局统计概览 Schema（仪表盘总览页数据契约）。"""

from __future__ import annotations

from pydantic import BaseModel


class DeviceStatusCount(BaseModel):
    """单状态设备计数。"""

    status: str
    label: str
    count: int


class RoomRackCapacity(BaseModel):
    """单机房机柜容量汇总。"""

    room_id: str
    room_name: str
    rack_count: int = 0
    total_u: int = 0
    used_u: int = 0
    utilization: float = 0.0


class DeviceTypeCount(BaseModel):
    """单类型设备计数。"""

    type: str
    label: str
    count: int


class StatsOverview(BaseModel):
    """仪表盘总览聚合数据。

    - room_count / rack_count / device_count：基础设施规模。
    - device_status：各状态设备计数（全部状态均有，缺失为 0）。
    - rack_capacity_by_room：各机房机柜使用率（按机房名排序）。
    - 其余字段为补充聚合：整体机柜使用率、链路/账号/耗材规模、设备类型分布。
    """

    room_count: int = 0
    rack_count: int = 0
    device_count: int = 0
    facility_count: int = 0
    device_status: list[DeviceStatusCount] = []
    rack_capacity_by_room: list[RoomRackCapacity] = []
    # 补充聚合（仪表盘补充模块使用）。
    total_u: int = 0
    used_u: int = 0
    overall_utilization: float = 0.0
    link_count: int = 0
    account_count: int = 0
    consumable_type_count: int = 0
    consumable_item_count: int = 0
    consumable_total_quantity: int = 0
    device_type_distribution: list[DeviceTypeCount] = []
