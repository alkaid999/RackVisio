"""接口相关 Schema（端口 → 接口 统一命名）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.core.enums import InterfaceRole, InterfaceSpeed, InterfaceType


class InterfaceCreate(BaseModel):
    """创建设备接口请求（device_id 来自路径）。

    状态（status）由链路事务维护，**此处不接受**；新增接口恒为 ``down``（未接线）。
    ``interface_no`` 为前面板序号（1 基），用于排序与面板定位；不传或传 0 表示自动追加。
    """

    name: str
    interface_type: InterfaceType = InterfaceType.RJ45
    speed: InterfaceSpeed = InterfaceSpeed.G1
    role: InterfaceRole = InterfaceRole.DATA
    interface_no: int = 0
    # 端口级 IP 地址（可空）。区别于设备级 ip_address，此处为接口自身属性。
    ip_address: Optional[str] = None


class InterfaceUpdate(BaseModel):
    """更新接口请求（全部可选）。状态不在此暴露（系统管理）。"""

    name: Optional[str] = None
    interface_type: Optional[InterfaceType] = None
    speed: Optional[InterfaceSpeed] = None
    role: Optional[InterfaceRole] = None
    interface_no: Optional[int] = None
    ip_address: Optional[str] = None


class InterfaceBatchCreate(BaseModel):
    """单组批量生成接口请求（如 48 口 RJ-45 交换机：Gig0/1..Gig0/48）。"""

    count: int
    naming_pattern: str = "Gig0/%d"  # 例如 "Gig0/%d" -> Gig0/1..Gig0/N
    interface_type: InterfaceType = InterfaceType.RJ45
    speed: InterfaceSpeed = InterfaceSpeed.G1
    role: InterfaceRole = InterfaceRole.DATA


class InterfaceMultiBatchCreate(BaseModel):
    """混合类型批量生成（大型交换机常有 RJ-45 + SFP + QSFP 多组端口）。

    ``groups`` 中每组独立生成；各组的 ``interface_no`` 在设备内全局唯一（自动错开）。
    """

    groups: list[InterfaceBatchCreate]


class InterfaceOut(BaseModel):
    """接口响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    device_id: str
    name: str
    interface_no: int = 0
    interface_type: str
    role: str
    speed: str
    status: str
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
