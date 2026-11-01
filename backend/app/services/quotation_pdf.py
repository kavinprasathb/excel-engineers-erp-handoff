"""Quotations as PDFs, all in the modern layout.

Every quotation and every negotiation shares one design (see `modern_pdf`):
title and logo, the two parties, the letter's opening line, the item table,
terms beside the totals with GST and the total in words, the closing
paragraphs and the signature. An item whose technical deviation has any
filled row prints those rows directly under it; an item with none prints
nothing extra.

A negotiation (N1, N2, ...) adds the old rate beside the new one.

This module also keeps the pieces other documents share: the asset folder,
the letterhead footer drawn on every page, and Indian number grouping.
"""

import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as esc

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate

from ..constants import LineKind
from ..models import AppSettings, Quotation

ASSETS = Path(__file__).resolve().parent.parent / "assets"

_T_FOOT = ParagraphStyle(
    "t_foot",
    fontName="Helvetica",
    fontSize=8.5,
    leading=11,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#6b7280"),
)


def indian_rupees(paise: int) -> str:
    """`2,16,000` - lakh/crore grouping, whole rupees, the way the letter prints it."""
    n = round(paise / 100)
    s = str(abs(n))
    if len(s) > 3:
        head, last3 = s[:-3], s[-3:]
        parts: list[str] = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + last3
    return ("-" if n < 0 else "") + s


def _letterhead_footer(settings: AppSettings) -> Paragraph:
    """The address/GSTIN/contact strip at the foot of every letterhead page."""
    address = ", ".join(
        p
        for p in (
            settings.company_address_line1,
            settings.company_address_line2,
            settings.company_city,
        )
        if p
    )
    line1 = esc(address)
    if settings.company_pincode:
        line1 += f" &ndash; {esc(settings.company_pincode)}"
    if settings.company_gstin:
        line1 += f"  GST: {esc(settings.company_gstin)}"
    bits = []
    if settings.company_phone:
        bits.append(f"Phone: {esc(settings.company_phone)}")
    if settings.company_mobile:
        bits.append(f"Mobile No.: {esc(settings.company_mobile)}")
    if settings.company_email:
        bits.append(f"e-mail: {esc(settings.company_email)}")
    return Paragraph(f"{line1}<br/>{'  '.join(bits)}", _T_FOOT)


def letterhead_page(settings: AppSettings) -> Any:
    footer = _letterhead_footer(settings)

    def draw(canvas: Canvas, doc: SimpleDocTemplate) -> None:
        canvas.saveState()
        width = doc.pagesize[0] - doc.leftMargin - doc.rightMargin
        _, h = footer.wrap(width, 30 * mm)
        y = 6 * mm
        canvas.setLineWidth(0.5)
        canvas.setStrokeColor(colors.grey)
        canvas.line(doc.leftMargin, y + h + 2 * mm, doc.leftMargin + width, y + h + 2 * mm)
        footer.drawOn(canvas, doc.leftMargin, y)
        canvas.restoreState()

    return draw


def _offer_of(q: Quotation) -> str:
    """'Offer for RNS Coupling' is echoed as 'our offer for RNS Coupling'."""
    subject = q.subject.strip() or "Offer"
    return subject[len("offer for ") :] if subject.lower().startswith("offer for ") else subject


_CLOSING = [
    "We trust to have made our offer in line with your requirements and in case of any query, "
    "please feel free to get in touch with us.",
    "Thanking you and assuring you of our best services always, we remain.",
]


def duty_point(labels: list[tuple[str, str]], values: list[str]) -> str:
    """'25 m³/hr @ 75 m' from a pump's capacity and total head rows, if filled."""
    cap = head = ""
    for (_, label), value in zip(labels, values, strict=False):
        low = label.lower()
        if not cap and re.search(r"capacity|flow|discharge", low):
            cap = value.strip()
        elif not head and "head" in low and "shut" not in low:
            head = value.strip()
    # Non-breaking spaces: "45 m" never splits across lines in a narrow heading.
    nb = chr(0xA0)
    return f"{cap}{nb}m³/hr @ {head}{nb}m" if cap and head else ""


