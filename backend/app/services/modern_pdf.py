"""The branded document layout: every quotation format, its negotiations, and
the purchase order.

Laid out after the company's quotation design: a white masthead with the
Excel Engineers and KSB marks, a blue hero with a pump drawn in line art, a
navy title band, two soft cards (customer details and the document facts), a
section bar over the item table, the totals box with a navy grand total,
terms beside a thank-you note, the signatory, and a navy footer band with the
company's address strip on every page.
"""

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape as esc

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from ..models import AppSettings
from .purchase_order_pdf import amount_in_words, money
from .quotation_pdf import ASSETS

NAVY = colors.HexColor("#0b2d6b")
BRAND = colors.HexColor("#1d5fc4")
SKY = colors.HexColor("#3f8ef0")
PANEL = colors.HexColor("#f2f6fc")
ZEBRA = colors.HexColor("#f7f9fd")
LINE = colors.HexColor("#d9e2ef")
INK = colors.HexColor("#1f2430")
INK2 = colors.HexColor("#5f6b7d")
GREEN = colors.HexColor("#16a34a")

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
WIDTH = PAGE_W - 2 * MARGIN - 12  # the frame, less its padding
FIRST_TOP = 69 * mm  # masthead + title band on page one
LATER_TOP = 18 * mm
BOTTOM = 27 * mm  # address strip + footer band

_B = ParagraphStyle("m_body", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
_BR = ParagraphStyle("m_body_r", parent=_B, alignment=TA_RIGHT)
_BC = ParagraphStyle("m_body_c", parent=_B, alignment=TA_CENTER)
_L = ParagraphStyle("m_label", parent=_B, textColor=INK2)
_BOLD = ParagraphStyle("m_bold", parent=_B, fontName="Helvetica-Bold")
_NAME = ParagraphStyle("m_name", parent=_BOLD, fontSize=10.5, leading=14)
_CARD_H = ParagraphStyle(
    "m_card_h", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=NAVY
)
_H = ParagraphStyle("m_h", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=NAVY)
_BAR = ParagraphStyle(
    "m_bar", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=colors.white
)
_TH = ParagraphStyle(
    "m_th",
    fontName="Helvetica-Bold",
    fontSize=8.8,
    leading=11,
    textColor=colors.white,
    alignment=TA_CENTER,
)
_SMALL = ParagraphStyle("m_small", parent=_B, fontSize=8.5, leading=11.5, textColor=INK)
_NOTE = ParagraphStyle("m_note", parent=_B, fontName="Helvetica-Oblique", textColor=INK2)
_TOTAL = ParagraphStyle(
    "m_total", parent=_B, fontName="Helvetica-Bold", fontSize=11, textColor=colors.white
)
_TOTAL_R = ParagraphStyle("m_total_r", parent=_TOTAL, alignment=TA_RIGHT)
_GREEN_L = ParagraphStyle("m_gl", parent=_BOLD, textColor=GREEN)
_GREEN_R = ParagraphStyle("m_gr", parent=_GREEN_L, alignment=TA_RIGHT)
_THANKS = ParagraphStyle("m_thanks", parent=_BOLD, fontSize=10.5, leading=14, textColor=NAVY)
# Report styles (Quote History, Deal Tracker, Analytics keep their own header).
_TITLE = ParagraphStyle(
    "m_title", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=BRAND
)
_SUB = ParagraphStyle("m_sub", parent=_B, fontSize=10.5, textColor=INK2)


@dataclass
class Row:
    """One line of the item table. `old_rate_paise` only on a negotiation."""

    description: str
    quantity: int | None = None
    rate_paise: int | None = None
    old_rate_paise: int | None = None
    is_note: bool = False
    unit: str = ""  # "Each", "Set": printed beside the quantity
    hsn: str = ""  # HSN/SAC code; the column appears only when a row has one
    # The item's technical deviation, printed directly under it. Only filled
    # rows are passed in; none means no panel.
    deviations: list[tuple[str, str]] = field(default_factory=list)
    # Spares layout columns; printed only when the quotation switches them on.
    part_no: str = ""
    moc: str = ""
    delivery: str = ""
    # Pump layout: the item's datasheet, (section, label, value), filled rows
    # only, and what its price includes.
    datasheet: list[tuple[str, str, str]] = field(default_factory=list)
    supply_scope: str = ""

    @property
    def amount_paise(self) -> int:
        return (self.quantity or 0) * (self.rate_paise or 0)


@dataclass
class Document:
    title: str
    subtitle: str
    meta: list[tuple[str, str]]  # ("Quotation No", "ESQP-26-4") ...
    by_heading: str
    by_rows: list[tuple[str, str]]
    to_heading: str
    to_rows: list[tuple[str, str]]
    place_of_supply: str
    rows: list[Row]
    gst_bp: int = 1800
    discount_paise: int = 0
    discount_label: str = "Discount"
    terms: list[str] = field(default_factory=list)
    terms_heading: str = "Terms and Conditions"
    notes: str = ""
    signature: bool = True
    show_old_rate: bool = False
    intro: list[str] = field(default_factory=list)
    items_heading: str = ""
    # The technical offer sheet, printed in place of the item table.
    tech: "TechSheet | None" = None
    # "pump", "spares" or "list" (the plain item table, also the purchase order's).
    layout: str = "list"
    print_columns: list[str] = field(default_factory=list)
    closing: list[str] = field(default_factory=list)


def _num(paise: int) -> str:
    """2,16,000.00: the table heading carries the currency, so cells stay on one line."""
    return money(paise).removeprefix("Rs. ")


def _rs(paise: int) -> str:
    return "Rs. " + _num(paise)


def _p(text: str, style: ParagraphStyle = _B) -> Paragraph:
    return Paragraph(esc(text).replace("\n", "<br/>"), style)


def _markup(markup: str, style: ParagraphStyle = _B) -> Paragraph:
    """Markup the caller built; any user text in it is escaped by the caller."""
    return Paragraph(markup, style)


def _tight() -> TableStyle:
    return TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]
    )


