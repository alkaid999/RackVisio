"""硬件管理相关 Schema。

层级：硬件类型（HardwareType）→ 分类（HardwareCategory）→ 具体硬件（HardwareItem）
→ 硬件变动记录（HardwareRecord）。

与耗材的关键差异（独立个体模型）：HardwareItem 是**一件实物一行记录**，无批量库存字段；
设备添加硬件 = 选具体某件（``assign_to_device``），一对一（``assigned_device_id``）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# ============ 硬件类型 ============
class HardwareTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None


class ReorderRequest(BaseModel):
    """手动排序：按展示顺序传入实体 id 列表（index 0 最靠前），后端持久化 sort_order。"""

    ids: list[str] = Field(..., min_length=1)


class HardwareTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: Optional[str] = None


class HardwareTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 汇总：该类型下分类数与硬件数（列表展示用，repo 填充）。
    category_count: int = 0
    item_count: int = 0


# ============ 硬件分类 ============
class HardwareCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None


class HardwareCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: Optional[str] = None


class HardwareCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type_id: str
    name: str
    description: Optional[str] = None
    type_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    item_count: int = 0


# ============ 具体硬件（独立个体）============
class HardwareItemCreate(BaseModel):
    type_id: str
    category_id: str
    name: str = Field(..., min_length=1, max_length=128)
    # 需求#3 新增字段：品牌 / SN 号（独立编号，建议填写，非空时唯一）。
    brand: Optional[str] = Field(default=None, max_length=64)
    sn: Optional[str] = Field(default=None, max_length=64)
    spec: Optional[str] = Field(default=None, max_length=128)
    remark: Optional[str] = None


class HardwareItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    brand: Optional[str] = Field(default=None, max_length=64)
    sn: Optional[str] = Field(default=None, max_length=64)
    spec: Optional[str] = Field(default=None, max_length=128)
    remark: Optional[str] = None


class HardwareItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type_id: str
    category_id: str
    name: str
    brand: Optional[str] = None
    sn: Optional[str] = None
    spec: Optional[str] = None
    status: str
    # 一对一设备关联：非空 = 已安装于该设备；空 = 在库。
    assigned_device_id: Optional[str] = None
    assigned_at: Optional[datetime] = None
    remark: Optional[str] = None
    # 冗余展示字段（service 填充）。
    type_name: Optional[str] = None
    category_name: Optional[str] = None
    assigned_device_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============ 硬件变动 ============
class HardwareRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    item_id: str
    operation_time: Optional[datetime] = None
    operation_type: str
    device_name: Optional[str] = None
    reason: Optional[str] = None
    operator: Optional[str] = None
    # 冗余展示字段（service 填充）。
    item_name: Optional[str] = None
    item_sn: Optional[str] = None
    type_name: Optional[str] = None
    category_name: Optional[str] = None
    created_at: Optional[datetime] = None


# ============ 设备硬件关联 ============
class DeviceHardwareAssignRequest(BaseModel):
    """将某一件硬件（独立个体）分配到设备。

    - hardware_item_id：硬件管理中「在库」的具体硬件（与机柜上架从设备列表选择同理）。
    - remark：安装备注（如插槽位，选填）。
    """

    hardware_item_id: str
    remark: Optional[str] = Field(default=None, max_length=255)
