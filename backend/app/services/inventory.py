"""The inventory list — the page the operator actually lives on.

This module is written around one number: the count of SQL statements a page
render costs. v2's version of this screen read the settings singleton inside a
list comprehension to decide whether each row was low on stock, so showing 100
rows cost 100 extra SELECTs of a table with one row in it, and the page got
slower in exact proportion to how much stock the client had.

Here the threshold is a scalar subquery inside the same statement, the low/out
booleans are computed by Postgres, and supplier and category arrive through
eager loaders. A page costs two statements — the count and the rows —
regardless of page size. `tests/test_inventory.py` asserts that with a
statement counter rather than trusting this docstring.
"""

from typing import Any, NamedTuple

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session, contains_eager

from ..constants import ReferenceType, StockType
from ..errors import NotFound
from ..models import AppSettings, Inventory, Product, Supplier
from ..schemas.category import CategoryRef
from ..schemas.inventory import InventoryRowOut, InventorySummaryOut
from ..schemas.supplier import SupplierRef
from . import orders, stock
from .like import LIKE_ESCAPE, contains

SETTINGS_ID = 1

# The company-wide threshold, joined as a scalar subquery. Postgres reads the
# single row once for the whole statement — this is the fix for the per-row
# fetch described in the module docstring.
_THRESHOLD = (
    select(AppSettings.low_stock_threshold).where(AppSettings.id == SETTINGS_ID).scalar_subquery()
)

# Per-product override wins where it is set. Always NULL in slice 1, but
# expressing it here means enabling the field later needs no query rewrite.
_EFFECTIVE_THRESHOLD = func.coalesce(Product.low_stock_threshold, _THRESHOLD)

# Only shelf stock can run low or out: a to-order item at 0 is normal, and a
# service has no stock at all, so neither raises an alert.
_SHELF = Product.stock_type == StockType.STOCKED.value
IS_OUT_OF_STOCK = and_(_SHELF, Inventory.quantity_on_hand <= 0)
# Low excludes out, deliberately: the two header cards must sum to something an
# operator can act on, and "12 low, 3 out" reads as 15 problems, not 12.
IS_LOW_STOCK = and_(
    _SHELF,
    Inventory.quantity_on_hand > 0,
    Inventory.quantity_on_hand <= _EFFECTIVE_THRESHOLD,
)

SORTS: dict[str, Any] = {
    "available": Inventory.quantity_available.asc(),
    "-available": Inventory.quantity_available.desc(),
    "name": Product.name.asc(),
    "-name": Product.name.desc(),
}

STOCK_STATUSES = ("all", "low", "out", "ok")


class _Row(NamedTuple):
    inventory: Inventory
    is_low: bool
    is_out: bool


def _to_out(row: _Row) -> InventoryRowOut:
    product = row.inventory.product
    return InventoryRowOut(
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        model_number=product.model_number,
        unit=product.unit,
        supplier=SupplierRef.model_validate(product.supplier) if product.supplier else None,
        category=CategoryRef.model_validate(product.category) if product.category else None,
        quantity_on_hand=row.inventory.quantity_on_hand,
        quantity_reserved=row.inventory.quantity_reserved,
        quantity_available=row.inventory.quantity_available,
        is_low_stock=row.is_low,
        is_out_of_stock=row.is_out,
        stock_type=product.stock_type,
    )