# --- small line icons, drawn rather than shipped as images ---------------------


def _glyph(c: Any, kind: str, cx: float, cy: float, r: float) -> None:
    """A simple line glyph centred on (cx, cy), roughly r in radius."""
    c.setLineWidth(max(r * 0.16, 0.6))
    c.setLineCap(1)
    c.setLineJoin(1)
    if kind == "person":
        c.circle(cx, cy + r * 0.38, r * 0.32, stroke=1, fill=0)
        p = c.beginPath()
        p.moveTo(cx - r * 0.62, cy - r * 0.62)
        p.curveTo(cx - r * 0.62, cy, cx + r * 0.62, cy, cx + r * 0.62, cy - r * 0.62)
        c.drawPath(p, stroke=1, fill=0)
    elif kind == "doc":
        c.roundRect(cx - r * 0.5, cy - r * 0.68, r, r * 1.36, r * 0.12, stroke=1, fill=0)
        for dy in (0.3, 0, -0.3):
            c.line(cx - r * 0.28, cy + r * dy, cx + r * 0.28, cy + r * dy)
    elif kind == "box":
        p = c.beginPath()
        p.moveTo(cx, cy + r * 0.7)
        p.lineTo(cx + r * 0.65, cy + r * 0.35)
        p.lineTo(cx + r * 0.65, cy - r * 0.4)
        p.lineTo(cx, cy - r * 0.75)
        p.lineTo(cx - r * 0.65, cy - r * 0.4)
        p.lineTo(cx - r * 0.65, cy + r * 0.35)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.line(cx - r * 0.65, cy + r * 0.35, cx, cy)
        c.line(cx + r * 0.65, cy + r * 0.35, cx, cy)
        c.line(cx, cy, cx, cy - r * 0.75)
    elif kind == "shield":
        p = c.beginPath()
        p.moveTo(cx, cy + r * 0.75)
        p.lineTo(cx + r * 0.6, cy + r * 0.5)
        p.curveTo(cx + r * 0.6, cy - r * 0.2, cx + r * 0.3, cy - r * 0.55, cx, cy - r * 0.78)
        p.curveTo(
            cx - r * 0.3, cy - r * 0.55, cx - r * 0.6, cy - r * 0.2, cx - r * 0.6, cy + r * 0.5
        )
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        p = c.beginPath()
        p.moveTo(cx - r * 0.25, cy)
        p.lineTo(cx - r * 0.05, cy - r * 0.2)
        p.lineTo(cx + r * 0.3, cy + r * 0.2)
        c.drawPath(p, stroke=1, fill=0)
    elif kind == "gear":
        c.circle(cx, cy, r * 0.42, stroke=1, fill=0)
        c.circle(cx, cy, r * 0.14, stroke=1, fill=0)
        import math

        for i in range(8):
            a = i * math.pi / 4
            c.line(
                cx + math.cos(a) * r * 0.48,
                cy + math.sin(a) * r * 0.48,
                cx + math.cos(a) * r * 0.72,
                cy + math.sin(a) * r * 0.72,
            )
    elif kind == "badge":
        c.circle(cx, cy + r * 0.15, r * 0.48, stroke=1, fill=0)
        p = c.beginPath()
        p.moveTo(cx - r * 0.3, cy - r * 0.25)
        p.lineTo(cx - r * 0.4, cy - r * 0.8)
        p.lineTo(cx, cy - r * 0.6)
        p.lineTo(cx + r * 0.4, cy - r * 0.8)
        p.lineTo(cx + r * 0.3, cy - r * 0.25)
        c.drawPath(p, stroke=1, fill=0)
    elif kind == "hands":
        p = c.beginPath()
        p.moveTo(cx - r * 0.8, cy + r * 0.1)
        p.lineTo(cx - r * 0.35, cy + r * 0.45)
        p.lineTo(cx + r * 0.05, cy + r * 0.2)
        p.lineTo(cx + r * 0.35, cy + r * 0.45)
        p.lineTo(cx + r * 0.8, cy + r * 0.1)
        c.drawPath(p, stroke=1, fill=0)
        p = c.beginPath()
        p.moveTo(cx - r * 0.55, cy - r * 0.05)
        p.lineTo(cx - r * 0.1, cy - r * 0.5)
        p.lineTo(cx + r * 0.2, cy - r * 0.25)
        p.lineTo(cx + r * 0.55, cy - r * 0.05)
        c.drawPath(p, stroke=1, fill=0)


class _Badge(Flowable):
    """A navy disc holding a white line glyph, for card and section headings."""

    def __init__(self, kind: str, size: float = 7.5 * mm) -> None:
        super().__init__()
        self.kind, self.size = kind, size
        self.width = self.height = size

    def draw(self) -> None:
        c = self.canv
        r = self.size / 2
        c.setFillColor(NAVY)
        c.circle(r, r, r, stroke=0, fill=1)
        c.setStrokeColor(colors.white)
        _glyph(c, self.kind, r, r, r * 0.55)


def _titled(kind: str, text: str, width: float) -> Table:
    t = Table([[_Badge(kind), Paragraph(esc(text), _CARD_H)]], colWidths=[10 * mm, width - 10 * mm])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def _card(content: list[Flowable], width: float) -> Table:
    box = Table([[content]], colWidths=[width])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("ROUNDEDCORNERS", [7, 7, 7, 7]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )
    return box


