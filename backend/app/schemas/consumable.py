"""耗材管理相关 Schema。

层级：耗材类型（ConsumableType）→ 分类（ConsumableCategory）→ 具体耗材（ConsumableItem）
→ 库存变动记录（ConsumableRecord）。类型/分类/耗材均为用户自定义，无枚举限制。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# ============ 耗材类型 ============
class ConsumableTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None


class ConsumableTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: Optional[str] = None


class ConsumableTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 汇总：该类型下分类数与耗材数（列表展示用，repo 填充）。
    category_count: int = 0
    item_count: int = 0


# ============ 耗材分类 ============
class ConsumableCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None


class ConsumableCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: Optional[str] = None


class ConsumableCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type_id: str
    name: str
    description: Optional[str] = None
    type_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    item_count: int = 0


# ============ 具体耗材 ============
class ConsumableItemCreate(BaseModel):
    type_id: str
    category_id: str
    name: str = Field(..., min_length=1, max_length=128)
    spec: Optional[str] = Field(default=None, max_length=128)
    unit: Optional[str] = Field(default=None, max_length=16)
    # 初始数量（建项时即录入结存，落一条「盘点」记录以留痕）。缺省 0。
    current_quantity: int = Field(default=0, ge=0)
    remark: Optional[str] = None


class ConsumableItemUpdate(BaseModel):
    # 仅允许改属性，不允许通过 update 直接改 current_quantity（必须经库存变动接口）。
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    spec: Optional[str] = Field(default=None, max_length=128)
    unit: Optional[str] = Field(default=None, max_length=16)
    remark: Optional[str] = None


class ConsumableItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type_id: str
    category_id: str
    name: str
    spec: Optional[str] = None
    unit: Optional[str] = None
    current_quantity: int
    remark: Optional[str] = None
    type_name: Optional[str] = None
    category_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============ 库存变动 ============
class StockAdjustRequest(BaseModel):
    """发起一次库存变动（入库 / 领用 / 报废 / 盘点）。

    - operation_type：入库/领用/报废/盘点（见 ConsumableOpType 取值）。
    - quantity：数量（正整数字面量）。领用/报废/入库须 >=1；盘点为该次实盘后的实际结存（>=0）。
    - operation_time：业务操作时间，缺省为当前时刻（便于补录历史单据）。
    - reason：操作原因/备注（选填）。
    """

    operation_type: str = Field(..., min_length=1, max_length=16)
    quantity: int = Field(..., ge=0, description="数量（>=0）")
    reason: Optional[str] = Field(default=None, max_length=255)
    operation_time: Optional[datetime] = None


class ConsumableRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    item_id: str
    operation_time: Optional[datetime] = None
    operation_type: str
    quantity: int
    reason: Optional[str] = None
    operator: Optional[str] = None
    balance_after: int
    # 冗余展示字段（repo 填充），便于全局历史列表跨耗材展示。
    item_name: Optional[str] = None
    type_name: Optional[str] = None
    category_name: Optional[str] = None
    created_at: Optional[datetime] = None
