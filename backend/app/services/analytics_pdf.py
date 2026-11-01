"""The Analytics page as a PDF, on the Excel Engineers letterhead.

Same numbers as the screen (`analytics.report`), laid out for print: headline
boxes, a few plain-sentence highlights, donut charts for conversion, decline
reasons and customers, a column chart of monthly sales, then the tables.
"""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape as esc

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from ..models import AppSettings
from .modern_pdf import report_header, report_table_style
from .quotation_pdf import indian_rupees
from .report_brand import brand_doc, brand_pages

IST = timezone(timedelta(hours=5, minutes=30))

# Categorical order, never cycled past its end; "Other" is always grey.
SERIES = ["#8b7cf0", "#7fd3c6", "#f6c453", "#f29ac8", "#7d86e8", "#9fc5f8", "#a8dd8e"]
GREY = "#d4d4d8"
GREEN, RED, AMBER, INK, INK2, LINE = (
    "#6fcf97",
    "#f29a9a",
    "#f6c453",
    "#1f1f1c",
    "#6b6a64",
    "#dcdad2",
)

_BODY = ParagraphStyle(
    "a_body", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor(INK)
)
_SMALL = ParagraphStyle(
    "a_small", parent=_BODY, fontSize=8, leading=10, textColor=colors.HexColor(INK2)
)
_H1 = ParagraphStyle(
    "a_h1", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.HexColor(INK)
)
_H2 = ParagraphStyle(
    "a_h2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#1e5eb8")
)
_KPI_L = ParagraphStyle("a_kl", parent=_SMALL, fontName="Helvetica-Bold", fontSize=7, leading=9)
_KPI_V = ParagraphStyle(
    "a_kv", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.HexColor(INK)
)
_CELL = ParagraphStyle("a_cell", parent=_BODY, fontSize=8, leading=10)
_CELL_R = ParagraphStyle("a_cellr", parent=_CELL, alignment=TA_RIGHT)
_HEAD = ParagraphStyle(
    "a_head", parent=_CELL, fontName="Helvetica-Bold", textColor=colors.HexColor(INK2)
)
_HEAD_R = ParagraphStyle("a_headr", parent=_HEAD, alignment=TA_RIGHT)
_TH = ParagraphStyle("a_th", parent=_HEAD, textColor=colors.white)
_TH_R = ParagraphStyle("a_thr", parent=_TH, alignment=TA_RIGHT)

WIDTH = 180 * mm - 12  # frame width less its padding


def rs(paise: int) -> str:
    return f"Rs. {indian_rupees(paise)}"


def pct(v: float | None) -> str:
    return "-" if v is None else f"{v:g}%"


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _or_dash(v: float | None, unit: str = "") -> str:
    return "-" if v is None else f"{v:g}{unit}"


def _d(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d.%m.%Y") if iso else "-"


def _kpis(a: dict[str, Any]) -> Table:
    c, s, p = a["conversion"], a["sales"], a["pipeline"]
    boxes = [
        ("QUOTES GIVEN", str(c["quoted"]), f"worth {rs(c['quoted_value_paise'])}", SERIES[0]),
        (
            "WIN RATE",
            pct(c["rate_answered"]),
            f"{c['accepted_count']} won of {c['accepted_count'] + c['declined_count']} answered",
            SERIES[2],
        ),
        (
            "SALES (DELIVERED)",
            rs(s["value_paise"]),
            plural(s["orders"], "order", "orders"),
            SERIES[5],
        ),
        (
            "MONEY STILL TO WIN",
            rs(p["value_paise"]),
            f"{p['count']} open, {p['follow_up_count']} need a call",
            SERIES[3],
        ),
    ]
    cells = [
        [Paragraph(label, _KPI_L), Paragraph(esc(value), _KPI_V), Paragraph(esc(sub), _SMALL)]
        for label, value, sub, _ in boxes
    ]
    w = (WIDTH - 3 * 3 * mm) / 4
    row = []
    for i, cell in enumerate(cells):
        t = Table([[x] for x in cell], colWidths=[w])
        t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(LINE)),
                    ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor(boxes[i][3])),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, 0), 7),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
                    ("TOPPADDING", (0, 1), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -2), 1),
                ]
            )
        )
        row.append(t)
    outer = Table([row], colWidths=[w + 3 * mm] * 3 + [w])
    outer.setStyle(
        TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)])
    )
    return outer