def _cards(doc: Document) -> Table:
    """Customer (or supplier) on the left, the document's facts on the right."""
    left_w = WIDTH * 0.52
    right_w = WIDTH - left_w - 5 * mm
    inner = left_w - 10 * mm
    who: list[Flowable] = [_titled("person", f"{doc.to_heading}", inner), Spacer(0, 2.5 * mm)]
    rows = [r for r in doc.to_rows if r[1]]
    if rows:
        who.append(Paragraph(esc(rows[0][1]), _NAME))
    detail = [[_p(k, _L), _p(v)] for k, v in rows[1:]]
    if detail:
        t = Table(detail, colWidths=[29 * mm, inner - 29 * mm], hAlign="LEFT")
        t.setStyle(_tight())
        who += [Spacer(0, 1.5 * mm), t]

    facts = list(doc.meta)
    if doc.place_of_supply:
        facts.append(("Place of supply", doc.place_of_supply))
    inner_r = right_w - 10 * mm
    ft = Table(
        [[_p(k, _L), _p(":", _L), _p(v, _BOLD)] for k, v in facts],
        colWidths=[30 * mm, 4 * mm, inner_r - 34 * mm],
        hAlign="LEFT",
    )
    ft.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
            ]
        )
    )
    facts_box: list[Flowable] = [
        _titled("doc", f"{doc.title} details", inner_r),
        Spacer(0, 2.5 * mm),
        ft,
    ]

    t = Table(
        [[_card(who, left_w), "", _card(facts_box, right_w)]],
        colWidths=[left_w, 5 * mm, right_w],
    )
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


def _deviation(rows: list[tuple[str, str]], width: float) -> Table:
    """An item's technical deviation: a soft panel of label : value rows, two per line."""
    cells = [[_p(k, _L), _p(v, _BOLD)] for k, v in rows]
    body = []
    for i in range(0, len(cells), 2):
        body.append(cells[i] + (cells[i + 1] if i + 1 < len(cells) else [_p(""), _p("")]))
    half = width / 2
    head: list[Flowable | str] = [_p("Technical Deviation", _BOLD), "", "", ""]
    t = Table([head, *body], colWidths=[half * 0.42, half * 0.58, half * 0.42, half * 0.58])
    t.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (-1, 0)),
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("TOPPADDING", (0, 0), (-1, 0), 2.5 * mm),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 2.5 * mm),
            ]
        )
    )
    return t


class _SectionBar(Flowable):
    """The navy-to-blue bar with a glyph that heads the item table."""

    def __init__(self, text: str, width: float, height: float = 9.5 * mm) -> None:
        super().__init__()
        self.text, self.width, self.height = text, width, height

    def draw(self) -> None:
        c = self.canv
        w, h = self.width, self.height
        c.saveState()
        p = c.beginPath()
        p.roundRect(0, 0, w, h, 2.2 * mm)
        c.clipPath(p, stroke=0, fill=0)
        c.linearGradient(0, 0, w, 0, (NAVY, BRAND), extend=True)
        c.restoreState()
        c.setStrokeColor(colors.white)
        _glyph(c, "box", 6 * mm, h / 2, 2.4 * mm)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(12 * mm, h / 2 - 3.6, self.text.upper())


@dataclass
class TechColumn:
    """One item of the technical sheet: its heading, model and row values."""

    service: str
    model: str
    values: list[str]
    quantity: int
    rate_paise: int
    old_rate_paise: int | None = None
    # "25 m³/hr @ 75 m", under the heading, from the capacity and head rows.
    duty: str = ""


@dataclass
class TechSheet:
    rows: list[tuple[str, str]]  # (section, label), in order
    columns: list[TechColumn]
    scope: str = ""
    # What the price covers: "Pump with accessories (without motor)".
    price_label: str = ""


# Pumps side by side per table; more continue in a second table that repeats
# the row labels. Six keep a model name readable on portrait A4, so an
# 11-pump enquiry is two tables, about two pages, like the client's sheets.
TECH_PER_TABLE = 6
_TL = ParagraphStyle("m_tl", parent=_SMALL, textColor=INK)
_TV = ParagraphStyle("m_tv", parent=_SMALL, alignment=TA_CENTER)
_TS = ParagraphStyle("m_ts", parent=_SMALL, fontName="Helvetica-Bold", textColor=NAVY)
_TDUTY = ParagraphStyle(
    "m_tduty",
    parent=_TH,
    fontName="Helvetica",
    fontSize=7.5,
    leading=9.5,
    textColor=colors.HexColor("#c9d8f2"),
)


def _tech(sheet: TechSheet, show_old_rate: bool) -> list[Flowable]:
    """The sheet as tables of up to five columns, each repeating the row labels.

    Rows run in the order given; a row whose section differs from the one
    above starts with a section heading row. Price rows close every table.
    """
    out: list[Flowable] = []
    label_w = 46 * mm
    for start in range(0, len(sheet.columns), TECH_PER_TABLE):
        cols = sheet.columns[start : start + TECH_PER_TABLE]
        col_w = (WIDTH - label_w) / len(cols)
        data: list[list[Any]] = [
            [_p("Parameter", _TH)]
            + [
                [
                    _p(c.service or f"Pump {start + i + 1}", _TH),
                    *([_p(c.duty, _TDUTY)] if c.duty else []),
                ]
                for i, c in enumerate(cols)
            ],
            [_p("Pump Model", _TL)] + [_p(c.model, _TV) for c in cols],
        ]
        style: list[Any] = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        section = ""
        for r, (sec, label) in enumerate(sheet.rows):
            values = [(c.values[r] if r < len(c.values) else "").strip() for c in cols]
            # A row empty for every pump on this table says nothing: skip it.
            if not any(values):
                continue
            if sec and sec != section:
                section = sec
                data.append([_p(sec, _TS)] + [""] * len(cols))
                n = len(data) - 1
                style += [("SPAN", (0, n), (-1, n)), ("BACKGROUND", (0, n), (-1, n), PANEL)]
            n = len(data)
            if len(cols) > 1 and len(set(values)) == 1:
                # The same for every pump ("Water", "2940", "SS410"): once, across.
                data.append([_p(label, _TL), _p(values[0], _TV)] + [""] * (len(cols) - 1))
                style.append(("SPAN", (1, n), (-1, n)))
            else:
                data.append([_p(label, _TL)] + [_p(v, _TV) for v in values])
        price_from = len(data)
        data.append([_p("Qty", _TL)] + [_p(str(c.quantity), _TV) for c in cols])
        if show_old_rate:
            data.append(
                [_p("Old Unit Price (Rs.)", _TL)]
                + [
                    _p(_num(c.old_rate_paise) if c.old_rate_paise is not None else "", _TV)
                    for c in cols
                ]
            )
        label = (
            f"{sheet.price_label} · Unit Price (Rs.)" if sheet.price_label else "Unit Price (Rs.)"
        )
        data.append([_p(label, _BOLD)] + [_p(_num(c.rate_paise), _TV) for c in cols])
        data.append(
            [_p("Total Price (Rs.)", _BOLD)]
            + [_markup(f"<b>{_num(c.rate_paise * c.quantity)}</b>", _TV) for c in cols]
        )
        style.append(("BACKGROUND", (0, price_from), (-1, -1), ZEBRA))
        t = Table(data, colWidths=[label_w] + [col_w] * len(cols), repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle(style))
        out += [t, Spacer(0, 4 * mm)]
    if sheet.scope:
        scope = f"<b>Scope:</b> {esc(sheet.scope)}".replace("\n", "<br/>")
        out += [_markup(scope), Spacer(0, 2 * mm)]
    return out


