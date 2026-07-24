"""通用 Schema 与统一响应信封工具。"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    """分页响应载荷。``data`` 字段的 ``items`` 为当前页对象列表。"""

    items: list[T] = []
    total: int = 0
    page: int = 1
    size: int = 20


class APIError(BaseModel):
    """统一错误体（信封的 data 为 null，错误信息在 message）。"""

    code: int
    message: str
    data: Any = None


def ok(data: Any = None) -> dict:
    """构造成功响应信封。"""
    return {"code": 0, "message": "ok", "data": data}


def paginated(items: list[Any], total: int, page: int, size: int) -> dict:
    """构造成功分页响应信封。"""
    return {
        "code": 0,
        "message": "ok",
        "data": {"items": items, "total": total, "page": page, "size": size},
    }


class ImportFailure(BaseModel):
    """导入单条失败明细（行号对应源文件数据行，不含表头）。"""

    row: int = Field(description="源数据中的行号（从 1 开始，对应文件第 N 行数据，不含表头）")
    errors: list[str] = Field(default_factory=list, description="该行失败原因（中文）")


class ImportResult(BaseModel):
    """导入结果摘要：成功条数 + 失败明细。"""

    created: int = 0
    failed: int = 0
    failures: list[ImportFailure] = Field(default_factory=list)