def _highlights(a: dict[str, Any]) -> list[str]:
    out = []
    customers = sorted(a["customers"], key=lambda r: (-r["sales_paise"], -r["quotes"]))
    if customers:
        top = customers[0]
        out.append(
            f"Best customer: <b>{esc(top['customer'])}</b> - "
            f"{plural(top['quotes'], 'quote', 'quotes')}, {top['accepted']} won."
        )
    reasons = a["conversion"]["reasons"]
    if reasons:
        out.append(
            f"Top reason for losing: <b>{esc(reasons[0]['reason'])}</b> "
            f"({reasons[0]['count']} of {a['conversion']['declined_count']})."
        )
    n = a["pipeline"]["follow_up_count"]
    if n:
        out.append(
            f"<b>{n}</b> pending {'quote needs' if n == 1 else 'quotes need'} a follow-up call."
        )
    return out


def _donut(title: str, slices: list[tuple[str, int, str]], center: str, sub: str) -> Flowable:
    """A donut with the headline inside and a legend naming every slice."""
    size = 100
    d = Drawing(size, size)
    shown = [(label, v, col) for label, v, col in slices if v > 0]
    if shown:
        ring = Doughnut()
        ring.x = ring.y = 5
        ring.width = ring.height = size - 10
        ring.data = [v for _, v, _ in shown]
        ring.labels = None
        ring.innerRadiusFraction = 0.62
        ring.startAngle = 90
        ring.direction = "clockwise"
        ring.slices.strokeColor = colors.white
        ring.slices.strokeWidth = 1.5
        for i, (_, _, col) in enumerate(shown):
            ring.slices[i].fillColor = colors.HexColor(col)
        d.add(ring)
    d.add(
        String(
            size / 2,
            size / 2 + 1,
            center,
            fontName="Helvetica-Bold",
            fontSize=14,
            textAnchor="middle",
            fillColor=colors.HexColor(INK),
        )
    )
    d.add(
        String(
            size / 2,
            size / 2 - 11,
            sub,
            fontName="Helvetica",
            fontSize=7,
            textAnchor="middle",
            fillColor=colors.HexColor(INK2),
        )
    )
    total = sum(v for _, v, _ in slices) or 1
    legend = [
        [
            Paragraph(f'<font color="{col}" size="11">&#9679;</font>', _CELL),
            Paragraph(esc(label), _CELL),
            Paragraph(f"{v} ({round(v * 100 / total)}%)", _CELL_R),
        ]
        for label, v, col in slices
    ]
    lg = Table(legend, colWidths=[5 * mm, 29 * mm, 15 * mm])
    lg.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    body = Table([[d, lg]], colWidths=[size + 4, 50 * mm])
    body.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)])
    )
    return Table([[Paragraph(title, _H2)], [body]], colWidths=[WIDTH / 2 - 2])


def _pair(left: Flowable, right: Flowable) -> Table:
    t = Table([[left, right]], colWidths=[WIDTH / 2, WIDTH / 2])
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


def _sales_chart(a: dict[str, Any]) -> list[Flowable]:
    months = a["sales"]["by_month"]
    title = Paragraph(
        f"Sales by month <font size=8 color='{INK2}'>- delivered orders, average "
        f"{rs(a['sales']['average_paise'])}</font>",
        _H2,
    )
    if not months:
        return [title, Paragraph("No deliveries in this period.", _SMALL)]
    d = Drawing(WIDTH, 150)
    ch = VerticalBarChart()
    ch.x, ch.y, ch.height = 50, 22, 115
    ch.width = int(WIDTH - 60)
    ch.data = [[m["value_paise"] / 100 for m in months]]
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    ch.categoryAxis.categoryNames = [
        f"{names[int(m['month'][5:]) - 1]} {m['month'][2:4]}" for m in months
    ]
    ch.categoryAxis.labels.fontName = "Helvetica"
    ch.categoryAxis.labels.fontSize = 7
    ch.categoryAxis.strokeColor = colors.HexColor(LINE)
    ch.valueAxis.valueMin = 0
    ch.valueAxis.labels.fontName = "Helvetica"
    ch.valueAxis.labels.fontSize = 7
    ch.valueAxis.labelTextFormat = lambda v: indian_rupees(int(v * 100))
    ch.valueAxis.strokeColor = colors.HexColor(LINE)
    ch.valueAxis.gridStrokeColor = colors.HexColor("#eeede8")
    ch.valueAxis.visibleGrid = True
    ch.bars[0].fillColor = colors.HexColor(SERIES[0])
    ch.bars[0].strokeColor = None
    ch.barLabelFormat = lambda v: indian_rupees(int(v * 100))
    ch.barLabels.fontName = "Helvetica"
    ch.barLabels.fontSize = 6.5
    ch.barLabels.nudge = 6
    d.add(ch)
    return [title, d]