def _body(doc: Document) -> list[Flowable]:
    """The item section in the quotation's layout."""
    if doc.tech is not None:
        return _tech(doc.tech, doc.show_old_rate)
    if doc.layout == "pump":
        return _pump_items(doc)
    if doc.layout == "spares":
        return _spares_items(doc)
    return [_items(doc)]


_KV_L = ParagraphStyle("m_kvl", parent=_SMALL, textColor=INK2)
_KV_V = ParagraphStyle("m_kvv", parent=_SMALL, fontName="Helvetica-Bold", textColor=INK)
_ITEM_H = ParagraphStyle(
    "m_item_h", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=colors.white
)
_ITEM_HR = ParagraphStyle("m_item_hr", parent=_ITEM_H, alignment=TA_RIGHT, fontName="Helvetica")
_PRICE_L = ParagraphStyle("m_price_l", parent=_SMALL, textColor=INK2, alignment=TA_RIGHT)
_PRICE_V = ParagraphStyle("m_price_v", parent=_BOLD, alignment=TA_RIGHT)
_PRICE_T = ParagraphStyle(
    "m_price_t", parent=_BOLD, alignment=TA_RIGHT, textColor=colors.white, fontSize=10.5
)


def _pump_items(doc: Document) -> list[Flowable]:
    """Pump offer: per pump a titled card with its datasheet, scope and price.

    The datasheet runs in two label/value pairs per row to keep a pump on a
    third of a page; a section heading spans the card. The price box sits
    beside the scope of supply, as in the client's letters ("Scope of supply
    and Price ... Rs. X/- Each Set"). Notes print between pumps as text.
    """
    out: list[Flowable] = []
    n = 0
    for r in doc.rows:
        if r.is_note:
            out += [_p(r.description, _NOTE), Spacer(0, 2 * mm)]
            continue
        n += 1
        model, _, rest = r.description.partition("\n")
        head = Table(
            [
                [
                    _markup(f"Item {n} &nbsp;·&nbsp; {esc(model)}", _ITEM_H),
                    _p(f"{r.quantity or ''} {r.unit}".strip(), _ITEM_HR),
                ]
            ],
            colWidths=[WIDTH * 0.75, WIDTH * 0.25],
        )
        head.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        block: list[Flowable] = [head]
        if rest.strip():
            block.append(_boxed([[_p(rest.strip(), _SMALL)]], [WIDTH]))
        if r.datasheet:
            rows: list[list[Any]] = []
            style: list[Any] = []
            section = ""
            pair: list[Any] = []
            for sec, label, value in r.datasheet:
                if sec and sec != section:
                    if pair:
                        rows.append(pair + [""] * (4 - len(pair)))
                        pair = []
                    section = sec
                    rows.append([_p(sec, _TS), "", "", ""])
                    i = len(rows) - 1
                    style += [("SPAN", (0, i), (-1, i)), ("BACKGROUND", (0, i), (-1, i), PANEL)]
                pair += [_p(label, _KV_L), _p(value, _KV_V)]
                if len(pair) == 4:
                    rows.append(pair)
                    pair = []
            if pair:
                rows.append(pair + [""] * (4 - len(pair)))
            w = WIDTH / 2
            ds = Table(rows, colWidths=[w * 0.45, w * 0.55, w * 0.45, w * 0.55])
            ds.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                        ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
                        ("LINEAFTER", (1, 0), (1, -1), 0.4, LINE),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        *style,
                    ]
                )
            )
            block.append(ds)
        # Scope of supply beside the price box.
        price_rows: list[list[Any]] = []
        if doc.show_old_rate and r.old_rate_paise is not None:
            price_rows.append(
                [_p("Old Rate (Rs.)", _PRICE_L), _p(_num(r.old_rate_paise), _PRICE_L)]
            )
        price_rows += [
            [_p("Unit price (Rs.)", _PRICE_L), _p(_num(r.rate_paise or 0), _PRICE_V)],
            [_p("Quantity", _PRICE_L), _p(f"{r.quantity or 0} {r.unit}".strip(), _PRICE_V)],
            [_p("Total (Rs.)", _PRICE_T), _p(_num(r.amount_paise), _PRICE_T)],
        ]
        pw = 62 * mm
        price = Table(price_rows, colWidths=[pw * 0.5, pw * 0.5])
        price.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, -1), (-1, -1), NAVY),
                    ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        scope = [
            _p("Scope of supply", _TS),
            Spacer(0, 1.5 * mm),
            _p(
                r.supply_scope or "As described above.",
                _SMALL,
            ),
        ]
        sp = Table([[scope, price]], colWidths=[WIDTH - pw - 4 * mm, pw + 4 * mm])
        sp.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (0, 0), 0.6, LINE),
                    ("BACKGROUND", (0, 0), (0, 0), ZEBRA),
                    ("LEFTPADDING", (0, 0), (0, 0), 8),
                    ("TOPPADDING", (0, 0), (0, 0), 6),
                    ("RIGHTPADDING", (1, 0), (1, 0), 0),
                    ("LEFTPADDING", (1, 0), (1, 0), 4 * mm),
                    ("TOPPADDING", (1, 0), (1, 0), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        block += [Spacer(0, 2 * mm), sp]
        if r.deviations:
            block += [Spacer(0, 2 * mm), _deviation(r.deviations, WIDTH - 12)]
        out += [KeepTogether(block), Spacer(0, 6 * mm)]
    return out


def _boxed(rows: list[list[Any]], widths: list[float]) -> Table:
    t = Table(rows, colWidths=widths)
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _spares_items(doc: Document) -> list[Flowable]:
    """Spares & service: one table, a heading row per pump model (a note line),
    the switched-on columns, and a subtotal per group when there are several."""
    cols = set(doc.print_columns)
    hsn = any(r.hsn for r in doc.rows if not r.is_note)
    spec: list[tuple[str, str, float]] = [("sl", "Sl.", 9), ("desc", "Description", 58)]
    if "part_no" in cols:
        spec.append(("part_no", "Part No", 17))
    if "moc" in cols:
        spec.append(("moc", "MOC", 19))
    if hsn:
        spec.append(("hsn", "HSN", 17))
    spec.append(("qty", "Qty", 12))
    if "unit" in cols:
        spec.append(("unit", "Unit", 12))
    if doc.show_old_rate:
        spec.append(("old", "Old Rate (Rs.)", 21))
    spec += [("rate", "Unit Rate (Rs.)", 22), ("total", "Total (Rs.)", 24)]
    if "delivery" in cols:
        spec.append(("delivery", "Delivery", 20))
    scale = WIDTH / sum(w for _, _, w in spec)
    widths = [w * scale for _, _, w in spec]
    keys = [k for k, _, _ in spec]
    ncol = len(spec)

    groups: list[tuple[str, list[Row]]] = []
    for r in doc.rows:
        if r.is_note:
            groups.append((r.description, []))
        else:
            if not groups:
                groups.append(("", []))
            groups[-1][1].append(r)
    groups = [g for g in groups if g[0] or g[1]]
    priced_groups = sum(1 for _, rows in groups if rows)

    data: list[list[Any]] = [[_p(h, _TH) for _, h, _ in spec]]
    style: list[Any] = []
    old_style = ParagraphStyle("old_s", parent=_BR, textColor=INK2)
    for heading, rows in groups:
        if heading:
            data.append([_p(heading, _TS)] + [""] * (ncol - 1))
            i = len(data) - 1
            style += [("SPAN", (0, i), (-1, i)), ("BACKGROUND", (0, i), (-1, i), PANEL)]
        sub = 0
        for n, r in enumerate(rows, start=1):
            unit = "" if "unit" in cols else f" {r.unit}"
            cell = {
                "sl": _p(str(n), _BC),
                "desc": _p(r.description),
                "part_no": _p(r.part_no, _BC),
                "moc": _p(r.moc, _BC),
                "hsn": _p(r.hsn, _BC),
                "qty": _p(f"{r.quantity or ''}{unit}".strip(), _BC),
                "unit": _p(r.unit, _BC),
                "old": _p(
                    _num(r.old_rate_paise) if r.old_rate_paise is not None else "new", old_style
                ),
                "rate": _p(_num(r.rate_paise or 0), _BR),
                "total": _p(_num(r.amount_paise), _BR),
                "delivery": _p(r.delivery, _BC),
            }
            data.append([cell[k] for k in keys])
            sub += r.amount_paise
            if r.deviations:
                i = len(data)
                data.append(
                    [_p(""), _deviation(r.deviations, sum(widths[1:]) - 12)] + [""] * (ncol - 2)
                )
                style += [("SPAN", (1, i), (-1, i)), ("BACKGROUND", (0, i), (-1, i), colors.white)]
        if rows and priced_groups > 1:
            label = f"Subtotal · {heading}" if heading else "Subtotal"
            data.append([_p(label, _BOLD)] + [""] * (ncol - 2) + [_p(_num(sub), _PRICE_V)])
            i = len(data) - 1
            style += [
                ("SPAN", (0, i), (-2, i)),
                ("BACKGROUND", (0, i), (-1, i), ZEBRA),
                ("LINEABOVE", (0, i), (-1, i), 0.8, NAVY),
            ]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                *style,
            ]
        )
    )
    return [t]


