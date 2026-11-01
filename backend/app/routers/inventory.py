"""The inventory screen: the list, its header cards, and the two edits it allows.

`/inventory/summary` is declared before `/inventory/{product_id}/...` so
"summary" is never parsed as a product id.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Pagination, get_current_user, get_pagination
from ..models import User
from ..schemas.common import Page
from ..schemas.inventory import (
    InventoryRowOut,
    InventorySummaryOut,
    StockAdjustRequest,
    SupplierAssignRequest,
)
from ..schemas.product import MovementOut
from ..services import inventory as service
from ..services import products as product_service

router = APIRouter(prefix="/inventory", tags=["inventory"])

StockStatus = Literal["all", "low", "out", "ok"]
InventorySort = Literal["available", "-available", "name", "-name"]


@router.get("", response_model=Page[InventoryRowOut])
def list_inventory(
    q: str | None = Query(default=None, max_length=200),
    supplier_id: int | None = None,
    category_id: int | None = None,
    stock_status: StockStatus = "all",
    has_supplier: bool | None = None,
    stock_type: Literal["stocked", "to_order", "service"] | None = None,
    sort: InventorySort = "name",
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[InventoryRowOut]:
    """Two SQL statements, whatever the page size — see services/inventory.py."""
    items, total = service.list_inventory(
        db,
        q=q,
        supplier_id=supplier_id,
        category_id=category_id,
        stock_status=stock_status,
        has_supplier=has_supplier,
        stock_type=stock_type,
        sort=sort,
        offset=page.offset,
        limit=page.limit,
    )
    return Page.build(items, total=total, page=page.page, page_size=page.page_size)


@router.get("/summary", response_model=InventorySummaryOut)
def inventory_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> InventorySummaryOut:
    return service.summary(db)


@router.post("/{product_id}/adjust", response_model=InventoryRowOut)
def adjust_stock(
    product_id: int,
    body: StockAdjustRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InventoryRowOut:
    """A recount or a damage write-off. Goes through the stock service, so it
    leaves a movement naming whoever did it."""
    return service.adjust(
        db, product_id=product_id, delta=body.delta, note=body.note, actor_id=user.id
    )


@router.patch("/{product_id}/supplier", response_model=InventoryRowOut)
def set_supplier(
    product_id: int,
    body: SupplierAssignRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> InventoryRowOut:
    """Tag an untagged product without leaving the inventory page.

    Returns the whole refreshed row so the client patches one cache entry
    instead of refetching the page and losing the operator's scroll position.
    """
    return service.set_supplier(db, product_id=product_id, supplier_id=body.supplier_id)


@router.get("/{product_id}/movements", response_model=Page[MovementOut])
def list_movements(
    product_id: int,
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[MovementOut]:
    """The same history as /products/{id}/movements — the drawer on this page
    should not have to know it is looking at a product."""
    items, total = product_service.list_movements(
        db, product_id, offset=page.offset, limit=page.limit
    )
    return Page.build(items, total=total, page=page.page, page_size=page.page_size)
