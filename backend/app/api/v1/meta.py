"""界面元数据路由：下发标签 / 颜色 / 阈值，消除前后端双源（审查报告规范#2）。

前端在应用启动时拉取一次，渲染设备状态 / 设备类型 / 机柜状态的颜色与中文标签，
以及机柜使用率 warn/crit 阈值；``utils/constants.js`` 仅作离线兜底。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.meta import (
    DEVICE_STATUS_META,
    DEVICE_TYPE_META,
    RACK_STATUS_META,
    USAGE_COLORS,
    USAGE_CRIT,
    USAGE_WARN,
)
from app.core.rbac import require_any_permission
from app.schemas.common import ok

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get(
    "",
    dependencies=[
        Depends(
            require_any_permission(
                ["room:view", "rack:view", "device:view", "link:view", "account:view"]
            )
        )
    ],
)
async def get_meta(db: AsyncSession = Depends(get_db)):
    """下发前端渲染所需的标签 / 颜色 / 阈值（后端为权威源）。"""
    return ok(
        {
            "device_status": [{"value": k, **v} for k, v in DEVICE_STATUS_META.items()],
            "device_type": [{"value": k, **v} for k, v in DEVICE_TYPE_META.items()],
            "rack_status": [{"value": k, **v} for k, v in RACK_STATUS_META.items()],
        "usage_thresholds": {"warn": USAGE_WARN, "crit": USAGE_CRIT},
        "usage_colors": USAGE_COLORS,
    }
    )
