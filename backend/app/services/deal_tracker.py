"""Deal Tracker: every quoted item followed from the first quote to delivery.

One row per item of a quote number — never per version, so a revised or
negotiated quotation is still one deal: who asked, what, the original quote
number, its latest revised quotation (R) and negotiation (N), the quoted
price, the revised price, the final price and the discount, the result and
the full version history, then the order,
the purchase order and supplier if it had to be bought in, when the goods
arrived, and when it was delivered.

Items are matched across a number's versions by position among its product
lines (the rule the negotiation table and Quote History use), and to the
order by the same position, because the order is made from the accepted
version's product lines in order.
"""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from openpyxl import Workbook  # type: ignore[import-untyped]
from openpyxl.utils import get_column_letter  # type: ignore[import-untyped]
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..constants import LineKind, OrderStatus, QuotationStatus
from ..models import Order, PurchaseOrder, PurchaseOrderLine, Quotation
from .modern_pdf import REPORT_TH, report_header, report_table_style
from .quotation_pdf import indian_rupees
from .report_brand import brand_doc, brand_pages, brand_sheet, finish_sheet
from .xlsx_safe import append_safe

IST = timezone(timedelta(hours=5, minutes=30))

STAGES = (
    "Quoted",
    "Revised quotation",
    "In negotiation",
    "Declined",
    "Waiting for stock",
    "Ready to deliver",
    "Delivered",
)


def _d(dt: datetime | None) -> date | None:
    return dt.astimezone(IST).date() if dt else None


