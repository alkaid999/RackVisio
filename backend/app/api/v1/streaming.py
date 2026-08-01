"""导出流式响应工具（P-01）：分批查询 + 流式 JSON 数组。

响应体仍是合法 JSON 信封 ``{"code":0,"message":"ok","data":[...]}``——仅传输方式
改为分块：服务端逐批查询、逐批序列化、逐块发送，**峰值内存 = 一批行**而非全量
（修复导出端点 size=100000 一次性全量加载的内存峰值）。前端 http 客户端
（axios/fetch）等完整 body 后 JSON.parse 行为不变，**前端零改动**。
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Awaitable, Callable

from fastapi.responses import StreamingResponse

# 每批拉取行数：控制服务端峰值内存与单次查询耗时（DCIM 数据量下 500 行/批合适）。
EXPORT_BATCH_SIZE = 500


async def _json_array_chunks(batches: AsyncIterator[list[Any]]) -> AsyncIterator[str]:
    """把分批行数组流式拼成 JSON 数组信封（与 ok() 同构）。"""
    yield '{"code":0,"message":"ok","data":['
    first = True
    async for batch in batches:
        for item in batch:
            if not first:
                yield ","
            # default=str 兜底 datetime 等非 JSON 原语（导出行理论上已 model_dump）。
            yield json.dumps(item, ensure_ascii=False, default=str)
            first = False
    yield "]}"


async def _batched(
    fetch: Callable[[int, int], Awaitable[tuple[list[Any], int]]],
) -> AsyncIterator[list[Any]]:
    """循环调用 fetch(page, size) 直到取完；每批内存 = EXPORT_BATCH_SIZE 行。

    fetch 签名：(page, size) -> (items, total)。以「本批行数 < 批大小 或
    page*size >= total」判定取完，兼容 total 不精确的场景。
    """
    page = 1
    while True:
        items, total = await fetch(page=page, size=EXPORT_BATCH_SIZE)
        if not items:
            break
        yield items
        if len(items) < EXPORT_BATCH_SIZE or page * EXPORT_BATCH_SIZE >= total:
            break
        page += 1


def export_json_stream(batches: AsyncIterator[list[Any]]) -> StreamingResponse:
    """把分批查询结果包装为流式 JSON 响应（信封格式与 ok() 一致，前端无感）。"""
    return StreamingResponse(
        _json_array_chunks(batches),
        media_type="application/json; charset=utf-8",
        headers={"X-Content-Type-Options": "nosniff"},
    )