def _items(doc: Document) -> Table:
    if doc.show_old_rate:
        head = [
            "Sl. No.",
            "Product / Item",
            "Quantity",
            "Old Rate (Rs.)",
            "New Rate (Rs.)",
            "Amount (Rs.)",
        ]
        widths = [15, 60, 20, 29, 29, 31]
    else:
        head = ["Sl. No.", "Product / Item", "Quantity", "Unit Price (Rs.)", "Amount (Rs.)"]
        widths = [16, 85, 22, 30, 31]
    hsn = any(r.hsn for r in doc.rows if not r.is_note)
    if hsn:
        head.insert(2, "HSN/SAC")
        widths[1] -= 21
        widths.insert(2, 21)
    scale = WIDTH / (sum(widths) * mm)
    col = [w * mm * scale for w in widths]
    data: list[list[Flowable | str]] = [[Paragraph(h, _TH) for h in head]]
    styles: list[Any] = []
    n = 0
    for r in doc.rows:
        row_index = len(data)
        if r.is_note:
            note_row: list[Flowable | str] = [_p(""), _p(r.description, _NOTE)]
            data.append(note_row + [""] * (len(head) - 2))
            styles.append(("SPAN", (1, row_index), (-1, row_index)))
            continue
        n += 1
        cells: list[Flowable | str] = [
            _p(str(n), _BC),
            _p(r.description),
            *([_p(r.hsn, _BC)] if hsn else []),
            _p(f"{r.quantity or ''} {r.unit}".strip(), _BC),
        ]
        if doc.show_old_rate:
            old = _num(r.old_rate_paise) if r.old_rate_paise is not None else "new"
            cells.append(_p(old, ParagraphStyle("old", parent=_BR, textColor=INK2)))
        cells += [_p(_num(r.rate_paise or 0), _BR), _p(_num(r.amount_paise), _BR)]
        data.append(cells)
        if r.deviations:
            # Under the item it belongs to: the panel spans every column but Sl. No.
            dev_index = len(data)
            panel = _deviation(r.deviations, sum(col[1:]) - 12)
            data.append([_p(""), panel] + [""] * (len(head) - 2))
            styles += [
                ("SPAN", (1, dev_index), (-1, dev_index)),
                ("BACKGROUND", (0, dev_index), (-1, dev_index), colors.white),
            ]
    t = Table(data, colWidths=col, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("LINEAFTER", (0, 0), (-2, 0), 0.4, colors.HexColor("#4f86d6")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                *styles,
            ]
        )
    )
    return t


