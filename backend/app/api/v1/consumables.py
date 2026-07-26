"""耗材管理路由：类型 / 分类 / 耗材的 CRUD + 库存变动 + 变动历史。

权限：所有写操作（增删改/库存变动）要求 ``consumable:edit``；读操作要求 ``consumable:view``。
操作人（operator）由后端从 JWT payload 注入，前端无需（也不应）传操作员身份。

端点一览：
- 类型：GET/POST /consumables/types；GET/PUT/DELETE /consumables/types/{id}
- 分类：GET/POST /consumables/types/{type_id}/categories；
        GET/PUT/DELETE /consumables/categories/{id}
- 耗材：GET/POST /consumables/items；GET/PUT/DELETE /consumables/items/{id}
- 库存变动：POST /consumables/items/{id}/adjust
- 历史：GET /consumables/items/{id}/records；GET /consumables/records（全局）
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.deps import get_db
from app.core.rbac import get_current_user, require_permission
from app.schemas.common import ok, paginated
from app.schemas.consumable import (
    ConsumableCategoryCreate,
    ConsumableCategoryOut,
    ConsumableCategoryUpdate,
    ConsumableItemCreate,
    ConsumableItemOut,
    ConsumableItemUpdate,
    ConsumableRecordOut,
    ConsumableTypeCreate,
    ConsumableTypeOut,
    ConsumableTypeUpdate,
    StockAdjustRequest,
)
from app.services.consumable_service import ConsumableService


def _operator(payload: dict) -> Optional[str]:
    """从 JWT payload 取操作人（优先 user_name，回退 sub）。"""
    return payload.get("user_name") or payload.get("sub")


def _ident(obj):
    """从 ORM 模型或 dict 提取 (id, name)，用于审计对象标识。"""
    if obj is None:
        return None, None
    if isinstance(obj, dict):
        return obj.get("id"), obj.get("name")
    return getattr(obj, "id", None), getattr(obj, "name", None)


router = APIRouter(prefix="/consumables", tags=["consumables"])


# ============ 耗材类型 ============
@router.get("/types", dependencies=[Depends(require_permission("consumable:view"))])
async def list_types(db: AsyncSession = Depends(get_db)):
    svc = ConsumableService(db)
    return ok(await svc.list_types())


@router.post("/types", dependencies=[Depends(require_permission("consumable:edit"))])
async def create_type(payload: ConsumableTypeCreate, request: Request, db: AsyncSession = Depends(get_db)):
    svc = ConsumableService(db)
    obj = await svc.create_type(payload)
    _id, name = _ident(obj)
    await log_audit(request=request, module="consumable", action="create", object_type="耗材类型", object_id=_id, object_name=name)
    return ok(obj)


@router.get("/types/{type_id}", dependencies=[Depends(require_permission("consumable:view"))])
async def get_type(type_id: str, db: AsyncSession = Depends(get_db)):
    svc = ConsumableService(db)
    return ok(await svc.get_type(type_id))


@router.put("/types/{type_id}", dependencies=[Depends(require_permission("consumable:edit"))])
async def update_type(
    type_id: str, payload: ConsumableTypeUpdate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = ConsumableService(db)
    obj = await svc.update_type(type_id, payload)
    _id, name = _ident(obj)
    await log_audit(request=request, module="consumable", action="update", object_type="耗材类型", object_id=_id, object_name=name)
    return ok(obj)


@router.delete("/types/{type_id}", dependencies=[Depends(require_permission("consumable:edit"))])
async def delete_type(type_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    svc = ConsumableService(db)
    obj = await svc.get_type(type_id)
    _id, name = _ident(obj)
    await svc.delete_type(type_id)
    await log_audit(request=request, module="consumable", action="delete", object_type="耗材类型", object_id=_id, object_name=name, detail=f"删除耗材类型「{name}」")
    return ok()


# ============ 耗材分类 ============
@router.get(
    "/types/{type_id}/categories",
    dependencies=[Depends(require_permission("consumable:view"))],
)
async def list_categories(type_id: str, db: AsyncSession = Depends(get_db)):
    svc = ConsumableService(db)
    return ok(await svc.list_categories(type_id))


@router.post(
    "/types/{type_id}/categories",
    dependencies=[Depends(require_permission("consumable:edit"))],
)
async def create_category(
    type_id: str, payload: ConsumableCategoryCreate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = ConsumableService(db)
    obj = await svc.create_category(type_id, payload)
    _id, name = _ident(obj)
    await log_audit(request=request, module="consumable", action="create", object_type="耗材分类", object_id=_id, object_name=name)
    return ok(obj)


@router.get(
    "/categories/{category_id}",
    dependencies=[Depends(require_permission("consumable:view"))],
)
async def get_category(category_id: str, db: AsyncSession = Depends(get_db)):
    svc = ConsumableService(db)
    return ok(await svc.get_category(category_id))


@router.put(
    "/categories/{category_id}",
    dependencies=[Depends(require_permission("consumable:edit"))],
)
async def update_category(
    category_id: str, payload: ConsumableCategoryUpdate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = ConsumableService(db)
    obj = await svc.update_category(category_id, payload)
    _id, name = _ident(obj)
    await log_audit(request=request, module="consumable", action="update", object_type="耗材分类", object_id=_id, object_name=name)
    return ok(obj)


@router.delete(
    "/categories/{category_id}",
    dependencies=[Depends(require_permission("consumable:edit"))],
)
async def delete_category(category_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    svc = ConsumableService(db)
    obj = await svc.get_category(category_id)
    _id, name = _ident(obj)
    await svc.delete_category(category_id)
    await log_audit(request=request, module="consumable", action="delete", object_type="耗材分类", object_id=_id, object_name=name, detail=f"删除耗材分类「{name}」")
    return ok()


# ============ 具体耗材 ============
@router.get("/items", dependencies=[Depends(require_permission("consumable:view"))])
async def list_items(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    type_id: Optional[str] = None,
    category_id: Optional[str] = None,
    keyword: Optional[str] = None,
):
    svc = ConsumableService(db)
    items, total = await svc.list_items(
        page=page, size=size, type_id=type_id, category_id=category_id, keyword=keyword
    )
    return paginated(items, total, page, size)


@router.post("/items", dependencies=[Depends(require_permission("consumable:edit"))])
async def create_item(
    payload: ConsumableItemCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    svc = ConsumableService(db)
    obj = await svc.create_item(payload, operator=_operator(current_user))
    _id, name = _ident(obj)
    await log_audit(request=request, module="consumable", action="create", object_type="耗材", object_id=_id, object_name=name)
    return ok(obj)


@router.get("/items/{item_id}", dependencies=[Depends(require_permission("consumable:view"))])
async def get_item(item_id: str, db: AsyncSession = Depends(get_db)):
    svc = ConsumableService(db)
    return ok(await svc.get_item(item_id))


@router.put("/items/{item_id}", dependencies=[Depends(require_permission("consumable:edit"))])
async def update_item(
    item_id: str, payload: ConsumableItemUpdate, request: Request, db: AsyncSession = Depends(get_db)
):
    svc = ConsumableService(db)
    obj = await svc.update_item(item_id, payload)
    _id, name = _ident(obj)
    await log_audit(request=request, module="consumable", action="update", object_type="耗材", object_id=_id, object_name=name)
    return ok(obj)


@router.delete("/items/{item_id}", dependencies=[Depends(require_permission("consumable:edit"))])
async def delete_item(item_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    svc = ConsumableService(db)
    obj = await svc.get_item(item_id)
    _id, name = _ident(obj)
    await svc.delete_item(item_id)
    await log_audit(request=request, module="consumable", action="delete", object_type="耗材", object_id=_id, object_name=name, detail=f"删除耗材「{name}」")
    return ok()


# ============ 库存变动 ============
@router.post(
    "/items/{item_id}/adjust",
    dependencies=[Depends(require_permission("consumable:edit"))],
)
async def adjust_stock(
    item_id: str,
    payload: StockAdjustRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    svc = ConsumableService(db)
    obj = await svc.adjust_stock(item_id, payload, operator=_operator(current_user))
    _id, name = _ident(obj)
    await log_audit(request=request, module="consumable", action="update", object_type="耗材", object_id=_id, object_name=name, detail=f"库存变动：{payload.operation_type} {payload.quantity}")
    return ok(obj)


# ============ 库存变动历史 ============
@router.get(
    "/items/{item_id}/records",
    dependencies=[Depends(require_permission("consumable:view"))],
)
async def item_records(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    svc = ConsumableService(db)
    records, total = await svc.list_records_by_item(item_id, page=page, size=size)
    return paginated(records, total, page, size)


@router.get("/records", dependencies=[Depends(require_permission("consumable:view"))])
async def all_records(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    type_id: Optional[str] = None,
    category_id: Optional[str] = None,
    item_id: Optional[str] = None,
    operation_type: Optional[str] = None,
):
    svc = ConsumableService(db)
    records, total = await svc.list_records(
        page=page, size=size, type_id=type_id, category_id=category_id,
        item_id=item_id, operation_type=operation_type,
    )
    return paginated(records, total, page, size)