def rows(
    db: Session,
    *,
    q: str | None = None,
    stage: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, Any]]:
    quotes = (
        db.execute(
            select(Quotation)
            .options(selectinload(Quotation.customer), selectinload(Quotation.lines))
            .order_by(
                Quotation.year.desc(),
                Quotation.seq.desc(),
                Quotation.type,
                Quotation.revision,
            )
        )
        .scalars()
        .all()
    )
    chains: dict[tuple[str, int, int], list[Quotation]] = {}
    for r in quotes:
        chains.setdefault((r.type.value, r.year, r.seq), []).append(r)

    orders = {
        o.quotation_id: o
        for o in db.execute(select(Order).options(selectinload(Order.lines))).scalars()
    }
    pos_by_order: dict[int, list[PurchaseOrder]] = {}
    for each in db.execute(
        select(PurchaseOrder).options(
            selectinload(PurchaseOrder.lines), selectinload(PurchaseOrder.supplier)
        )
    ).scalars():
        if each.order_id is not None:
            pos_by_order.setdefault(each.order_id, []).append(each)

    needle = q.strip().lower() if q else ""
    out: list[dict[str, Any]] = []
    for chain in chains.values():
        first, latest = chain[0], chain[-1]
        if date_from and first.quote_date < date_from:
            continue
        if date_to and first.quote_date > date_to:
            continue
        accepted = next((v for v in chain if v.status == QuotationStatus.ACCEPTED), None)
        final = accepted or latest
        order = orders.get(accepted.id) if accepted else None
        first_lines = [ln for ln in first.lines if ln.kind == LineKind.PRODUCT]
        final_lines = [ln for ln in final.lines if ln.kind == LineKind.PRODUCT]
        # The revised quotation the deal rests on (before its negotiations), if any.
        revised = next(
            (v for v in reversed(chain) if v.rev_no and v.rev_no == final.rev_no and v.neg_no == 0),
            None,
        )
        revised_lines = (
            [ln for ln in revised.lines if ln.kind == LineKind.PRODUCT] if revised else []
        )
        history = " → ".join(
            [
                "Original",
                *[
                    (f"R{v.rev_no}" if v.rev_no else "") + (f"N{v.neg_no}" if v.neg_no else "")
                    for v in chain[1:]
                ],
            ]
        )
        order_lines = sorted(order.lines, key=lambda ln: ln.position) if order else []
        for i, ln in enumerate(final_lines):
            quoted = first_lines[i].rate_paise if i < len(first_lines) else ln.rate_paise
            # The order lines made from this quotation line: one, or one per item
            # of a multi-item line. Older orders have no source: theirs is position.
            olines = [
                ol
                for ol in order_lines
                if (ol.source_position if ol.source_position is not None else ol.position) == i
            ]
            po: PurchaseOrder | None = None
            po_lines: list[PurchaseOrderLine] = []
            if order:
                for ol in olines:
                    for p in pos_by_order.get(order.id, []):
                        match = next((pl for pl in p.lines if pl.product_id == ol.product_id), None)
                        if match:
                            po = po or p
                            po_lines.append(match)
                            break
            bought = sum(pl.quantity for pl in po_lines)
            if final.status == QuotationStatus.DECLINED:
                where = "Declined"
            elif order is None:
                where = (
                    "In negotiation"
                    if final.neg_no
                    else "Revised quotation"
                    if final.rev_no
                    else "Quoted"
                )
            elif order.status == OrderStatus.DELIVERED:
                where = "Delivered"
            elif order.status == OrderStatus.READY:
                where = "Ready to deliver"
            else:
                where = "Waiting for stock"
            if stage and where != stage:
                continue
            supplier = po.supplier.name if po and po.supplier else ""
            if (
                needle
                and needle
                not in " ".join(
                    [first.customer.name, final.number, ln.description, supplier]
                ).lower()
            ):
                continue
            delivered = _d(order.delivered_at) if order else None
            out.append(
                {
                    "quotation_id": final.id,
                    "original_id": first.id,
                    "customer": first.customer.name,
                    "quote_no": final.base_number,
                    "final_version": final.number,
                    "revision_ref": f"{final.base_number}-R{final.rev_no}" if final.rev_no else "",
                    "negotiation_ref": final.number if final.neg_no else "",
                    "history": history,
                    "quote_date": first.quote_date,
                    "description": ln.description.split("\n", 1)[0],
                    "quantity": ln.quantity,
                    "quoted_paise": quoted,
                    "revised_paise": revised_lines[i].rate_paise
                    if i < len(revised_lines)
                    else None,
                    "final_paise": ln.rate_paise,
                    "discount_paise": (quoted - ln.rate_paise) * ln.quantity,
                    "value_paise": ln.rate_paise * ln.quantity,
                    "revisions": final.rev_no,
                    "negotiations": final.neg_no,
                    "result": {
                        QuotationStatus.ACCEPTED: "Accepted",
                        QuotationStatus.DECLINED: "Declined",
                    }.get(final.status, "Pending"),
                    "decline_reason": final.decline_reason
                    if final.status == QuotationStatus.DECLINED
                    else "",
                    "accepted_on": _d(order.created_at) if order else None,
                    "order_id": order.id if order else None,
                    "order_no": order.number if order else "",
                    "from_stock": sum(ol.quantity for ol in olines) - bought if olines else None,
                    "bought_in": bought if po_lines else None,
                    "po_id": po.id if po else None,
                    "po_no": po.number if po else "",
                    "supplier": supplier,
                    "po_date": _d(po.created_at) if po else None,
                    "po_sent": _d(po.sent_at) if po else None,
                    "goods_received": _d(po.received_at) if po else None,
                    "delivered_on": delivered,
                    "days_to_deliver": (delivered - first.quote_date).days if delivered else None,
                    "stage": where,
                }
            )
    return out


# --- downloads ---------------------------------------------------------------

COLUMNS: list[tuple[str, str, str]] = [
    # (key, heading, kind): kind is text, date, int or money
    ("customer", "Client", "text"),
    ("quote_no", "Quote no.", "text"),
    ("quote_date", "Quote date", "date"),
    ("description", "Product / description", "text"),
    ("quantity", "Qty", "int"),
    ("quoted_paise", "Quoted price", "money"),
    ("negotiations", "Negotiations", "int"),
    ("final_paise", "Final price", "money"),
    ("discount_paise", "Discount (total)", "money"),
    ("value_paise", "Value", "money"),
    ("result", "Result", "text"),
    ("decline_reason", "Decline reason", "text"),
    ("accepted_on", "Accepted on", "date"),
    ("order_no", "Order no.", "text"),
    ("from_stock", "From stock", "int"),
    ("bought_in", "Bought in", "int"),
    ("po_no", "PO no.", "text"),
    ("supplier", "Supplier", "text"),
    ("po_date", "PO date", "date"),
    ("po_sent", "PO sent", "date"),
    ("goods_received", "Goods received", "date"),
    ("delivered_on", "Delivered on", "date"),
    ("days_to_deliver", "Days, quote to delivery", "int"),
    ("stage", "Where it is now", "text"),
    # Added with revised quotations, after the existing columns.
    ("revision_ref", "Latest revision", "text"),
    ("negotiation_ref", "Negotiation", "text"),
    ("revised_paise", "Revised price", "money"),
    ("history", "Version history", "text"),
]