def _base(
    *,
    q: str | None,
    supplier_id: int | None,
    category_id: int | None,
    stock_status: str,
    has_supplier: bool | None,
    stock_type: str | None = None,
) -> Select[Any]:
    stmt = select(Inventory).join(Product, Product.id == Inventory.product_id)
    if q:
        pattern = contains(q)
        stmt = stmt.where(
            or_(
                Product.sku.ilike(pattern, escape=LIKE_ESCAPE),
                Product.name.ilike(pattern, escape=LIKE_ESCAPE),
                Product.model_number.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    if supplier_id is not None:
        stmt = stmt.where(Product.supplier_id == supplier_id)
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if has_supplier is not None:
        stmt = stmt.where(
            Product.supplier_id.is_not(None) if has_supplier else Product.supplier_id.is_(None)
        )
    if stock_type:
        stmt = stmt.where(Product.stock_type == stock_type)
    if stock_status == "low":
        stmt = stmt.where(IS_LOW_STOCK)
    elif stock_status == "out":
        stmt = stmt.where(IS_OUT_OF_STOCK)
    elif stock_status == "ok":
        stmt = stmt.where(and_(~IS_LOW_STOCK, ~IS_OUT_OF_STOCK))
    return stmt


def list_inventory(
    db: Session,
    *,
    q: str | None = None,
    supplier_id: int | None = None,
    category_id: int | None = None,
    stock_status: str = "all",
    has_supplier: bool | None = None,
    stock_type: str | None = None,
    sort: str = "name",
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[InventoryRowOut], int]:
    """Two statements: one count, one page. Never more, whatever `limit` is."""
    stmt = _base(
        q=q,
        supplier_id=supplier_id,
        category_id=category_id,
        stock_status=stock_status,
        has_supplier=has_supplier,
        stock_type=stock_type,
    )
    total = db.execute(
        select(func.count()).select_from(stmt.with_only_columns(Inventory.id).subquery())
    ).scalar_one()

    rows = db.execute(
        stmt.add_columns(IS_LOW_STOCK.label("is_low"), IS_OUT_OF_STOCK.label("is_out"))
        # contains_eager rather than joinedload for the product: the join is
        # already in the statement for filtering and sorting, and a second
        # aliased one would be paid for nothing.
        .options(
            contains_eager(Inventory.product).joinedload(Product.supplier),
            contains_eager(Inventory.product).joinedload(Product.category),
        )
        .order_by(SORTS[sort], Inventory.product_id.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    return [_to_out(_Row(inv, is_low, is_out)) for inv, is_low, is_out in rows], total


def get_row(db: Session, product_id: int) -> InventoryRowOut:
    """One row in the same shape the list produces.

    Used by adjust and by the supplier change so the client can patch its cache
    in place instead of refetching the page it is looking at.
    """
    row = db.execute(
        select(Inventory, IS_LOW_STOCK.label("is_low"), IS_OUT_OF_STOCK.label("is_out"))
        .join(Product, Product.id == Inventory.product_id)
        .options(
            contains_eager(Inventory.product).joinedload(Product.supplier),
            contains_eager(Inventory.product).joinedload(Product.category),
        )
        .where(Inventory.product_id == product_id)
    ).first()
    if row is None:
        raise NotFound(f"Product {product_id} was not found.", product_id=product_id)
    return _to_out(_Row(row[0], row[1], row[2]))


def summary(db: Session) -> InventorySummaryOut:
    """The header cards, in one statement.

    Counts every product with an inventory row, matching what the list shows
    when no filter is applied — a card that disagreed with the table under it
    would send the operator looking for rows that are not there.
    """
    row = db.execute(
        select(
            func.count(Inventory.id),
            func.coalesce(func.sum(case((IS_LOW_STOCK, 1), else_=0)), 0),
            func.coalesce(func.sum(case((IS_OUT_OF_STOCK, 1), else_=0)), 0),
            func.coalesce(func.sum(case((Product.supplier_id.is_(None), 1), else_=0)), 0),
            # Valued at purchase cost, not sell price: this is what the stock
            # on the floor cost, which is the number an accountant asks for.
            func.coalesce(func.sum(Inventory.quantity_on_hand * Product.purchase_cost), 0),
        ).join(Product, Product.id == Inventory.product_id)
    ).one()
    return InventorySummaryOut(
        total_products=row[0],
        low_stock_count=row[1],
        out_of_stock_count=row[2],
        missing_supplier_count=row[3],
        total_stock_value_paise=row[4],
    )


def adjust(
    db: Session, *, product_id: int, delta: int, note: str, actor_id: int | None = None
) -> InventoryRowOut:
    """A manual correction. The stock service owns the rules; this owns the commit."""
    stock.adjust(
        db,
        product_id=product_id,
        delta=delta,
        ref=stock.StockRef(ReferenceType.MANUAL, note=note),
        actor_id=actor_id,
    )
    if delta > 0:
        orders.fill_waiting_orders(db, {product_id}, actor_id=actor_id)
    db.commit()
    return get_row(db, product_id)


def set_supplier(db: Session, *, product_id: int, supplier_id: int | None) -> InventoryRowOut:
    """Tag a product from the inventory page, without leaving it.

    Returns the whole refreshed row rather than an acknowledgement: the client
    replaces one entry in its cache and the table does not flicker.
    """
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound(f"Product {product_id} was not found.", product_id=product_id)
    if supplier_id is not None and db.get(Supplier, supplier_id) is None:
        raise NotFound(f"Supplier {supplier_id} was not found.", supplier_id=supplier_id)

    product.supplier_id = supplier_id
    db.commit()
    return get_row(db, product_id)
