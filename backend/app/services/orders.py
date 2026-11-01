"""Orders from accepted quotations, and the purchase orders they need.

The rules, all here:

* Accepting a quotation creates its order in the same transaction. Every
  item must be a product from the catalogue — stock cannot be checked for
  free text — so accepting is refused while any item is not.
* A quotation line made of several items (a pump set) becomes one order line
  per item, quantity = the item's quantity per set x the sets quoted, so each
  item's stock is held and delivered on its own. Its description is never
  read for stock.
* The order holds (reserves) whatever stock is available now, item by item,
  so nobody else can sell it. For each item still short, a draft purchase
  order is prepared, one per supplier.
* Nothing ships until everything is held: the order is `waiting_stock` until
  every item is fully reserved, then `ready` for Product Delivery.
* "Check stock again" tops up the reservations after goods arrive.
* Product Delivery takes the reserved stock out of the shop, one movement per
  item, and closes the order.

Stock only ever moves through `services.stock`.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session, selectinload

from ..constants import LineKind, OrderStatus, PurchaseOrderStatus, ReferenceType, StockType
from ..errors import Conflict, NotFound, ValidationFailed
from ..models import (
    Customer,
    Inventory,
    Order,
    OrderLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Quotation,
    Supplier,
    SupplierBranch,
)
from . import stock
from .like import LIKE_ESCAPE, contains
from .stock import StockRef

IST = timezone(timedelta(hours=5, minutes=30))
# Purchase orders always carry 18% GST: SGST 9% + CGST 9%.
PO_GST_RATE_BP = 1800


def _base_number(quotation: Quotation) -> str:
    """ESQSP-26-2-R1N3 -> ESQSP-26-2: the order is for the quote, not a version."""
    return quotation.base_number


def unlinked_items(quotation: Quotation) -> list[str]:
    """Product lines that are free text: an order cannot check their stock."""
    return [
        ln.description
        for ln in quotation.lines
        if ln.kind == LineKind.PRODUCT and ln.product_id is None and not ln.components
    ]


def _load(stmt: Select[tuple[Order]]) -> Select[tuple[Order]]:
    return stmt.options(
        selectinload(Order.customer),
        selectinload(Order.lines).selectinload(OrderLine.product),
    )


def get_order(db: Session, order_id: int) -> Order:
    row = db.execute(_load(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if row is None:
        raise NotFound(f"Order {order_id} was not found.", order_id=order_id)
    return row


def order_for_quotation(db: Session, quotation_id: int) -> Order | None:
    return db.execute(select(Order).where(Order.quotation_id == quotation_id)).scalar_one_or_none()


def _allocate(db: Session, order: Order, actor_id: int | None) -> None:
    """Hold as much of each item as stock allows, then set the status.

    Lines are taken in product-id order, the same rule as `bulk_reserve`, so
    two orders allocating at once lock rows in the same order and cannot
    deadlock. The inventory row is locked before reading what is available,
    so the reservation that follows cannot fail on a race.
    """
    services = _service_ids(db, order)
    for line in sorted(order.lines, key=lambda ln: (ln.product_id, ln.position)):
        need = line.quantity - line.reserved
        if need <= 0:
            continue
        if line.product_id in services:
            # A service is never on a shelf: it counts as held at once, and
            # no stock is reserved for it.
            line.reserved = line.quantity
            continue
        available = db.execute(
            select(Inventory.quantity_available)
            .where(Inventory.product_id == line.product_id)
            .with_for_update()
        ).scalar_one_or_none()
        take = min(need, available or 0)
        if take > 0:
            stock.reserve(
                db,
                product_id=line.product_id,
                qty=take,
                ref=StockRef(ReferenceType.ORDER, order.id, f"Order {order.number}"),
                actor_id=actor_id,
            )
            line.reserved += take
    if order.status != OrderStatus.DELIVERED:
        complete = all(ln.reserved == ln.quantity for ln in order.lines)
        order.status = OrderStatus.READY if complete else OrderStatus.WAITING_STOCK


def _service_ids(db: Session, order: Order) -> set[int]:
    """The order's products that are services: no stock is held or delivered."""
    ids = {ln.product_id for ln in order.lines}
    if not ids:
        return set()
    return set(
        db.execute(
            select(Product.id).where(
                Product.id.in_(ids), Product.stock_type == StockType.SERVICE.value
            )
        ).scalars()
    )