def to_xlsx(data: list[dict[str, Any]], *, filters: str = "") -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Deal tracker"
    head = brand_sheet(
        ws,
        "Deal Tracker",
        [
            ("Period", filters or "All"),
            ("Items", str(len(data))),
            ("Prices", "Rs., before GST"),
            ("Prepared", datetime.now(IST).strftime("%d.%m.%Y %H:%M")),
        ],
        [h for _, h, _ in COLUMNS],
    )
    for r in data:
        row: list[Any] = []
        for key, _, kind in COLUMNS:
            v = r[key]
            # Rupees and dates as real numbers and dates, so the sheet can sort and sum.
            row.append(v / 100 if kind == "money" and v is not None else v)
        append_safe(ws, row)
    for i, (key, heading, kind) in enumerate(COLUMNS, start=1):
        letter = get_column_letter(i)
        width = max(len(heading), 12 if kind != "text" else 18)
        if key in ("description", "customer", "decline_reason"):
            width = 34
        ws.column_dimensions[letter].width = width
        for cell in ws[letter][head:]:
            if kind == "money":
                cell.number_format = "#,##,##0.00"
            elif kind == "date":
                cell.number_format = "DD-MM-YYYY"
    finish_sheet(ws, head, "Deal Tracker", freeze_col="E")
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


_CELL = ParagraphStyle("dt", fontName="Helvetica", fontSize=6.5, leading=8)
_CELL_R = ParagraphStyle("dtr", parent=_CELL, alignment=2)
_HEAD = ParagraphStyle("dth", parent=_CELL, fontName="Helvetica-Bold")
_TITLE = ParagraphStyle("dtt", fontName="Helvetica-Bold", fontSize=14, leading=18)
_SUB = ParagraphStyle("dts", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey)


def _fmt(v: Any, kind: str) -> str:
    if v is None or v == "":
        return "-"
    if kind == "money":
        return indian_rupees(int(v))
    if kind == "date":
        return str(v.strftime("%d-%m-%y"))
    return str(v)


def to_pdf(data: list[dict[str, Any]], *, company: str, filters: str) -> bytes:
    buf = BytesIO()
    doc = brand_doc(
        buf,
        landscape(A3),
        8 * mm,
        title="Deal Tracker",
        author=company,
    )
    widths_mm = [
        34,
        20,
        14,
        44,
        8,
        18,
        10,
        18,
        18,
        20,
        14,
        26,
        14,
        26,
        10,
        10,
        18,
        26,
        14,
        14,
        14,
        14,
        12,
        20,
        22,
        24,
        18,
        30,
    ]
    scale = (doc.width / mm) / sum(widths_mm)
    table = [[Paragraph(escape(h), REPORT_TH) for _, h, _ in COLUMNS]]
    for r in data:
        table.append(
            [
                Paragraph(escape(_fmt(r[k], kind)), _CELL if kind in ("text", "date") else _CELL_R)
                for k, _, kind in COLUMNS
            ]
        )
    t = Table(table, colWidths=[w * scale * mm for w in widths_mm], repeatRows=1)
    t.setStyle(report_table_style(padding=2))
    made = datetime.now(IST).strftime("%d.%m.%Y %H:%M")
    doc.build(
        [
            report_header(
                "Deal Tracker",
                "Each item from the first quote to delivery.",
                [
                    ("Period", filters),
                    ("Items", str(len(data))),
                    ("Prices", "Rs., before GST"),
                    ("Prepared", made),
                ],
                doc.width,
                logo=False,
            ),
            Spacer(0, 5 * mm),
            t,
        ],
        onFirstPage=brand_pages("Deal Tracker", made),
        onLaterPages=brand_pages("Deal Tracker", made),
    )
    return buf.getvalue()
