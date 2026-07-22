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
    """更新链路请求（全部可选）。"""

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


class TopologyNode(BaseModel):
    """拓扑节点（设备）。"""

    id: str
    name: str
    device_type: str
    status: str
    rack_id: Optional[str] = None


class TopologyEdge(BaseModel):
    """拓扑边（链路）。source / target 为设备 id。"""

    id: str
    source: str
    target: str
    source_interface: Optional[str] = None
    target_interface: Optional[str] = None
    remark: Optional[str] = None
    medium: str = "tp"
    cable_length: Optional[str] = None


class TopologyResponse(BaseModel):
    """拓扑数据（nodes + edges）。"""

    nodes: list[TopologyNode] = []
    edges: list[TopologyEdge] = []
