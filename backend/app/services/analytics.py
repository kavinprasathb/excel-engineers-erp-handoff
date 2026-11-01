"""Analytics: how quotes convert, what sells, and where deals get stuck.

Everything is computed in Python over the period's rows — a dealer writes
hundreds of offers a year, not millions — so the rules stay readable and in
one place.

The rules:

* A quote is one *number* (ESQSP-26-70) with all its revised quotations
  (R1, R2...) and negotiations (N1, N2...), counted once. Its period is the
  day the first version was sent; its outcome and current value are the
  latest version's.
* A sale is a delivered order, dated by its Product Delivery.
* Amounts include GST at 18%, the rate the business works at.
* The pending pipeline is "right now", not limited to the period.
"""

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..constants import (
    DECLINE_REASONS,
    LineKind,
    MovementType,
    OrderStatus,
    PurchaseOrderStatus,
    QuotationStatus,
)
from ..models import (
    AppSettings,
    Inventory,
    Order,
    OrderLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Quotation,
    StockMovement,
)

IST = timezone(timedelta(hours=5, minutes=30))
GST_BP = 1800
# A pending quote older than this needs a follow-up call.
FOLLOW_UP_DAYS = 15


def with_gst(paise: int) -> int:
    return paise + round(paise * GST_BP / 10000)


def reason_bucket(reason: str) -> str:
    """'Price too high' or 'Other: ...' -> the reason it is counted under."""
    head = reason.split(":", 1)[0].strip()
    return head if head in DECLINE_REASONS else "Other"


def _chains(db: Session) -> list[list[Quotation]]:
    rows = (
        db.execute(
            select(Quotation)
            .options(selectinload(Quotation.customer), selectinload(Quotation.lines))
            .order_by(Quotation.type, Quotation.year, Quotation.seq, Quotation.revision)
        )
        .scalars()
        .all()
    )
    chains: dict[tuple[str, int, int], list[Quotation]] = {}
    for r in rows:
        chains.setdefault((r.type.value, r.year, r.seq), []).append(r)
    return list(chains.values())


def _in(d: date, date_from: date | None, date_to: date | None) -> bool:
    return (date_from is None or d >= date_from) and (date_to is None or d <= date_to)


def _pct(part: int, whole: int) -> float | None:
    return round(part * 100 / whole, 1) if whole else None