def _draft_purchase_orders(db: Session, order: Order) -> list[PurchaseOrder]:
    """One draft per supplier for every item the order is still short of."""
    short = [ln for ln in order.lines if ln.reserved < ln.quantity]
    if not short:
        return []
    products = {
        p.id: p
        for p in db.execute(
            select(Product).where(Product.id.in_({ln.product_id for ln in short}))
        ).scalars()
    }
    by_supplier: dict[int | None, list[OrderLine]] = {}
    for ln in short:
        by_supplier.setdefault(products[ln.product_id].supplier_id, []).append(ln)
    drafts = []
    for supplier_id, lines in by_supplier.items():
        po = PurchaseOrder(
            number=_next_po_number(db),
            supplier_id=supplier_id,
            order_id=order.id,
            status=PurchaseOrderStatus.DRAFT,
            lines=[
                PurchaseOrderLine(
                    position=i,
                    product_id=ln.product_id,
                    description=products[ln.product_id].name,
                    quantity=ln.quantity - ln.reserved,
                    rate_paise=products[ln.product_id].purchase_cost,
                    gst_rate_bp=PO_GST_RATE_BP,
                )
                for i, ln in enumerate(lines)
            ],
        )
        db.add(po)
        db.flush()
        drafts.append(po)
    return drafts


def _next_po_number(db: Session) -> str:
    """ESPO-26-1, ESPO-26-2, ... numbered within the (IST) calendar year.

    A transaction-scoped advisory lock serialises concurrent drafts; the
    unique constraint on the number is the backstop.
    """
    year = datetime.now(IST).year % 100
    prefix = f"ESPO-{year:02d}-"
    db.execute(sql_text("SELECT pg_advisory_xact_lock(hashtext('purchase_order_number'))"))
    numbers = db.execute(
        select(PurchaseOrder.number).where(PurchaseOrder.number.like(f"{prefix}%"))
    ).scalars()
    last = max((int(n[len(prefix) :]) for n in numbers if n[len(prefix) :].isdigit()), default=0)
    return f"{prefix}{last + 1}"


def ensure_orderable(quotation: Quotation) -> None:
    """Every item must be a catalogue product, and there must be at least one."""
    missing = unlinked_items(quotation)
    if missing:
        raise ValidationFailed(
            "These items are not in Products, so their stock cannot be checked: "
            + "; ".join(missing)
            + ". Add them in Products, pick them from the catalogue on the quote, then accept.",
            items=missing,
        )
    if not any(ln.kind == LineKind.PRODUCT for ln in quotation.lines):
        raise ValidationFailed("This quotation has no items to order.")


def create_from_quotation(db: Session, quotation: Quotation, *, actor_id: int | None) -> Order:
    """Make the order for an accepted quotation. Does not commit.

    The caller (accepting the quote) owns the transaction, so the status
    change, the reservations and the purchase drafts land together or not
    at all.
    """
    existing = order_for_quotation(db, quotation.id)
    if existing is not None:
        return existing
    ensure_orderable(quotation)
    products = [ln for ln in quotation.lines if ln.kind == LineKind.PRODUCT]
    # The items of every multi-item line must still be in the catalogue.
    wanted = {c["product_id"] for ln in products for c in ln.components}
    catalogue = {
        p.id: p for p in db.execute(select(Product).where(Product.id.in_(wanted))).scalars()
    }
    gone = sorted(
        {
            c.get("name") or f"#{c['product_id']}"
            for ln in products
            for c in ln.components
            if c["product_id"] not in catalogue or not catalogue[c["product_id"]].is_active
        }
    )
    if gone:
        raise ValidationFailed(
            "These items are no longer in Inventory: "
            + "; ".join(gone)
            + ". Remove or replace them on the quote, then accept.",
            items=gone,
        )
    order_lines: list[OrderLine] = []
    for i, ln in enumerate(products):
        if not ln.components:
            order_lines.append(
                OrderLine(
                    position=len(order_lines),
                    product_id=ln.product_id,
                    description=ln.description,
                    quantity=ln.quantity,
                    rate_paise=ln.rate_paise,
                    reserved=0,
                    source_position=i,
                )
            )
            continue
        for j, c in enumerate(ln.components):
            order_lines.append(
                OrderLine(
                    position=len(order_lines),
                    product_id=c["product_id"],
                    description=catalogue[c["product_id"]].name,
                    quantity=c["quantity"] * ln.quantity,
                    rate_paise=0,
                    reserved=0,
                    source_position=i,
                    set_description=ln.description,
                    amount_paise=ln.value_paise if j == 0 else 0,
                )
            )
    order = Order(
        number=f"ORD-{_base_number(quotation)}",
        quotation_id=quotation.id,
        customer_id=quotation.customer_id,
        status=OrderStatus.WAITING_STOCK,
        created_by_id=actor_id,
        lines=order_lines,
    )
    db.add(order)
    db.flush()
    _allocate(db, order, actor_id)
    _draft_purchase_orders(db, order)
    return order


