"""Notifications: everything that needs someone to act, worked out live.

Nothing is stored. Each notification is a question asked of the data right
now ("which quotes have had no answer for 15 days?"), so it disappears by
itself the moment the work is done: reply recorded, order delivered, stock
received. There is nothing to mark as read and nothing to go stale.

Severity:
  critical - money or a customer is at risk now (out of stock, PO with no supplier)
  warning  - overdue; chase it today
  info     - ready for the next step
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..constants import LineKind, OrderStatus, PurchaseOrderStatus, QuotationStatus
from ..models import Inventory, Order, Product, PurchaseOrder, Quotation
from .inventory import IS_LOW_STOCK, IS_OUT_OF_STOCK

IST = timezone(timedelta(hours=5, minutes=30))
QUOTE_STALE_DAYS = 15
ORDER_WAIT_DAYS = 7
PO_CHASE_DAYS = 7
MAX_STOCK_ITEMS = 50

_RANK = {"critical": 0, "warning": 1, "info": 2}


def _days(since: datetime, now: datetime) -> int:
    return max((now - since).days, 0)


def _item(
    key: str, category: str, severity: str, title: str, detail: str, link: str, days: int | None
) -> dict[str, Any]:
    return {
        "key": key,
        "category": category,
        "severity": severity,
        "title": title,
        "detail": detail,
        "link": link,
        "days": days,
    }


def _quotes(db: Session, now: datetime) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(Quotation)
            .where(Quotation.status == QuotationStatus.PENDING)
            .options(selectinload(Quotation.customer), selectinload(Quotation.lines))
        )
        .scalars()
        .all()
    )
    out = []
    for q in rows:
        idle = _days(q.updated_at, now)
        who = q.customer.name
        if idle >= QUOTE_STALE_DAYS:
            if q.revision == 0:
                out.append(
                    _item(
                        f"quote-noreply-{q.id}",
                        "quotes",
                        "warning",
                        f"No reply on {q.number}",
                        f"{who} has not answered in {idle} days. Call and mark it accepted, "
                        "declined, or negotiate.",
                        f"/quotations/{q.id}",
                        idle,
                    )
                )
            else:
                out.append(
                    _item(
                        f"quote-stuck-{q.id}",
                        "quotes",
                        "warning",
                        f"Negotiation {q.number} has gone quiet",
                        f"No change in {idle} days with {who}. Update its status.",
                        f"/quotations/{q.id}",
                        idle,
                    )
                )
        free_text = [ln for ln in q.lines if ln.kind == LineKind.PRODUCT and ln.product_id is None]
        if free_text:
            out.append(
                _item(
                    f"quote-freetext-{q.id}",
                    "quotes",
                    "info",
                    f"{q.number} has items not in Products",
                    f"{len(free_text)} item(s) must be added to Products before this quote "
                    "can be accepted.",
                    f"/quotations/{q.id}",
                    None,
                )
            )
    return out


def _orders(db: Session, now: datetime) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(Order)
            .where(Order.status != OrderStatus.DELIVERED)
            .options(selectinload(Order.customer), selectinload(Order.lines))
        )
        .scalars()
        .all()
    )
    out = []
    for o in rows:
        age = _days(o.created_at, now)
        if o.status == OrderStatus.READY:
            out.append(
                _item(
                    f"order-ready-{o.id}",
                    "orders",
                    "info",
                    f"{o.number} is ready to deliver",
                    f"Everything for {o.customer.name} is in stock. Do the Product Delivery.",
                    f"/orders/{o.id}",
                    age,
                )
            )
        elif age >= ORDER_WAIT_DAYS:
            short = sum(1 for ln in o.lines if ln.reserved < ln.quantity)
            out.append(
                _item(
                    f"order-waiting-{o.id}",
                    "orders",
                    "warning",
                    f"{o.number} waiting for stock for {age} days",
                    f"{short} item(s) for {o.customer.name} still to come. Check the purchase "
                    "orders.",
                    f"/orders/{o.id}",
                    age,
                )
            )
    return out


def _purchase_orders(db: Session, now: datetime) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(PurchaseOrder)
            .where(PurchaseOrder.status != PurchaseOrderStatus.RECEIVED)
            .options(selectinload(PurchaseOrder.supplier))
        )
        .scalars()
        .all()
    )
    out = []
    for p in rows:
        age = _days(p.created_at, now)
        if p.status == PurchaseOrderStatus.DRAFT and p.supplier is None:
            out.append(
                _item(
                    f"po-nosupplier-{p.id}",
                    "purchase_orders",
                    "critical",
                    f"{p.number} has no supplier",
                    "Choose the supplier so it can be sent.",
                    f"/purchase-orders/{p.id}",
                    age,
                )
            )
        elif p.status == PurchaseOrderStatus.DRAFT:
            out.append(
                _item(
                    f"po-unsent-{p.id}",
                    "purchase_orders",
                    "warning",
                    f"Send {p.number} to {p.supplier.name if p.supplier else ''}",
                    "Drafted for stock an order is waiting on, not sent yet.",
                    f"/purchase-orders/{p.id}",
                    age,
                )
            )
        elif age >= PO_CHASE_DAYS:
            out.append(
                _item(
                    f"po-chase-{p.id}",
                    "purchase_orders",
                    "warning",
                    f"Goods on {p.number} not received",
                    f"Sent to {p.supplier.name if p.supplier else 'the supplier'} "
                    f"{age} days ago. Chase the supplier, or mark it received.",
                    f"/purchase-orders/{p.id}",
                    age,
                )
            )
    return out


def _stock(db: Session) -> list[dict[str, Any]]:
    out = []
    for severity, cond, word in (
        ("critical", IS_OUT_OF_STOCK, "Out of stock"),
        ("warning", IS_LOW_STOCK, "Low stock"),
    ):
        rows = db.execute(
            select(Product.id, Product.name, Product.sku, Inventory.quantity_on_hand)
            .join(Inventory, Inventory.product_id == Product.id)
            .where(cond, Product.is_active.is_(True))
            .order_by(Inventory.quantity_on_hand, Product.name)
            .limit(MAX_STOCK_ITEMS)
        ).all()
        for pid, name, sku, qty in rows:
            out.append(
                _item(
                    f"stock-{severity}-{pid}",
                    "inventory",
                    severity,
                    f"{word}: {name}",
                    f"{sku + ' · ' if sku else ''}{qty} on hand. Reorder or receive stock.",
                    f"/inventory?q={sku or name}",
                    None,
                )
            )
    missing = db.execute(
        select(Product.id, Product.name)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Product.supplier_id.is_(None), Product.is_active.is_(True))
        .order_by(Product.name)
        .limit(MAX_STOCK_ITEMS)
    ).all()
    for pid, name in missing:
        out.append(
            _item(
                f"stock-nosupplier-{pid}",
                "inventory",
                "info",
                f"No supplier for {name}",
                "Set a supplier so purchase orders can be drafted for it.",
                "/inventory?has_supplier=false",
                None,
            )
        )
    return out


def notifications(db: Session) -> dict[str, Any]:
    now = datetime.now(IST)
    items = _quotes(db, now) + _orders(db, now) + _purchase_orders(db, now) + _stock(db)
    items.sort(key=lambda i: (_RANK[i["severity"]], -(i["days"] or 0), i["title"]))
    counts = {s: sum(1 for i in items if i["severity"] == s) for s in _RANK}
    by_category: dict[str, int] = {}
    for i in items:
        by_category[i["category"]] = by_category.get(i["category"], 0) + 1
    return {
        "total": len(items),
        "counts": counts,
        "by_category": by_category,
        "items": items,
    }
