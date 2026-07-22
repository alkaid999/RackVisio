"""集中导入所有 ORM 模型，确保 Base.metadata 登记全部表。"""

from app.models.consumable import (
    ConsumableCategory,
    ConsumableItem,
    ConsumableRecord,
    ConsumableType,
)
from app.models.device import Device
from app.models.interface import DeviceInterface
from app.models.link import DeviceLink
from app.models.mount_record import MountRecord
from app.models.rack import Rack
from app.models.room import Room
from app.models.user import User

__all__ = [
    "Room",
    "Rack",
    "Device",
    "DeviceInterface",
    "DeviceLink",
    "MountRecord",
    "User",
    "ConsumableType",
    "ConsumableCategory",
    "ConsumableItem",
    "ConsumableRecord",
]
