"""Quote History as a file: Excel for working with, PDF for printing or sharing.

Both take the rows `quotations.history_matrix` produced, so the download is
exactly what the screen showed under the same search and filter.
"""

import re
from datetime import date
from io import BytesIO
from typing import Any

from openpyxl import Workbook  # type: ignore[import-untyped]
from openpyxl.utils import get_column_letter  # type: ignore[import-untyped]
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table

from .modern_pdf import REPORT_TH, report_header, report_table_style
from .quotation_pdf import indian_rupees
from .report_brand import brand_doc, brand_pages, brand_sheet, finish_sheet
from .xlsx_safe import append_safe

STAGES = 10
# Versions after the original, in order: each a revised quotation (R) or a
# negotiation (N). "Versions" names them, so V1, V2... read as R1, R2, N1...
HEADERS = (
    ["Company", "Quote no.", "Description", "Qty", "Quoted price"]
    + [f"V{n}" for n in range(1, STAGES + 1)]
    + ["Current price", "Result", "Stage", "Versions", "Decline reason"]
)


def _stages(r: dict[str, Any]) -> list[dict[str, Any]]:
    """The labelled versions; a row without them reads its N1..N10 rates as negotiations."""
    if "stages" in r:
        return list(r["stages"])
    rates = r.get("negotiations_paise") or []
    return [{"label": f"N{i}", "rate_paise": v} for i, v in enumerate(rates, 1) if v is not None]


def _versions(r: dict[str, Any]) -> str:
    return " > ".join(s["label"] for s in _stages(r))


def _stage_rates(r: dict[str, Any]) -> list[int | None]:
    rates = [s["rate_paise"] for s in _stages(r)[:STAGES]]
    return rates + [None] * (STAGES - len(rates))


def _original(r: dict[str, Any]) -> str:
    """ESQSP-26-2-R1N2 -> ESQSP-26-2, when the row does not say."""
    return str(r.get("original_number") or re.sub(r"(-R\d+)?(N\d+)?$", "", str(r["number"])))


def _stage_label(r: dict[str, Any]) -> str:
    if r.get("stage_label"):
        return str(r["stage_label"])
    return "Initial quote" if not r.get("stage") else f"Negotiation N{r['stage']}"


def _current(r: dict[str, Any]) -> int | None:
    if "current_paise" in r:
        return r["current_paise"]  # type: ignore[no-any-return]
    rates = [v for v in [r.get("quoted_paise"), *_stage_rates(r)] if v is not None]
    return rates[-1] if rates else None


def to_xlsx(rows: list[dict[str, Any]], *, filters: str = "") -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Quote history"
    head = brand_sheet(
        ws,
        "Quote History",
        [
            ("As on", date.today().strftime("%d.%m.%Y")),
            ("Filters", filters or "None"),
            ("Prices", "Rs., before GST"),
        ],
        HEADERS,
    )
    for r in rows:
        # Rupees as numbers, not text, so the sheet can sum and sort them.
        rupees = [
            None if v is None else v / 100
            for v in [r["quoted_paise"], *_stage_rates(r), _current(r)]
        ]
        append_safe(
            ws,
            [
                r["customer"],
                _original(r),
                r["description"],
                r["quantity"],
                *rupees,
                str(r["status"]).capitalize(),
                _stage_label(r),
                _versions(r) or None,
                r["decline_reason"] or None,
            ],
        )
    money_cols = range(5, 5 + 2 + STAGES)
    for row in ws.iter_rows(min_row=head + 1):
        for c in money_cols:
            row[c - 1].number_format = "#,##,##0"
    widths = [34, 16, 40, 6, 14] + [12] * STAGES + [14, 11, 26, 24, 40]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    finish_sheet(ws, head, "Quote History", freeze_col="D")
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


_CELL = ParagraphStyle("hcell", fontName="Helvetica", fontSize=7, leading=8.5)
_HEAD = ParagraphStyle("hhead", parent=_CELL, fontName="Helvetica-Bold")
_TITLE = ParagraphStyle("htitle", fontName="Helvetica-Bold", fontSize=13, leading=16)
_SUB = ParagraphStyle("hsub", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.grey)


def _rs(v: int | None) -> str:
    return "" if v is None else indian_rupees(v)


def to_pdf(rows: list[dict[str, Any]], *, company: str, filters: str) -> bytes:
    buf = BytesIO()
    doc = brand_doc(
        buf,
        landscape(A4),
        8 * mm,
        title="Quote history",
        author=company,
    )
    head = (
        ["Company", "Description", "Qty", "Quoted"]
        + [f"V{n}" for n in range(1, STAGES + 1)]
        + ["Result"]
    )
    data: list[list[Any]] = [[Paragraph(h, REPORT_TH) for h in head]]
    style: list[tuple[Any, ...]] = [
        ("ALIGN", (2, 1), (-2, -1), "RIGHT"),
        ("FONTNAME", (2, 1), (-2, -1), "Helvetica"),
        ("FONTSIZE", (2, 1), (-2, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    prev_quote = None
    for i, r in enumerate(rows, start=1):
        first = r["quotation_id"] != prev_quote
        prev_quote = r["quotation_id"]
        who = f"<b>{_esc(r['customer'])}</b><br/>{_esc(_original(r))}" if first else ""
        result = ""
        if first:
            result = f"<b>{str(r['status']).capitalize()}</b><br/>{_esc(_stage_label(r))}"
            if _stages(r):
                result += f"<br/>V: {_esc(_versions(r))}"
            if r["decline_reason"]:
                result += f"<br/>{_esc(r['decline_reason'])}"
        prices = [r["quoted_paise"], *_stage_rates(r)]
        data.append(
            [
                Paragraph(who, _CELL),
                Paragraph(_esc(r["description"]), _CELL),
                str(r["quantity"] or ""),
            ]
            + [_rs(v) for v in prices]
            + [Paragraph(result, _CELL)]
        )
        if first and i > 1:
            style.append(("LINEABOVE", (0, i), (-1, i), 0.8, colors.HexColor("#9fb4d8")))
        # Green where the price came down from the stage before.
        for n in range(1, len(prices)):
            a, b = prices[n - 1], prices[n]
            if a is not None and b is not None and b < a:
                style.append(("TEXTCOLOR", (3 + n, i), (3 + n, i), colors.HexColor("#15803D")))
    # 281 mm of landscape A4 inside the margins.
    widths = [36 * mm, 46 * mm, 8 * mm, 17 * mm] + [14 * mm] * STAGES + [30 * mm]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(report_table_style(style, padding=2))
    story = [
        report_header(
            "Quote History",
            "Every item, end to end: quoted price, each negotiation, and the result.",
            [
                ("As on", date.today().strftime("%d.%m.%Y")),
                ("Filters", filters or "None"),
                ("Prices", "Rs., before GST"),
            ],
            doc.width,
            logo=False,
        ),
        Spacer(0, 5 * mm),
        table,
    ]
    page = brand_pages("Quote History", "As on " + date.today().strftime("%d.%m.%Y"))
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()


def _esc(s: str) -> str:
    from xml.sax.saxutils import escape

    return escape(s)
