"""The product catalogue.

Two rules this module exists to keep:

* **Every list query states its loader options.** Relationships are
  `lazy="raise"`, so a forgotten `joinedload` is an exception on the first row
  rather than 25 extra round-trips nobody measures.
* **Only `create_product` touches stock, and only through the stock service.**
  A product edit must never move a counter — see `update_product`.
"""

from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..constants import ReferenceType, StockType
from ..errors import Conflict, NotFound, ValidationFailed
from ..models import Category, Inventory, Product, StockMovement, Supplier, User
from ..schemas.product import (
    MovementActor,
    MovementOut,
    ProductCreate,
    ProductLookup,
    ProductUpdate,
)
from . import stock
from .like import LIKE_ESCAPE, contains

SORTS: dict[str, Any] = {
    "name": Product.name.asc(),
    "-name": Product.name.desc(),
    "sku": Product.sku.asc(),
    "-sku": Product.sku.desc(),
    "created_at": Product.created_at.asc(),
    "-created_at": Product.created_at.desc(),
}

# Loading the three relationships the contract's Product shape needs. Stated
# once so no endpoint can render a product with a different set loaded.
_FULL = (
    joinedload(Product.supplier),
    joinedload(Product.category),
    joinedload(Product.inventory),
)


def _filtered(
    *,
    q: str | None,
    supplier_id: int | None,
    category_id: int | None,
    is_active: bool | None,
    has_supplier: bool | None,
) -> Select[tuple[Product]]:
    stmt = select(Product)
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
    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))
    if has_supplier is not None:
        # The filter that earns its keep: after an import, products nobody
        # tagged are invisible until they block an order, so the operator needs
        # a way to ask for exactly them.
        stmt = stmt.where(
            Product.supplier_id.is_not(None) if has_supplier else Product.supplier_id.is_(None)
        )
    return stmt


def list_products(
    db: Session,
    *,
    q: str | None = None,
    supplier_id: int | None = None,
    category_id: int | None = None,
    is_active: bool | None = None,
    has_supplier: bool | None = None,
    sort: str = "name",
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[Product], int]:
    stmt = _filtered(
        q=q,
        supplier_id=supplier_id,
        category_id=category_id,
        is_active=is_active,
        has_supplier=has_supplier,
    )
    total = db.execute(
        select(func.count()).select_from(stmt.with_only_columns(Product.id).subquery())
    ).scalar_one()
    rows = (
        db.execute(
            stmt.options(*_FULL).order_by(SORTS[sort], Product.id.asc()).offset(offset).limit(limit)
        )
        .scalars()
        .unique()
        .all()
    )
    return list(rows), total


def get_product(db: Session, product_id: int) -> Product:
    product = db.execute(
        select(Product).options(*_FULL).where(Product.id == product_id)
    ).scalar_one_or_none()
    if product is None:
        raise NotFound(f"Product {product_id} was not found.", product_id=product_id)
    return product


