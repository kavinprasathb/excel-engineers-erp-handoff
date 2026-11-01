"""Render a purchase order on the Excel Engineers letterhead.

The layout follows the supplier PO the client shared (TEW-PO-1): title,
number and date, the supplier addressed "To M/s", one table of items, a
sub total, SGST and CGST (half the GST rate each), the total in words, and
the signature block. The letterhead is the one on quotation format 2: the
logos at the top, the address strip at the foot of every page.
"""

from datetime import timedelta, timezone
from xml.sax.saxutils import escape as esc

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    Table,
    TableStyle,
)

from ..models import AppSettings, PurchaseOrder

IST = timezone(timedelta(hours=5, minutes=30))

_BODY = ParagraphStyle("po_body", fontName="Times-Roman", fontSize=11, leading=14.5)
_BOLD = ParagraphStyle("po_bold", parent=_BODY, fontName="Times-Bold")
_TITLE = ParagraphStyle("po_title", parent=_BOLD, fontSize=15, leading=19, alignment=TA_CENTER)
_CELL = ParagraphStyle("po_cell", parent=_BODY, fontSize=10.5, leading=13)
_CELL_C = ParagraphStyle("po_cell_c", parent=_CELL, alignment=TA_CENTER)
_CELL_R = ParagraphStyle("po_cell_r", parent=_CELL, alignment=TA_RIGHT)
_CELL_RB = ParagraphStyle("po_cell_rb", parent=_CELL_R, fontName="Times-Bold")
_HEAD = ParagraphStyle("po_head", parent=_CELL_C, fontName="Times-Bold")