def _table(head: list[str], rows: list[list[str]], widths: list[float], left: int = 1) -> Table:
    """The first `left` columns are text, left-aligned; the rest are numbers."""
    data = [[Paragraph(h, _TH if i < left else _TH_R) for i, h in enumerate(head)]]
    for r in rows:
        data.append([Paragraph(esc(v), _CELL if i < left else _CELL_R) for i, v in enumerate(r)])
    scale = WIDTH / sum(widths)
    t = Table(data, colWidths=[w * scale for w in widths], repeatRows=1)
    t.setStyle(report_table_style([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t


def _section(title: str, sub: str, body: Flowable | None, empty: str) -> Flowable:
    parts: list[Flowable] = [
        Paragraph(f"{esc(title)} <font size=8 color='{INK2}'>- {esc(sub)}</font>", _H2),
        Spacer(0, 2 * mm),
    ]
    parts.append(body if body is not None else Paragraph(empty, _SMALL))
    return KeepTogether(parts)


def render_analytics_pdf(a: dict[str, Any], settings: AppSettings) -> bytes:
    buf = BytesIO()
    doc = brand_doc(
        buf,
        A4,
        15 * mm,
        title="Analytics",
        author=settings.company_name,
    )
    start = _d(a["from"]) if a["from"] else "From the start"
    period = f"{start} to {_d(a['to']) if a['to'] else 'today'}"
    made = datetime.now(IST).strftime("%d.%m.%Y %H:%M")
    c = a["conversion"]

    story: list[Flowable] = [
        report_header(
            "Sales Analytics",
            "How quotes convert, what sells, and where deals get stuck.",
            [("Period", period), ("Amounts", "include 18% GST"), ("Prepared", made)],
            WIDTH,
            logo=False,
        ),
        Spacer(0, 5 * mm),
        _kpis(a),
        Spacer(0, 4 * mm),
    ]
    for h in _highlights(a):
        story.append(Paragraph(f'<font color="{SERIES[1]}">&#9656;</font> {h}', _BODY))
    story.append(Spacer(0, 5 * mm))

    conv = _donut(
        "Quote conversion",
        [
            ("Accepted", c["accepted_count"], GREEN),
            ("Declined", c["declined_count"], RED),
            ("Still pending", c["pending_count"], AMBER),
        ],
        pct(c["rate_answered"]),
        "win rate",
    )
    slot = 0
    reason_slices = []
    for r in c["reasons"]:
        if r["reason"] == "Other":
            col = GREY
        else:
            col = SERIES[slot % len(SERIES)]
            slot += 1
        reason_slices.append((r["reason"], r["count"], col))
    reasons: Flowable = (
        _donut("Why quotes were declined", reason_slices, str(c["declined_count"]), "declined")
        if reason_slices
        else Table(
            [[Paragraph("Why quotes were declined", _H2)], [Paragraph("Nothing declined.", _SMALL)]]
        )
    )
    story += [_pair(conv, reasons), Spacer(0, 5 * mm)]

    customers = sorted(a["customers"], key=lambda r: -r["quotes"])
    cust_slices = [(r["customer"], r["quotes"], SERIES[i]) for i, r in enumerate(customers[:5])]
    rest = sum(r["quotes"] for r in customers[5:])
    if rest:
        cust_slices.append(("All others", rest, GREY))
    repeat = sum(1 for r in customers if r["repeat"])
    who: Flowable = (
        _donut("Who asks for quotes", cust_slices, str(len(customers)), "customers")
        if cust_slices
        else Paragraph("No customers in this period.", _SMALL)
    )
    t = a["time_to_close"]
    close = Table(
        [
            [Paragraph("Time to close", _H2)],
            [
                Paragraph(
                    f"To win: <b>{_or_dash(t['accepted_avg_days'], ' days')}</b><br/>"
                    f"To lose: <b>{_or_dash(t['declined_avg_days'], ' days')}</b><br/>"
                    f"Negotiations to win: <b>{_or_dash(t['avg_rounds_to_win'])}</b><br/><br/>"
                    f"{repeat} of {plural(len(customers), 'customer', 'customers')} "
                    "came back for more than one quote.",
                    _BODY,
                )
            ],
        ]
    )
    story += [
        KeepTogether(_sales_chart(a)),
        Spacer(0, 5 * mm),
        _pair(who, close),
        Spacer(0, 5 * mm),
    ]

    story.append(
        _section(
            "Customers",
            "most quotes first",
            _table(
                ["Customer", "Quotes", "Won", "Declined", "Win rate", "Quoted", "Sales"],
                [
                    [
                        r["customer"] + (" (repeat)" if r["repeat"] else ""),
                        str(r["quotes"]),
                        str(r["accepted"]),
                        str(r["declined"]),
                        pct(r["rate"]),
                        rs(r["quoted_value_paise"]),
                        rs(r["sales_paise"]),
                    ]
                    for r in customers
                ],
                [60, 14, 12, 16, 16, 28, 28],
            )
            if customers
            else None,
            "No customers in this period.",
        )
    )
    story.append(Spacer(0, 5 * mm))
    story.append(
        _section(
            "Products",
            "quoted against won",
            _table(
                [
                    "Product",
                    "Quotes",
                    "Qty",
                    "Quoted value",
                    "Won",
                    "Qty won",
                    "Won value",
                    "Win rate",
                ],
                [
                    [
                        p["description"],
                        str(p["times_quoted"]),
                        str(p["qty_quoted"]),
                        rs(p["value_quoted_paise"]),
                        str(p["times_won"]),
                        str(p["qty_won"]),
                        rs(p["value_won_paise"]),
                        pct(p["rate"]),
                    ]
                    for p in a["products"]
                ],
                [50, 15, 10, 25, 11, 16, 25, 16],
            )
            if a["products"]
            else None,
            "No products quoted in this period.",
        )
    )
    story.append(Spacer(0, 5 * mm))
    d = a["discount"]
    story.append(
        _section(
            "Discount given in negotiation",
            f"{rs(d['discount_paise'])} ({pct(d['discount_pct'])}) off the first price"
            if d["won_quotes"]
            else "no quotes won",
            _table(
                ["Quote", "Customer", "Rounds", "First price", "Final price", "Discount"],
                [
                    [
                        r["number"],
                        r["customer"],
                        str(r["rounds"]),
                        rs(r["first_paise"]),
                        rs(r["final_paise"]),
                        f"{rs(r['discount_paise'])} ({pct(r['discount_pct'])})",
                    ]
                    for r in d["rows"]
                ],
                [26, 46, 16, 26, 26, 34],
                left=2,
            )
            if d["rows"]
            else None,
            "No won quote was negotiated down.",
        )
    )
    story.append(Spacer(0, 5 * mm))
    ro = a["reorder"]
    story.append(
        _section(
            "Reorder suggestions",
            f"{ro['count']} to buy, about {rs(ro['value_paise'])} at cost"
            if ro["count"]
            else "nothing to buy right now",
            _table(
                ["Product", "Free", "On order", "Per month", "Lasts", "Buy", "Cost"],
                [
                    [
                        r["name"] + ("  URGENT" if r["urgent"] else ""),
                        str(r["available"]),
                        str(r["on_order"]),
                        f"{r['per_month']:g}",
                        "-" if r["days_left"] is None else f"{r['days_left']} days",
                        str(r["suggest"]),
                        rs(r["value_paise"]),
                    ]
                    for r in ro["rows"]
                ],
                [60, 14, 16, 18, 18, 12, 26],
            )
            if ro["rows"]
            else None,
            "All stocked.",
        )
    )
    story.append(Spacer(0, 5 * mm))
    p = a["pipeline"]
    story.append(
        _section(
            "Pending quotes to follow up",
            f"oldest first; no change in {p['follow_up_days']}+ days is marked FOLLOW UP",
            _table(
                ["Quote", "Customer", "First sent", "Last change", "Age", "Value"],
                [
                    [
                        r["number"] + ("  FOLLOW UP" if r["follow_up"] else ""),
                        r["customer"],
                        _d(r["quote_date"]),
                        _d(r["last_change"]),
                        f"{r['age_days']} days",
                        rs(r["value_paise"]),
                    ]
                    for r in p["rows"]
                ],
                [40, 50, 22, 22, 16, 26],
                left=2,
            )
            if p["rows"]
            else None,
            "No pending quotes.",
        )
    )

    page = brand_pages("Sales Analytics", made)
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()
