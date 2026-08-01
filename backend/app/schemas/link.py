"""链路与拓扑相关 Schema（接口命名统一）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.enums import ConnectorType, LinkMedium


class LinkCreate(BaseModel):
    """创建链路请求。

    本端 ``source_interface_id`` 必填；对端二选一：
    - ``target_interface_id``：对端接口在本系统内（完整链路）；
    - ``target_external``：对端不在本系统（半链路），自由文本记录对端位置。
    """

    source_interface_id: str
    target_interface_id: Optional[str] = None
    target_external: Optional[str] = None
    remark: Optional[str] = None
    medium: LinkMedium = LinkMedium.TP
    connector_type: ConnectorType  # 必填：双绞线需选线缆类别（CAT5/CAT5e/CAT6/CAT6a），光纤需指定具体连接器
    cable_length: Optional[str] = None

    @model_validator(mode="after")
    def _check_target(self) -> "LinkCreate":
        if not self.target_interface_id and not self.target_external:
            raise ValueError("必须指定对端接口或对端外部位置")
        if self.target_interface_id and self.target_external:
            raise ValueError("对端接口与对端外部位置不能同时填写")
        return self


class LinkUpdate(BaseModel):
    """更新链路请求（全部可选）。

    设计决策（R-09）：**不支持修改链路两端端点**（source/target 接口不可变）。
    链路的物理连接关系一旦变更，语义上应视为「旧链路断开 + 新链路建立」——
    两端接口的链路状态（up/down）需要同步回落与重建，直接改端点极易产生
    状态不一致（如旧对端接口仍显示已连接）。因此编辑链路仅允许修改属性
    （备注 / 介质 / 连接器 / 线缆长度）；如需更改连接关系，请先断开再新建。
    """

    remark: Optional[str] = None
    medium: Optional[LinkMedium] = None
    connector_type: Optional[ConnectorType] = None
    cable_length: Optional[str] = None


class LinkOut(BaseModel):
    """链路响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_interface_id: str
    target_interface_id: Optional[str] = None
    target_external: Optional[str] = None
    remark: Optional[str] = None
    medium: str
    connector_type: Optional[str] = None
    cable_length: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LinkDetailOut(BaseModel):
    """链路详情响应（已联表解析设备名与接口名，便于列表展示）。

    半链路时 ``target_interface_id`` 为空，``target_device_name`` 退回 ``target_external``
    文本，``target_interface_name`` 为空。
    """

    id: str
    source_device_id: str
    source_device_name: str
    source_interface_id: str
    source_interface_name: str
    target_device_id: Optional[str] = None
    target_device_name: str
    target_external: Optional[str] = None
    target_interface_id: Optional[str] = None
    target_interface_name: Optional[str] = None
    remark: Optional[str] = None
    medium: str
    connector_type: Optional[str] = None
    cable_length: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DeviceLinkView(BaseModel):
    """设备视角链路（钻取层）：归一到「本设备接口 + 对端（或外部）」。

    用于设备详情页「链路」Card：本端角色由当前设备决定，peer 展示对端
    （系统内设备名/接口，或半链路外部文本），便于单设备连接总览浏览。
    """

    link_id: str
    local_interface_id: str
    local_interface_name: str
    peer_device_id: Optional[str] = None
    peer_device_name: str
    peer_interface_id: Optional[str] = None
    peer_interface_name: Optional[str] = None
    is_half: bool = False
    medium: str
    connector_type: Optional[str] = None
    cable_length: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None