_ONES = [
    "Zero",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
_TENS = [
    "_",
    "_",
    "Twenty",
    "Thirty",
    "Forty",
    "Fifty",
    "Sixty",
    "Seventy",
    "Eighty",
    "Ninety",
]


def _below_100(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + ("" if n % 10 == 0 else f" {_ONES[n % 10]}")


def _below_1000(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} Hundred")
    if rest:
        parts.append(_below_100(rest))
    return " ".join(parts)


def indian_words(rupees: int) -> str:
    """1,25,300 -> 'One Lakh Twenty Five Thousand Three Hundred' (Indian grouping)."""
    if rupees == 0:
        return "Zero"
    parts = []
    crore, rupees = divmod(rupees, 10_000_000)
    lakh, rupees = divmod(rupees, 100_000)
    thousand, rupees = divmod(rupees, 1000)
    if crore:
        parts.append(f"{indian_words(crore) if crore >= 100 else _below_100(crore)} Crore")
    if lakh:
        parts.append(f"{_below_100(lakh)} Lakh")
    if thousand:
        parts.append(f"{_below_100(thousand)} Thousand")
    if rupees:
        parts.append(_below_1000(rupees))
    return " ".join(parts)


def amount_in_words(paise: int) -> str:
    rupees, p = divmod(paise, 100)
    words = f"INR {indian_words(rupees)}"
    if p:
        words += f" and {_below_100(p)} Paise"
    return f"({words} Only)"


def money(paise: int) -> str:
    """Rs. 1,25,300.00 - Indian grouping, two decimals."""
    rupees, p = divmod(abs(paise), 100)
    s = str(rupees)
    if len(s) > 3:
        head, last3 = s[:-3], s[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + last3
    return f"Rs. {'-' if paise < 0 else ''}{s}.{p:02d}"


def _half_rate(bp: int) -> str:
    """Half of a GST rate in basis points, as printed: 1800 -> '9', 500 -> '2.5'."""
    return f"{bp / 200:g}"


def totals(po: PurchaseOrder) -> tuple[int, list[tuple[int, int]], int]:
    """Sub total, then (GST rate bp, SGST = CGST paise) per rate, then the total.

    Tax is worked out per rate on that rate's sub total and split in two
    equal halves, so SGST and CGST always match.
    """
    by_rate: dict[int, int] = {}
    for ln in po.lines:
        by_rate[ln.gst_rate_bp] = by_rate.get(ln.gst_rate_bp, 0) + ln.quantity * ln.rate_paise
    sub = sum(by_rate.values())
    halves = [(bp, round(value * bp / 20000)) for bp, value in sorted(by_rate.items())]
    return sub, halves, sub + 2 * sum(tax for _, tax in halves)


def _supplier_block(po: PurchaseOrder) -> list[str]:
    s = po.supplier
    if s is None:
        return ["M/s. ________________________"]
    lines = [f"M/s. {s.name}"]
    for part in (s.address_line1, s.address_line2):
        if part:
            lines.append(part)
    place = ", ".join(p for p in (s.city, s.state) if p)
    if s.pincode:
        place = f"{place} - {s.pincode}" if place else s.pincode
    if place:
        lines.append(place)
    if s.gstin:
        lines.append(f"GSTIN: {s.gstin}")
    return lines


def _no_pad(t: Table) -> Table:
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def _items(po: PurchaseOrder) -> Table:
    rows: list[list[Flowable]] = [
        [
            Paragraph("S No", _HEAD),
            Paragraph("Description", _HEAD),
            Paragraph("Qty", _HEAD),
            Paragraph("Rate", _HEAD),
            Paragraph("Amount", _HEAD),
        ]
    ]
    for i, ln in enumerate(po.lines, start=1):
        rows.append(
            [
                Paragraph(str(i), _CELL_C),
                Paragraph(esc(ln.description).replace("\n", "<br/>"), _CELL),
                Paragraph(str(ln.quantity), _CELL_C),
                Paragraph(money(ln.rate_paise), _CELL_R),
                Paragraph(money(ln.quantity * ln.rate_paise), _CELL_R),
            ]
        )
    sub, halves, total = totals(po)
    summary: list[tuple[str, int, bool]] = [("Sub Total", sub, False)]
    for bp, tax in halves:
        summary.append((f"SGST @ {_half_rate(bp)}%", tax, False))
        summary.append((f"CGST @ {_half_rate(bp)}%", tax, False))
    summary.append(("Total", total, True))
    first_summary = len(rows)
    for label, value, bold in summary:
        style = _CELL_RB if bold else _CELL_R
        rows.append(
            [
                Paragraph("", _CELL),
                Paragraph(label, style),
                Paragraph("", _CELL),
                Paragraph("", _CELL),
                Paragraph(money(value), style),
            ]
        )
    t = Table(rows, colWidths=[13 * mm, 84 * mm, 15 * mm, 32 * mm, 31.7 * mm], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, first_summary - 1), 0.6, colors.black),
                ("BOX", (0, first_summary), (-1, -1), 0.6, colors.black),
                ("LINEBEFORE", (4, first_summary), (4, -1), 0.6, colors.black),
                ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black),
                *[("SPAN", (1, r), (3, r)) for r in range(first_summary, len(rows))],
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def render_purchase_order_pdf(po: PurchaseOrder, settings: AppSettings) -> bytes:
    """The purchase order in the modern layout; signature space left blank."""
    from .modern_pdf import Document, Row, company_rows, render

    sup = po.supplier
    supplier_rows: list[tuple[str, str]] = [("", f"M/s. {sup.name}" if sup else "M/s. ________")]
    br = po.supplier_branch
    if sup and br is not None:
        # A named branch replaces the head office's GST number and address.
        place = ", ".join(p for p in (br.address_line1, br.city, br.state) if p)
        if br.pincode:
            place += f" - {br.pincode}"
        supplier_rows += [("Branch", br.name), ("Address", place), ("GSTIN", br.gstin)]
    elif sup:
        place = ", ".join(
            p for p in (sup.address_line1, sup.address_line2, sup.city, sup.state) if p
        )
        if sup.pincode:
            place += f" - {sup.pincode}"
        supplier_rows += [("Address", place), ("GSTIN", sup.gstin)]
    issued = po.created_at.astimezone(IST).strftime("%d %b %Y").upper()
    doc = Document(
        title="Purchase Order",
        subtitle="Please supply the following materials as per the details below.",
        meta=[("PO No", po.number), ("Date", issued)],
        by_heading="Order by",
        by_rows=company_rows(settings),
        to_heading="Supplier Details",
        to_rows=supplier_rows,
        place_of_supply=settings.company_state,
        rows=[
            Row(description=ln.description, quantity=ln.quantity, rate_paise=ln.rate_paise)
            for ln in po.lines
        ],
        gst_bp=po.lines[0].gst_rate_bp if po.lines else 1800,
        signature=False,
    )
    return render(doc, settings)