def recheck(db: Session, order_id: int, *, actor_id: int | None) -> Order:
    """Top up the reservations from stock that has arrived since."""
    order = get_order(db, order_id)
    if order.status == OrderStatus.DELIVERED:
        raise Conflict(f"{order.number} has already been delivered.")
    _allocate(db, order, actor_id)
    db.commit()
    return get_order(db, order_id)


def deliver(db: Session, order_id: int, *, actor_id: int | None) -> Order:
    """Product Delivery: the held stock leaves the shop, and the order closes."""
    order = get_order(db, order_id)
    if order.status == OrderStatus.DELIVERED:
        raise Conflict(f"{order.number} has already been delivered.")
    if order.status != OrderStatus.READY:
        raise Conflict(
            f"{order.number} is still waiting for stock; every item must be in before delivery."
        )
    services = _service_ids(db, order)
    for line in sorted(order.lines, key=lambda ln: (ln.product_id, ln.position)):
        if line.product_id in services:
            continue  # nothing leaves the shelf for a service
        stock.deliver(
            db,
            product_id=line.product_id,
            qty=line.quantity,
            ref=StockRef(ReferenceType.ORDER, order.id, f"Product Delivery {order.number}"),
            actor_id=actor_id,
        )
    order.status = OrderStatus.DELIVERED
    order.delivered_at = datetime.now(UTC)
    db.commit()
    return get_order(db, order_id)