def render_quotation_pdf(
    q: Quotation, settings: AppSettings, changes: list[dict[str, Any]] | None = None
) -> bytes:
    from .modern_pdf import Document, Row, TechColumn, TechSheet, company_rows, render

    c = q.customer
    b = q.customer_branch
    # A named branch replaces the head office's GST number and address.
    if b is not None:
        address = ", ".join(p for p in (b.address_line1, b.city) if p)
        pincode, state, gstin = b.pincode, b.state, b.gstin
    else:
        address = ", ".join(
            p for p in (c.billing_address_line1, c.billing_address_line2, c.billing_city) if p
        )
        pincode, state, gstin = c.billing_pincode, c.billing_state, c.gstin
    if pincode:
        address += f" - {pincode}"
    old_rates = [ch.get("old_rate_paise") for ch in (changes or [])]
    labels = [(r.get("section", ""), r["label"]) for r in q.tech_rows]
    rows: list[Row] = []
    i = 0
    for line in q.lines:
        if line.kind == LineKind.NOTE:
            rows.append(Row(description=line.description, is_note=True))
            continue
        old = old_rates[i] if i < len(old_rates) else None
        i += 1
        rows.append(
            Row(
                description=line.description,
                quantity=line.quantity,
                rate_paise=line.rate_paise,
                old_rate_paise=old,
                unit=line.unit_label,
                hsn=line.hsn_code,
                deviations=[
                    (d["label"], d["value"])
                    for d in line.deviations
                    if d.get("label", "").strip() and d.get("value", "").strip()
                ],
                part_no=line.part_no,
                moc=line.moc,
                delivery=line.delivery,
                supply_scope=line.supply_scope,
                # The pump offer prints only the filled datasheet rows.
                datasheet=[
                    (sec, label, value.strip())
                    for (sec, label), value in zip(labels, line.tech_values, strict=False)
                    if value.strip()
                ],
            )
        )
    # Old rates and the saving print on a negotiation only; a revised
    # quotation is a fresh offer.
    negotiated = q.neg_no > 0 and bool(changes)
    saved = sum(
        max((r.old_rate_paise or r.rate_paise or 0) - (r.rate_paise or 0), 0) * (r.quantity or 0)
        for r in rows
        if not r.is_note
    )
    meta = [("Quotation No", q.number), ("Date", q.quote_date.strftime("%d %b %Y"))]
    if q.reference:
        meta.append(("Reference", q.reference))
    subtitle = q.subject.strip()
    if q.revision:
        subtitle = q.stage_label + (f" · {subtitle}" if subtitle else "")

    intro = [
        f"We thank you very much for the enquiry, we are submitting our offer for {_offer_of(q)}."
    ]

    doc = Document(
        title="Quotation",
        subtitle=subtitle,
        meta=meta,
        by_heading="Quotation by",
        by_rows=company_rows(settings),
        to_heading="Customer Details",
        to_rows=[
            ("", f"M/s. {c.name}"),
            *([("Branch", b.name)] if b is not None else []),
            ("Address", address),
            ("GSTIN", gstin),
            ("Contact Person", c.contact_person),
            ("Phone", c.phone),
            ("Email", c.email),
        ],
        place_of_supply=state or settings.company_state,
        rows=rows,
        discount_paise=saved if negotiated else 0,
        discount_label="Saved vs last offer",
        terms=[f"{t.label}: {t.text}" for t in q.terms if t.included],
        terms_heading="Commercial Terms & Conditions",
        show_old_rate=negotiated,
        intro=intro,
        closing=_CLOSING,
    )
    doc.layout = q.format if q.format in ("pump", "spares") else "list"
    if q.format == "pump":
        doc.items_heading = "Technical & Commercial Offer"
    elif q.format == "spares":
        doc.items_heading = "Spares & Service Details"
    doc.print_columns = list(q.print_columns)
    if q.format == "technical":
        # A data sheet, not a letter: the client's technical offers carry no
        # "We thank you..." paragraphs, only the grid, terms and scope.
        doc.intro, doc.closing = [], []
        items = [ln for ln in q.lines if ln.kind != LineKind.NOTE]
        doc.items_heading = "Technical Offer"
        doc.tech = TechSheet(
            rows=[(r.get("section", ""), r["label"]) for r in q.tech_rows],
            columns=[
                TechColumn(
                    service=ln.service,
                    model=ln.description,
                    values=list(ln.tech_values),
                    quantity=ln.quantity,
                    rate_paise=ln.rate_paise,
                    old_rate_paise=old_rates[i] if i < len(old_rates) else None,
                    duty=duty_point(labels, ln.tech_values),
                )
                for i, ln in enumerate(items)
            ],
            scope=q.scope,
            price_label=q.price_label,
        )
    return render(doc, settings)