def totals(doc: Document) -> tuple[int, int, int, int]:
    """(sub total, SGST = CGST each, total after discount and tax, taxable)."""
    sub = sum(r.amount_paise for r in doc.rows if not r.is_note)
    taxable = sub - doc.discount_paise if doc.discount_paise and not doc.show_old_rate else sub
    half = round(taxable * doc.gst_bp / 20000)
    return sub, half, taxable + 2 * half, taxable


def _summary(doc: Document) -> list[Flowable]:
    """The totals box: bordered rows, the grand total on navy, the amount in words."""
    sub, half, total, _ = totals(doc)
    rows: list[list[Flowable | str]] = [[_p("Sub Total", _BOLD), _p(_rs(sub), _BR)]]
    if doc.discount_paise:
        # On a negotiation the saving is shown, not subtracted: the new rates already carry it.
        sign = "" if doc.show_old_rate else "- "
        rows.append(
            [_p(doc.discount_label, _GREEN_L), _p(f"{sign}{_rs(doc.discount_paise)}", _GREEN_R)]
        )
    pct = f"{doc.gst_bp / 200:g}"
    rows += [
        [_p(f"SGST @ {pct}%", _BOLD), _p(_rs(half), _BR)],
        [_p(f"CGST @ {pct}%", _BOLD), _p(_rs(half), _BR)],
        [_p("Grand Total", _TOTAL), _p(_rs(total), _TOTAL_R)],
    ]
    w = 86 * mm
    t = Table(rows, colWidths=[w * 0.5, w * 0.5], hAlign="RIGHT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -2), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), NAVY),
                ("ROWBACKGROUNDS", (0, 0), (-1, -2), [colors.white, PANEL]),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -2), 0.4, LINE),
                ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, -1), (-1, -1), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )
    words = Paragraph(
        f'<font color="#5f6b7d">Amount in words:</font> {esc(amount_in_words(total).strip("()"))}',
        ParagraphStyle("m_words", parent=_SMALL, alignment=TA_RIGHT),
    )
    words_box = Table([[words]], colWidths=[WIDTH], hAlign="RIGHT")
    words_box.setStyle(_tight())
    return [t, Spacer(0, 1.5 * mm), words_box]


def _terms_block(doc: Document, width: float) -> list[Flowable]:
    out: list[Flowable] = []
    if doc.terms:
        out += [_titled("doc", doc.terms_heading, width), Spacer(0, 2.5 * mm)]
        rows = [[_p(f"{i}.", _SMALL), _p(t, _SMALL)] for i, t in enumerate(doc.terms, start=1)]
        t = Table(rows, colWidths=[6 * mm, width - 6 * mm], hAlign="LEFT")
        t.setStyle(_tight())
        out.append(t)
    if doc.notes:
        out += [
            Spacer(0, 4 * mm),
            Paragraph("Additional Notes", _H),
            Spacer(0, 2 * mm),
            _p(doc.notes, _SMALL),
        ]
    return out


def _thanks(settings: AppSettings) -> list[Flowable]:
    name = esc(settings.company_name or "Excel Engineers")
    return [
        Paragraph(f"Thank you for your interest in {name}.", _THANKS),
        Spacer(0, 2 * mm),
        Paragraph("We look forward to the opportunity to serve you.", _L),
    ]


# Beyond this many terms the side-by-side block could outgrow a page (a table
# row cannot split), so the terms flow full width instead.
SIDE_BY_SIDE_TERMS = 8


def _closing(doc: Document, settings: AppSettings) -> list[Flowable]:
    out: list[Flowable] = [KeepTogether(_summary(doc)), Spacer(0, 7 * mm)]
    left_w = WIDTH - 68 * mm
    side = len(doc.terms) <= SIDE_BY_SIDE_TERMS and len(doc.notes) < 600
    terms = _terms_block(doc, left_w if side else WIDTH)
    if side:
        t = Table([[terms or [Spacer(0, 1)], _thanks(settings)]], colWidths=[left_w, 68 * mm])
        t.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 6 * mm),
                    ("LEFTPADDING", (1, 0), (1, 0), 6 * mm),
                    ("RIGHTPADDING", (1, 0), (1, 0), 0),
                    ("LINEBEFORE", (1, 0), (1, 0), 0.8, LINE),
                    ("TOPPADDING", (1, 0), (1, 0), 6 * mm),
                ]
            )
        )
        out.append(KeepTogether([t]))
    else:
        out += [*terms, Spacer(0, 5 * mm), *_thanks(settings)]
    return out


