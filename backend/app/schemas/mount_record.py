"""上架记录（mount_records）相关 Schema。

仅暴露可追溯字段（操作人）的编辑；U 位 / 占用 U 数不在此处修改
（调整设备 U 位请先下架再重新上架，不再提供原地改位接口）。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MountRecordUpdate(BaseModel):
    """编辑上架记录（仅操作人等追溯字段）。

    - mounted_by：上架人
    - unmounted_by：下架人
    """

    mounted_by: Optional[str] = Field(default=None, max_length=64, description="上架人")
    unmounted_by: Optional[str] = Field(default=None, max_length=64, description="下架人")