def lookup_products(db: Session, *, q: str | None = None, limit: int = 20) -> list[ProductLookup]:
    """A type-ahead picker for documents that list items: active only, short list.

    Columns are selected explicitly rather than loading Product rows, so
    `purchase_cost` is never even fetched on this path — what we paid must never
    reach a customer-facing screen, and not selecting it is a stronger
    guarantee than remembering to omit it from a schema. Inventory is an inner
    join because `create_product` gives every product its row in the same
    transaction, so a product without one does not exist.
    """
    stmt = (
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.model_number,
            Product.unit,
            Product.hsn_code,
            Product.sell_price,
            Inventory.quantity_available,
            Product.stock_type,
        )
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Product.is_active.is_(True))
    )
    if q:
        pattern = contains(q)
        stmt = stmt.where(
            or_(
                Product.sku.ilike(pattern, escape=LIKE_ESCAPE),
                Product.name.ilike(pattern, escape=LIKE_ESCAPE),
                Product.model_number.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    rows = db.execute(stmt.order_by(Product.name.asc(), Product.id.asc()).limit(limit)).all()
    return [ProductLookup.model_validate(row, from_attributes=True) for row in rows]


def _check_relations(db: Session, supplier_id: int | None, category_id: int | None) -> None:
    """Fail with a message naming the missing row, not with a foreign-key error."""
    if supplier_id is not None and db.get(Supplier, supplier_id) is None:
        raise NotFound(f"Supplier {supplier_id} was not found.", supplier_id=supplier_id)
    if category_id is not None and db.get(Category, category_id) is None:
        raise NotFound(f"Category {category_id} was not found.", category_id=category_id)


def _reject_duplicate_sku(db: Session, sku: str, *, exclude_id: int | None = None) -> None:
    stmt = select(Product.id).where(func.lower(Product.sku) == sku.strip().lower())
    if exclude_id is not None:
        stmt = stmt.where(Product.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise Conflict(f"A product with SKU '{sku.strip()}' already exists.", sku=sku.strip())


_SKU_PREFIX = {StockType.STOCKED: "ITM", StockType.TO_ORDER: "ORD", StockType.SERVICE: "SRV"}


def _next_sku(db: Session, stock_type: StockType) -> str:
    """The next free SKU of the type's series: ORD-0001, ORD-0002, ..."""
    prefix = _SKU_PREFIX[stock_type]
    used = db.execute(select(Product.sku).where(Product.sku.op("~")(rf"^{prefix}-\d+$"))).scalars()
    n = max((int(s.split("-", 1)[1]) for s in used), default=0)
    return f"{prefix}-{n + 1:04d}"


def create_product(db: Session, body: ProductCreate, *, actor_id: int | None = None) -> Product:
    """Product, inventory row and opening movement — one transaction.

    A single commit at the end is the point. Committing the product first and
    then receiving stock would let a crash in between leave a product with no
    inventory row, which every later stock operation would reject with "no
    inventory record" and no way to fix it from the UI.
    """
    if body.stock_type == StockType.SERVICE and body.opening_quantity > 0:
        raise ValidationFailed("A service has no stock; leave the opening quantity at 0.")
    sku = body.sku.strip() or _next_sku(db, body.stock_type)
    _reject_duplicate_sku(db, sku)
    _check_relations(db, body.supplier_id, body.category_id)

    data = body.model_dump(exclude={"opening_quantity"})
    product = Product(**{**data, "sku": sku, "name": body.name.strip()})
    db.add(product)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(f"A product with SKU '{sku}' already exists.") from exc

    # A fresh INSERT, not an UPDATE, so the stock guard allows it: there is no
    # movement to record because the counters start at zero either way.
    db.add(Inventory(product_id=product.id))
    db.flush()

    if body.opening_quantity > 0:
        stock.receive(
            db,
            product_id=product.id,
            qty=body.opening_quantity,
            ref=stock.StockRef(ReferenceType.MANUAL, note="Opening stock"),
            actor_id=actor_id,
        )

    db.commit()
    return get_product(db, product.id)


def update_product(db: Session, product_id: int, body: ProductUpdate) -> Product:
    """Catalogue fields only.

    There is deliberately no quantity path here — not even a guarded one. Stock
    moves through /inventory so that every change has a movement behind it.
    """
    product = get_product(db, product_id)
    changes = body.model_dump(exclude_unset=True)

    if changes.get("sku") is not None:
        changes["sku"] = changes["sku"].strip()
        _reject_duplicate_sku(db, changes["sku"], exclude_id=product_id)
    _check_relations(
        db,
        changes.get("supplier_id") if "supplier_id" in changes else None,
        changes.get("category_id") if "category_id" in changes else None,
    )

    for field, value in changes.items():
        # supplier_id and category_id are nullable relations: an explicit null
        # clears them, which is how the UI removes a tag. Every other field
        # treats None as "not sent".
        if value is None and field not in {"supplier_id", "category_id"}:
            continue
        setattr(product, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("A product with that SKU already exists.") from exc
    return get_product(db, product_id)


def deactivate_product(db: Session, product_id: int) -> None:
    """Soft delete: the ledger references this product forever."""
    product = get_product(db, product_id)
    product.is_active = False
    db.commit()


def list_movements(
    db: Session, product_id: int, *, offset: int = 0, limit: int = 25
) -> tuple[list[MovementOut], int]:
    """Newest first.

    The actor is fetched by an explicit outer join rather than a relationship:
    StockMovement has none, and adding one would give the ledger a mutable edge
    into a table it only ever names.
    """
    get_product(db, product_id)

    total = db.execute(
        select(func.count(StockMovement.id)).where(StockMovement.product_id == product_id)
    ).scalar_one()
    rows = db.execute(
        select(StockMovement, User.id, User.full_name)
        .outerjoin(User, User.id == StockMovement.created_by_id)
        .where(StockMovement.product_id == product_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        MovementOut.model_validate(
            {
                **{
                    field: getattr(movement, field)
                    for field in MovementOut.model_fields
                    if field != "created_by"
                },
                "created_by": (
                    MovementActor(id=user_id, full_name=full_name) if user_id is not None else None
                ),
            }
        )
        for movement, user_id, full_name in rows
    ]
    return items, total