def list_orders(
    db: Session,
    *,
    q: str | None = None,
    status: OrderStatus | None = None,
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[Order], int]:
    stmt = select(Order)
    if q:
        pattern = contains(q)
        stmt = stmt.join(Order.customer).where(
            or_(
                Order.number.ilike(pattern, escape=LIKE_ESCAPE),
                Customer.name.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    if status is not None:
        stmt = stmt.where(Order.status == status)
    total = db.execute(
        select(func.count()).select_from(stmt.with_only_columns(Order.id).subquery())
    ).scalar_one()
    rows = (
        db.execute(
            _load(
                stmt.order_by(Order.created_at.desc(), Order.id.desc()).offset(offset).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


# --- purchase orders -----------------------------------------------------------


def _load_po(stmt: Select[tuple[PurchaseOrder]]) -> Select[tuple[PurchaseOrder]]:
    return stmt.options(
        selectinload(PurchaseOrder.supplier),
        selectinload(PurchaseOrder.supplier_branch),
        selectinload(PurchaseOrder.lines),
    )


def get_purchase_order(db: Session, po_id: int) -> PurchaseOrder:
    row = db.execute(
        _load_po(select(PurchaseOrder).where(PurchaseOrder.id == po_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(f"Purchase order {po_id} was not found.", purchase_order_id=po_id)
    return row


def purchase_orders_for(db: Session, order_id: int) -> list[PurchaseOrder]:
    return list(
        db.execute(
            _load_po(
                select(PurchaseOrder)
                .where(PurchaseOrder.order_id == order_id)
                .order_by(PurchaseOrder.id)
            )
        )
        .scalars()
        .all()
    )


def list_purchase_orders(
    db: Session,
    *,
    q: str | None = None,
    status: PurchaseOrderStatus | None = None,
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[PurchaseOrder], int]:
    stmt = select(PurchaseOrder)
    if q:
        pattern = contains(q)
        stmt = stmt.outerjoin(PurchaseOrder.supplier).where(
            or_(
                PurchaseOrder.number.ilike(pattern, escape=LIKE_ESCAPE),
                Supplier.name.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    if status is not None:
        stmt = stmt.where(PurchaseOrder.status == status)
    total = db.execute(
        select(func.count()).select_from(stmt.with_only_columns(PurchaseOrder.id).subquery())
    ).scalar_one()
    rows = (
        db.execute(
            _load_po(
                stmt.order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


def set_po_supplier(
    db: Session, po_id: int, supplier_id: int, branch_id: int | None = None
) -> PurchaseOrder:
    """Choose the supplier, and optionally one of its branches (else its head office)."""
    po = get_purchase_order(db, po_id)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise Conflict(f"{po.number} has been sent; its supplier can no longer change.")
    if db.get(Supplier, supplier_id) is None:
        raise NotFound(f"Supplier {supplier_id} was not found.", supplier_id=supplier_id)
    if branch_id is not None:
        branch = db.get(SupplierBranch, branch_id)
        if branch is None or branch.supplier_id != supplier_id or not branch.is_active:
            raise ValidationFailed(
                "That branch does not belong to the chosen supplier.", branch_id=branch_id
            )
    po.supplier_id = supplier_id
    po.supplier_branch_id = branch_id
    db.commit()
    return get_purchase_order(db, po_id)


def mark_po_sent(db: Session, po_id: int) -> PurchaseOrder:
    po = get_purchase_order(db, po_id)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise Conflict(f"{po.number} has already been sent.")
    if po.supplier_id is None:
        raise ValidationFailed("Choose the supplier before sending this purchase order.")
    po.status = PurchaseOrderStatus.SENT
    po.sent_at = datetime.now(UTC)
    db.commit()
    return get_purchase_order(db, po_id)


def fill_waiting_orders(db: Session, product_ids: set[int], *, actor_id: int | None) -> None:
    """Stock came in: hold it for orders waiting on those products, oldest first.

    Called wherever goods arrive (a purchase order received, an inventory
    top-up), so an order moves to ready without anyone pressing a button.
    Does not commit; the caller owns the transaction.
    """
    if not product_ids:
        return
    waiting = (
        db.execute(
            _load(
                select(Order)
                .where(
                    Order.status == OrderStatus.WAITING_STOCK,
                    Order.id.in_(
                        select(OrderLine.order_id).where(OrderLine.product_id.in_(product_ids))
                    ),
                )
                .order_by(Order.created_at, Order.id)
            )
        )
        .scalars()
        .all()
    )
    for order in waiting:
        _allocate(db, order, actor_id)


def receive_po(db: Session, po_id: int, *, actor_id: int | None) -> PurchaseOrder:
    """Goods arrived: into inventory first, then held for the orders waiting on them."""
    po = get_purchase_order(db, po_id)
    if po.status == PurchaseOrderStatus.RECEIVED:
        raise Conflict(f"{po.number} has already been received.")
    if po.supplier_id is None:
        raise ValidationFailed("Choose the supplier before receiving this purchase order.")
    for line in sorted(po.lines, key=lambda ln: (ln.product_id, ln.position)):
        stock.receive(
            db,
            product_id=line.product_id,
            qty=line.quantity,
            ref=StockRef(ReferenceType.PURCHASE_ORDER, po.id, f"Received {po.number}"),
            actor_id=actor_id,
        )
    po.status = PurchaseOrderStatus.RECEIVED
    po.received_at = datetime.now(UTC)
    fill_waiting_orders(db, {ln.product_id for ln in po.lines}, actor_id=actor_id)
    db.commit()
    return get_purchase_order(db, po_id)


def order_out(db: Session, order: Order) -> dict[str, Any]:
    """The order with each line's stock position, for the screen."""
    quotation = db.get(Quotation, order.quotation_id)
    return {
        "id": order.id,
        "number": order.number,
        "status": order.status,
        "quotation_id": order.quotation_id,
        "quotation_number": quotation.number if quotation else "",
        "customer": order.customer,
        "delivered_at": order.delivered_at,
        "created_at": order.created_at,
        "total_paise": sum(ln.value_paise for ln in order.lines),
        "lines": [
            {
                "id": ln.id,
                "product_id": ln.product_id,
                "sku": ln.product.sku,
                "description": ln.description,
                "quantity": ln.quantity,
                "reserved": ln.reserved,
                "short": ln.quantity - ln.reserved,
                "rate_paise": ln.rate_paise,
                "value_paise": ln.value_paise,
                "set_description": ln.set_description,
            }
            for ln in order.lines
        ],
    }
