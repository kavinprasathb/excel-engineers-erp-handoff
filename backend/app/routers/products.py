"""The product catalogue."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Pagination, get_current_user, get_pagination, owner_only
from ..models import User
from ..schemas.common import Page
from ..schemas.product import (
    MovementOut,
    ProductCreate,
    ProductLookup,
    ProductOut,
    ProductUpdate,
)
from ..services import products as service
from ..viewer import is_owner

router = APIRouter(prefix="/products", tags=["products"])

ProductSort = Literal["name", "-name", "sku", "-sku", "created_at", "-created_at"]


@router.get("", response_model=Page[ProductOut])
def list_products(
    q: str | None = Query(default=None, max_length=200),
    supplier_id: int | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
    has_supplier: bool | None = Query(
        default=None,
        description="false finds products no supplier has been assigned to — "
        "the ones an import leaves untagged.",
    ),
    sort: ProductSort = "name",
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[ProductOut]:
    items, total = service.list_products(
        db,
        q=q,
        supplier_id=supplier_id,
        category_id=category_id,
        is_active=is_active,
        has_supplier=has_supplier,
        sort=sort,
        offset=page.offset,
        limit=page.limit,
    )
    return Page.build(
        [ProductOut.model_validate(p) for p in items],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProductOut:
    """Product, inventory row and opening movement, or none of them."""
    if not is_owner(user):
        # Staff never see purchase cost, so they cannot set it either.
        body = body.model_copy(update={"purchase_cost": 0})
    return ProductOut.model_validate(service.create_product(db, body, actor_id=user.id))


@router.get("/lookup", response_model=list[ProductLookup])
def lookup_products(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ProductLookup]:
    """A type-ahead product picker for any document that lists items.

    Declared before `/{product_id}` — the other way round "lookup" is read as
    an id and every keystroke in the picker gets a 422. Unpaginated on purpose:
    a type-ahead wants the best few matches, not an envelope and a page count.
    """
    return service.lookup_products(db, q=q, limit=limit)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ProductOut:
    return ProductOut.model_validate(service.get_product(db, product_id))


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    body: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProductOut:
    """Catalogue fields only — stock moves through /inventory and nowhere else."""
    if not is_owner(user):
        body = ProductUpdate.model_validate(
            body.model_dump(exclude_unset=True, exclude={"purchase_cost"})
        )
    return ProductOut.model_validate(service.update_product(db, product_id, body))


@router.delete(
    "/{product_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(owner_only)]
)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    """Soft delete: the stock ledger references this product forever."""
    service.deactivate_product(db, product_id)


@router.get("/{product_id}/movements", response_model=Page[MovementOut])
def list_movements(
    product_id: int,
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[MovementOut]:
    items, total = service.list_movements(db, product_id, offset=page.offset, limit=page.limit)
    return Page.build(items, total=total, page=page.page, page_size=page.page_size)