def _month(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _closed_on(q: Quotation) -> date:
    """When the latest version got its answer: its last change, in IST."""
    return q.updated_at.astimezone(IST).date()


def report(db: Session, *, date_from: date | None, date_to: date | None) -> dict[str, Any]:
    all_chains = _chains(db)
    chains = [c for c in all_chains if _in(c[0].quote_date, date_from, date_to)]
    today = datetime.now(IST).date()

    # --- conversion ---------------------------------------------------------
    counts: dict[str, int] = {s: 0 for s in ("pending", "accepted", "declined")}
    values = {s: 0 for s in counts}
    reasons: dict[str, int] = {r: 0 for r in DECLINE_REASONS}
    reasons["Other"] = 0
    declined_list: list[dict[str, Any]] = []
    for c in chains:
        latest = c[-1]
        key = latest.status.value if latest.status.value in counts else "pending"
        counts[key] += 1
        values[key] += with_gst(latest.total_paise)
        if latest.status == QuotationStatus.DECLINED:
            reasons[reason_bucket(latest.decline_reason)] += 1
            declined_list.append(
                {
                    "id": latest.id,
                    "number": latest.number,
                    "customer": latest.customer.name,
                    "reason": latest.decline_reason,
                    "value_paise": with_gst(latest.total_paise),
                }
            )
    total = len(chains)
    answered = counts["accepted"] + counts["declined"]
    conversion = {
        "quoted": total,
        "quoted_value_paise": sum(values.values()),
        **{f"{k}_count": v for k, v in counts.items()},
        **{f"{k}_value_paise": v for k, v in values.items()},
        # Won out of all quotes, and won out of those the customer answered.
        "rate_all": _pct(counts["accepted"], total),
        "rate_answered": _pct(counts["accepted"], answered),
        "reasons": [
            {"reason": r, "count": n} for r, n in sorted(reasons.items(), key=lambda x: -x[1]) if n
        ],
        "declined": declined_list,
    }

    # --- sales: delivered orders -------------------------------------------
    orders = (
        db.execute(
            select(Order)
            .where(Order.status == OrderStatus.DELIVERED)
            .options(selectinload(Order.customer), selectinload(Order.lines))
        )
        .scalars()
        .all()
    )
    delivered = [
        o
        for o in orders
        if o.delivered_at is not None
        and _in(o.delivered_at.astimezone(IST).date(), date_from, date_to)
    ]

    def order_value(o: Order) -> int:
        return with_gst(sum(ln.value_paise for ln in o.lines))

    by_month: dict[str, dict[str, int]] = {}
    for o in delivered:
        assert o.delivered_at is not None
        m = by_month.setdefault(
            _month(o.delivered_at.astimezone(IST).date()), {"orders": 0, "value_paise": 0}
        )
        m["orders"] += 1
        m["value_paise"] += order_value(o)
    sales_total = sum(order_value(o) for o in delivered)
    sales = {
        "orders": len(delivered),
        "value_paise": sales_total,
        "average_paise": round(sales_total / len(delivered)) if delivered else 0,
        "by_month": [{"month": k, **v} for k, v in sorted(by_month.items())],
    }

    # --- customers: who comes back -----------------------------------------
    customers: dict[int, dict[str, Any]] = {}
    for c in chains:
        latest = c[-1]
        row = customers.setdefault(
            latest.customer_id,
            {
                "customer_id": latest.customer_id,
                "customer": latest.customer.name,
                "quotes": 0,
                "accepted": 0,
                "declined": 0,
                "quoted_value_paise": 0,
                "sales_paise": 0,
                "last_quote": c[0].quote_date,
            },
        )
        row["quotes"] += 1
        row["quoted_value_paise"] += with_gst(latest.total_paise)
        if latest.status == QuotationStatus.ACCEPTED:
            row["accepted"] += 1
        elif latest.status == QuotationStatus.DECLINED:
            row["declined"] += 1
        row["last_quote"] = max(row["last_quote"], c[0].quote_date)
    for o in delivered:
        if o.customer_id in customers:
            customers[o.customer_id]["sales_paise"] += order_value(o)
        else:
            customers[o.customer_id] = {
                "customer_id": o.customer_id,
                "customer": o.customer.name,
                "quotes": 0,
                "accepted": 0,
                "declined": 0,
                "quoted_value_paise": 0,
                "sales_paise": order_value(o),
                "last_quote": None,
            }
    customer_rows = sorted(
        customers.values(), key=lambda r: (-r["quotes"], -r["sales_paise"], r["customer"])
    )
    for r in customer_rows:
        r["rate"] = _pct(r["accepted"], r["quotes"])
        r["last_quote"] = r["last_quote"].isoformat() if r["last_quote"] else None
        r["repeat"] = r["quotes"] > 1

    # --- products: quoted vs won -------------------------------------------
    products: dict[str, dict[str, Any]] = {}
    for c in chains:
        latest = c[-1]
        for ln in latest.lines:
            if ln.kind != LineKind.PRODUCT:
                continue
            pkey = str(ln.product_id) if ln.product_id else ln.description.strip().lower()
            p = products.setdefault(
                pkey,
                {
                    "description": ln.description.split("\n", 1)[0],
                    "times_quoted": 0,
                    "qty_quoted": 0,
                    "value_quoted_paise": 0,
                    "times_won": 0,
                    "qty_won": 0,
                    "value_won_paise": 0,
                },
            )
            p["times_quoted"] += 1
            p["qty_quoted"] += ln.quantity
            p["value_quoted_paise"] += with_gst(ln.value_paise)
            if latest.status == QuotationStatus.ACCEPTED:
                p["times_won"] += 1
                p["qty_won"] += ln.quantity
                p["value_won_paise"] += with_gst(ln.value_paise)
    product_rows = sorted(
        products.values(), key=lambda p: (-p["value_quoted_paise"], p["description"])
    )
    for p in product_rows:
        p["rate"] = _pct(p["times_won"], p["times_quoted"])

    # --- discount given in negotiation -------------------------------------
    discounts: list[dict[str, Any]] = []
    for c in chains:
        latest = c[-1]
        if latest.status != QuotationStatus.ACCEPTED or len(c) < 2:
            continue
        first = with_gst(c[0].total_paise)
        final = with_gst(latest.total_paise)
        # The revised quotation the deal was won on, before its negotiations.
        revised = next(
            (v for v in reversed(c) if v.rev_no and v.rev_no == latest.rev_no and v.neg_no == 0),
            None,
        )
        discounts.append(
            {
                "id": latest.id,
                "number": latest.number,
                "original_number": latest.base_number,
                "stage_label": latest.stage_label,
                "customer": latest.customer.name,
                "rounds": latest.revision,
                "revisions": latest.rev_no,
                "negotiations": latest.neg_no,
                "revised_paise": with_gst(revised.total_paise) if revised else None,
                "first_paise": first,
                "final_paise": final,
                "discount_paise": first - final,
                "discount_pct": _pct(first - final, first),
            }
        )
    won = [c[-1] for c in chains if c[-1].status == QuotationStatus.ACCEPTED]
    first_total = sum(with_gst(c[0].total_paise) for c in chains if c[-1] in won)
    final_total = sum(with_gst(q.total_paise) for q in won)
    discount = {
        "won_quotes": len(won),
        "negotiated": len(discounts),
        "first_paise": first_total,
        "final_paise": final_total,
        "discount_paise": first_total - final_total,
        "discount_pct": _pct(first_total - final_total, first_total),
        "rows": sorted(discounts, key=lambda d: -d["discount_paise"]),
    }

    # --- time to close -------------------------------------------------------
    def days(c: list[Quotation]) -> int:
        return max((_closed_on(c[-1]) - c[0].quote_date).days, 0)

    acc_days = [days(c) for c in chains if c[-1].status == QuotationStatus.ACCEPTED]
    dec_days = [days(c) for c in chains if c[-1].status == QuotationStatus.DECLINED]
    time_to_close = {
        "accepted_avg_days": round(sum(acc_days) / len(acc_days), 1) if acc_days else None,
        "declined_avg_days": round(sum(dec_days) / len(dec_days), 1) if dec_days else None,
        "avg_rounds_to_win": (round(sum(q.revision for q in won) / len(won), 1) if won else None),
    }

    # --- pending pipeline (now, all periods) --------------------------------
    pending: list[dict[str, Any]] = []
    for c in all_chains:
        latest = c[-1]
        if latest.status != QuotationStatus.PENDING:
            continue
        age = (today - c[0].quote_date).days
        pending.append(
            {
                "id": latest.id,
                "number": latest.number,
                "customer": latest.customer.name,
                "quote_date": c[0].quote_date.isoformat(),
                "last_change": _closed_on(latest).isoformat(),
                "age_days": age,
                "rounds": latest.revision,
                "stage_label": latest.stage_label,
                "value_paise": with_gst(latest.total_paise),
                "follow_up": (today - _closed_on(latest)).days >= FOLLOW_UP_DAYS,
            }
        )
    pending.sort(key=lambda p: -p["age_days"])
    pipeline = {
        "count": len(pending),
        "value_paise": sum(p["value_paise"] for p in pending),
        "follow_up_count": sum(1 for p in pending if p["follow_up"]),
        "follow_up_days": FOLLOW_UP_DAYS,
        "rows": pending,
    }

    return {
        "from": date_from.isoformat() if date_from else None,
        "to": date_to.isoformat() if date_to else None,
        "conversion": conversion,
        "sales": sales,
        "customers": customer_rows,
        "products": product_rows,
        "discount": discount,
        "time_to_close": time_to_close,
        "pipeline": pipeline,
        "reorder": reorder_suggestions(db),
    }


# Reorder: how long a supplier usually takes, and how many days of stock to hold after it arrives.
LEAD_DAYS = 14
COVER_DAYS = 30
SALES_WINDOW_DAYS = 90


def _sums(db: Session, stmt: Any) -> dict[int, int]:
    """product id -> summed quantity, from a two-column grouped query."""
    return {int(pid): int(n or 0) for pid, n in db.execute(stmt).all()}


def reorder_suggestions(db: Session) -> dict[str, Any]:
    """What to buy now, from how fast each product actually sells.

    Speed is the last 90 days of Product Deliveries. The suggestion tops the
    stock up to cover the supplier's lead time plus a month, never below the
    low-stock level, plus anything waiting orders still need, less what is
    already on the shelf (free to sell) and already on order.
    """
    since = datetime.now(IST) - timedelta(days=SALES_WINDOW_DAYS)
    sold = _sums(
        db,
        select(StockMovement.product_id, func.sum(-StockMovement.on_hand_delta))
        .where(
            StockMovement.movement_type == MovementType.DELIVER,
            StockMovement.created_at >= since,
        )
        .group_by(StockMovement.product_id),
    )
    on_order = _sums(
        db,
        select(PurchaseOrderLine.product_id, func.sum(PurchaseOrderLine.quantity))
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
        .where(PurchaseOrder.status != PurchaseOrderStatus.RECEIVED)
        .group_by(PurchaseOrderLine.product_id),
    )
    waiting = _sums(
        db,
        select(OrderLine.product_id, func.sum(OrderLine.quantity - OrderLine.reserved))
        .join(Order, Order.id == OrderLine.order_id)
        .where(Order.status == OrderStatus.WAITING_STOCK)
        .group_by(OrderLine.product_id),
    )
    settings = db.get(AppSettings, 1)
    default_low = settings.low_stock_threshold if settings else 0
    rows = db.execute(
        select(Product, Inventory)
        .join(Inventory, Inventory.product_id == Product.id)
        .options(selectinload(Product.supplier))
        .where(Product.is_active.is_(True))
    ).all()
    out = []
    for product, inv in rows:
        sold90 = sold.get(product.id, 0)
        per_day = sold90 / SALES_WINDOW_DAYS
        low = (
            product.low_stock_threshold if product.low_stock_threshold is not None else default_low
        )
        coming = on_order.get(product.id, 0)
        needed = waiting.get(product.id, 0)
        target = max(math.ceil(per_day * (LEAD_DAYS + COVER_DAYS)), low + 1 if low else 0)
        suggest = target + needed - inv.quantity_available - coming
        if suggest <= 0:
            continue
        days_left = round(inv.quantity_available / per_day) if per_day > 0 else None
        reasons = []
        if needed:
            reasons.append(f"{needed} needed by waiting orders")
        if days_left is not None and days_left <= LEAD_DAYS:
            reasons.append(f"runs out in about {days_left} days, supplier takes ~{LEAD_DAYS}")
        elif per_day > 0:
            reasons.append(f"sells about {round(per_day * 30, 1):g} a month")
        if low and inv.quantity_on_hand <= low:
            reasons.append("at or below the low-stock level")
        out.append(
            {
                "product_id": product.id,
                "name": product.name,
                "sku": product.sku,
                "supplier": product.supplier.name if product.supplier else "",
                "available": inv.quantity_available,
                "on_order": coming,
                "sold_90_days": sold90,
                "per_month": round(per_day * 30, 1),
                "days_left": days_left,
                "suggest": suggest,
                "value_paise": suggest * product.purchase_cost,
                "reason": "; ".join(reasons) or "below the stock to hold",
                "urgent": needed > 0
                or inv.quantity_available <= 0
                or (days_left is not None and days_left <= LEAD_DAYS),
            }
        )
    out.sort(
        key=lambda r: (
            not r["urgent"],
            r["days_left"] if r["days_left"] is not None else 10**6,
            -r["suggest"],
        )
    )
    return {
        "lead_days": LEAD_DAYS,
        "cover_days": COVER_DAYS,
        "window_days": SALES_WINDOW_DAYS,
        "count": len(out),
        "value_paise": sum(r["value_paise"] for r in out),
        "rows": out,
    }