def _signatory(doc: Document, settings: AppSettings) -> Table:
    company = esc(settings.company_name or "Excel Engineers")
    sign: list[Flowable] = [Paragraph(f"For {company}", _H), Spacer(0, 2 * mm)]
    if doc.signature:
        stamp = Image(str(ASSETS / "stamp-signature.jpg"), width=44 * mm, height=13.3 * mm)
        stamp.hAlign = "LEFT"
        sign.append(stamp)
    else:
        sign.append(Spacer(0, 14 * mm))
    who = esc(settings.signatory_name or "")
    sign.append(
        Paragraph(
            (f"{who}<br/>" if who else "") + "Authorized Signatory",
            ParagraphStyle("m_sig", parent=_SMALL, textColor=INK2),
        )
    )
    t = Table([[sign]], colWidths=[70 * mm], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -1), 0, colors.white),
            ]
        )
    )
    return t


def company_rows(settings: AppSettings) -> list[tuple[str, str]]:
    address = ", ".join(
        p
        for p in (
            settings.company_address_line1,
            settings.company_address_line2,
            settings.company_city,
        )
        if p
    )
    if settings.company_pincode:
        address += f" - {settings.company_pincode}"
    return [
        ("", settings.company_name or "Excel Engineers"),
        ("Address", address),
        ("GSTIN", settings.company_gstin),
        ("Phone", settings.company_mobile or settings.company_phone),
    ]


# --- the page furniture: masthead, title band, footer band --------------------

FOOTER_POINTS = [
    ("badge", "KSB Genuine Products", "& Support"),
    ("shield", "Reliable", "After-Sales Service"),
    ("gear", "Expert Technical", "Consultation"),
    ("hands", "Your Trusted Partner", "in Fluid Solutions"),
]


def _poly(c: Any, pts: list[tuple[float, float]], fill: Any) -> None:
    p = c.beginPath()
    p.moveTo(*pts[0])
    for x, y in pts[1:]:
        p.lineTo(x, y)
    p.close()
    c.setFillColor(fill)
    c.drawPath(p, stroke=0, fill=1)


def _masthead(c: Any, doc: Document) -> None:
    top = PAGE_H
    # Hero: blue gradient wedge with the pump, top right.
    c.saveState()
    p = c.beginPath()
    p.moveTo(126 * mm, top)
    p.lineTo(PAGE_W, top)
    p.lineTo(PAGE_W, top - 64 * mm)
    p.lineTo(150 * mm, top - 64 * mm)
    p.close()
    c.clipPath(p, stroke=0, fill=0)
    c.linearGradient(126 * mm, top, PAGE_W, top - 64 * mm, (SKY, BRAND, NAVY), extend=True)
    c.setStrokeColor(colors.HexColor("#ffffff"))
    c.setStrokeAlpha(0.07)
    for i in range(0, 90, 6):
        c.line(126 * mm + i * mm, top, 126 * mm + i * mm, top - 64 * mm)
    c.setStrokeAlpha(1)
    c.restoreState()

    # Marks: Excel Engineers, a rule, KSB authorised dealer.
    # The company logo (E, speed lines, name and tagline), 611 x 128.
    logo_w = 62 * mm
    c.drawImage(
        str(ASSETS / "logo-excel.png"),
        MARGIN,
        top - 27.5 * mm,
        width=logo_w,
        height=logo_w * 128 / 611,
        mask="auto",
    )
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(MARGIN, top - 32.5 * mm, "ENGINEERING   |   SOLUTIONS   |   SUSTAINABILITY")
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.line(84 * mm, top - 12 * mm, 84 * mm, top - 35 * mm)
    c.drawImage(
        str(ASSETS / "logo-ksb.jpg"),
        90 * mm,
        top - 26 * mm,
        width=26 * mm,
        height=11.5 * mm,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(90 * mm, top - 31.5 * mm, "AUTHORIZED DEALER")

    # Title band.
    _poly(
        c,
        [
            (0, top - 42 * mm),
            (148 * mm, top - 42 * mm),
            (136 * mm, top - 64 * mm),
            (0, top - 64 * mm),
        ],
        NAVY,
    )
    _poly(
        c,
        [
            (150 * mm, top - 42 * mm),
            (156 * mm, top - 42 * mm),
            (144 * mm, top - 64 * mm),
            (138 * mm, top - 64 * mm),
        ],
        SKY,
    )
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(MARGIN, top - 54 * mm, doc.title.upper())
    sub = doc.subtitle or "Reliable Solutions for a Better Tomorrow"
    c.setFont("Helvetica", 9.5)
    while c.stringWidth(sub, "Helvetica", 9.5) > 112 * mm and len(sub) > 4:
        sub = sub[:-2].rstrip() + "…"
    c.setFillColor(colors.HexColor("#d6e4ff"))
    c.drawString(MARGIN, top - 60.5 * mm, sub)


def _address_strip(settings: AppSettings) -> Paragraph:
    bits = []
    address = ", ".join(
        p
        for p in (
            settings.company_address_line1,
            settings.company_address_line2,
            settings.company_city,
        )
        if p
    )
    if settings.company_pincode:
        address += f" - {settings.company_pincode}"
    if address:
        bits.append(esc(address))
    if settings.company_gstin:
        bits.append(f"GSTIN: {esc(settings.company_gstin)}")
    phone = settings.company_mobile or settings.company_phone
    if phone:
        bits.append(f"Phone: {esc(phone)}")
    if settings.company_email:
        bits.append(esc(settings.company_email))
    return Paragraph(
        "  ·  ".join(bits),
        ParagraphStyle(
            "m_strip",
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=INK2,
            alignment=TA_CENTER,
        ),
    )


def _footer_band(c: Any, settings: AppSettings) -> None:
    strip = _address_strip(settings)
    w = PAGE_W - 2 * MARGIN
    _, h = strip.wrap(w, 20 * mm)
    strip.drawOn(c, MARGIN, 18 * mm)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, 18 * mm + h + 1.5 * mm, PAGE_W - MARGIN, 18 * mm + h + 1.5 * mm)

    band = 15 * mm
    _poly(c, [(0, 0), (PAGE_W, 0), (PAGE_W, band), (0, band)], colors.HexColor("#e8f0fb"))
    _poly(c, [(0, 0), (146 * mm, 0), (156 * mm, band), (0, band)], NAVY)
    _poly(c, [(146 * mm, 0), (150 * mm, 0), (160 * mm, band), (156 * mm, band)], SKY)
    x = 8 * mm
    for i, (kind, a, b) in enumerate(FOOTER_POINTS):
        c.setStrokeColor(colors.white)
        _glyph(c, kind, x + 4 * mm, band / 2, 2.6 * mm)
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 6.8)
        c.drawString(x + 9 * mm, band / 2 + 0.8 * mm, a)
        c.drawString(x + 9 * mm, band / 2 - 2.6 * mm, b)
        if i < len(FOOTER_POINTS) - 1:
            c.setStrokeColor(colors.HexColor("#3a5a94"))
            c.setLineWidth(0.5)
            c.line(x + 34 * mm, 3.5 * mm, x + 34 * mm, band - 3.5 * mm)
        x += 35 * mm
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(164 * mm, 8.6 * mm, (settings.company_name or "Excel Engineers")[:24])
    c.setFillColor(BRAND)
    c.setFont("Helvetica", 7.5)
    c.drawString(164 * mm, 4.4 * mm, "Authorized Dealer - KSB")


def render(doc: Document, settings: AppSettings) -> bytes:
    buf = BytesIO()
    ref = doc.meta[0][1] if doc.meta else doc.title
    pdf = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=LATER_TOP,
        bottomMargin=BOTTOM,
        title=ref,
        author=settings.company_name,
    )
    frame_w = PAGE_W - 2 * MARGIN

    def first(c: Any, d: Any) -> None:
        c.saveState()
        _masthead(c, doc)
        _footer_band(c, settings)
        c.restoreState()

    def later(c: Any, d: Any) -> None:
        """Continuation pages: a slim navy bar naming the document and the page."""
        c.saveState()
        _poly(
            c,
            [(0, PAGE_H - 11 * mm), (PAGE_W, PAGE_H - 11 * mm), (PAGE_W, PAGE_H), (0, PAGE_H)],
            NAVY,
        )
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(MARGIN, PAGE_H - 7 * mm, doc.title.upper())
        c.setFont("Helvetica", 8.5)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 7 * mm, f"{ref} · Page {d.page}")
        _footer_band(c, settings)
        c.restoreState()

    pdf.addPageTemplates(
        [
            PageTemplate(
                id="first",
                frames=[Frame(MARGIN, BOTTOM, frame_w, PAGE_H - FIRST_TOP - BOTTOM, id="f1")],
                onPage=first,
            ),
            PageTemplate(
                id="later",
                frames=[Frame(MARGIN, BOTTOM, frame_w, PAGE_H - LATER_TOP - BOTTOM, id="f2")],
                onPage=later,
            ),
        ]
    )
    story: list[Flowable] = [NextPageTemplate("later"), _cards(doc)]
    for text in doc.intro:
        story += [Spacer(0, 4 * mm), _p(text)]
    story += [
        Spacer(0, 6 * mm),
        _SectionBar(doc.items_heading or "Product / Item Details", WIDTH),
        *_body(doc),
        Spacer(0, 6 * mm),
        *_closing(doc, settings),
        *[f for text in doc.closing for f in (Spacer(0, 3 * mm), _p(text))],
        Spacer(0, 8 * mm),
        KeepTogether([_signatory(doc, settings)]),
    ]
    pdf.build(story)
    return buf.getvalue()


# --- reports (Quote History, Deal Tracker, Analytics) ------------------------

REPORT_TH = ParagraphStyle(
    "m_rth", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=colors.white
)


def report_header(
    title: str, subtitle: str, meta: list[tuple[str, str]], width: float, logo: bool = True
) -> Table:
    """The document header, for reports: blue title, a line under it, the facts, the logo.

    `logo=False` when the page band (report_brand) already carries it."""
    left: list[Flowable] = [Paragraph(esc(title), _TITLE)]
    if subtitle:
        left.append(Paragraph(esc(subtitle), _SUB))
    if meta:
        left.append(Spacer(0, 2 * mm))
        m = Table(
            [[_p(k, _L), _p(v, _BOLD)] for k, v in meta],
            colWidths=[30 * mm, 90 * mm],
            hAlign="LEFT",
        )
        m.setStyle(_tight())
        left.append(m)
    if logo:
        mark = Image(str(ASSETS / "logo-excel.png"), width=52 * mm, height=52 * mm * 128 / 611)
        mark.hAlign = "RIGHT"
        t = Table([[left, mark]], colWidths=[width - 58 * mm, 58 * mm])
    else:
        t = Table([[left, ""]], colWidths=[width - 1, 1])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 4 * mm),
            ]
        )
    )
    return t


def report_table_style(extra: list[Any] | None = None, padding: float = 3) -> TableStyle:
    """Blue header row, zebra rows, rounded corners, hairline row rules."""
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND),
            ("ROUNDEDCORNERS", [5, 5, 5, 5]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ("LEFTPADDING", (0, 0), (-1, -1), padding + 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), padding + 1),
            *(extra or []),
        ]
    )


def report_pages(title: str) -> Any:
    """Every report page: a quiet 'title · page n' at the top right."""

    def draw(canvas: Any, d: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(INK2)
        canvas.drawRightString(
            d.pagesize[0] - d.rightMargin, d.pagesize[1] - 6 * mm, f"{title} · Page {d.page}"
        )
        canvas.restoreState()

    return draw
