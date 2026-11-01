"""The login page's look, for every report download (Analytics, Quote History, Deal Tracker).

PDF: a light header band with the Excel Engineers / KSB logo and the tagline,
a thin blue-tinted photo strip, and the navy footer band with the three
promises, on every page. `brand_doc` gives the margins that keep the content
clear of the bands; `brand_pages` draws them.

Excel: `brand_sheet` writes the logo, tagline, title and facts above the
column headers; `finish_sheet` adds the promise row, filter, freeze and
print setup once the data is in. Quotation and purchase-order PDFs keep
their own letterhead (modern_pdf.render).
"""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from openpyxl.drawing.image import Image as XLImage  # type: ignore[import-untyped]
from openpyxl.styles import (  # type: ignore[import-untyped]
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter  # type: ignore[import-untyped]
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate

from .xlsx_safe import is_risky

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LOGO = ASSETS / "logo-excel-ksb.png"
BANNER = ASSETS / "report-banner.jpg"

TAGLINE = ("Engineering Excellence", "with Trusted Solutions")
PROMISES = (
    ("shield", "German Engineering", "Superior Quality"),
    ("gear", "Reliable Performance", "Longer Life"),
    ("leaf", "Sustainable Solutions", "for a Better Tomorrow"),
)

HEADER_BG = colors.HexColor("#f3f7fc")
HEADER_RULE = colors.HexColor("#d6e2f2")
TAG_BLUE = colors.HexColor("#1f4f9a")
NAVY = colors.HexColor("#081f4d")
TINT = colors.HexColor("#123c86")

HEADER_H = 17 * mm
BANNER_H = 6 * mm
FOOTER_H = 13 * mm
GAP = 5 * mm


# --- PDF ---------------------------------------------------------------------


def brand_doc(buf: Any, pagesize: tuple[float, float], side: float, **kw: Any) -> SimpleDocTemplate:
    """A report document whose frame sits between the header and footer bands."""
    return SimpleDocTemplate(
        buf,
        pagesize=pagesize,
        leftMargin=side,
        rightMargin=side,
        topMargin=HEADER_H + BANNER_H + GAP,
        bottomMargin=FOOTER_H + GAP,
        **kw,
    )


def _icon(c: Any, kind: str, cx: float, cy: float, r: float) -> None:
    """White line icons: shield, gear, leaf."""
    c.saveState()
    c.setStrokeColor(colors.white)
    c.setLineWidth(0.8)
    c.setLineJoin(1)
    c.setLineCap(1)
    if kind == "shield":
        p = c.beginPath()
        p.moveTo(cx, cy + r)
        p.lineTo(cx + 0.85 * r, cy + 0.65 * r)
        p.curveTo(cx + 0.85 * r, cy - 0.2 * r, cx + 0.5 * r, cy - 0.7 * r, cx, cy - r)
        p.curveTo(
            cx - 0.5 * r, cy - 0.7 * r, cx - 0.85 * r, cy - 0.2 * r, cx - 0.85 * r, cy + 0.65 * r
        )
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.lines(
            [
                (cx - 0.38 * r, cy, cx - 0.08 * r, cy - 0.3 * r),
                (cx - 0.08 * r, cy - 0.3 * r, cx + 0.42 * r, cy + 0.3 * r),
            ]
        )
    elif kind == "gear":
        import math

        c.circle(cx, cy, 0.62 * r, stroke=1, fill=0)
        c.circle(cx, cy, 0.25 * r, stroke=1, fill=0)
        for i in range(8):
            a = i * math.pi / 4
            c.line(
                cx + 0.62 * r * math.cos(a),
                cy + 0.62 * r * math.sin(a),
                cx + r * math.cos(a),
                cy + r * math.sin(a),
            )
    else:  # leaf
        p = c.beginPath()
        p.moveTo(cx - 0.8 * r, cy - 0.8 * r)
        p.curveTo(cx - 0.9 * r, cy + 0.6 * r, cx + 0.2 * r, cy + r, cx + 0.9 * r, cy + 0.9 * r)
        p.curveTo(
            cx + 0.9 * r, cy + 0.1 * r, cx + 0.5 * r, cy - 0.9 * r, cx - 0.8 * r, cy - 0.8 * r
        )
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.line(cx - 0.8 * r, cy - 0.8 * r, cx + 0.4 * r, cy + 0.4 * r)
    c.restoreState()


def _header(c: Any, w: float, h: float, side: float) -> None:
    y = h - HEADER_H
    c.setFillColor(HEADER_BG)
    c.rect(0, y, w, HEADER_H, stroke=0, fill=1)
    logo_h = 11 * mm
    c.drawImage(
        str(LOGO), side, y + (HEADER_H - logo_h) / 2, width=logo_h * 4.5, height=logo_h, mask="auto"
    )
    # Tagline on the right, a thin divider before it.
    c.setFillColor(TAG_BLUE)
    c.setFont("Helvetica-Bold", 9)
    tw = max(c.stringWidth(t, "Helvetica-Bold", 9) for t in TAGLINE)
    x = w - side - tw
    c.drawString(x, y + HEADER_H / 2 + 1.2 * mm, TAGLINE[0])
    c.setFont("Helvetica", 9)
    c.drawString(x, y + HEADER_H / 2 - 3.4 * mm, TAGLINE[1])
    c.setStrokeColor(HEADER_RULE)
    c.setLineWidth(0.8)
    c.line(x - 4 * mm, y + 3.5 * mm, x - 4 * mm, y + HEADER_H - 3.5 * mm)
    # Photo strip, tinted blue like the login hero.
    by = y - BANNER_H
    c.saveState()
    p = c.beginPath()
    p.rect(0, by, w, BANNER_H)
    c.clipPath(p, stroke=0, fill=0)
    img_h = w * 215 / 1200
    c.drawImage(str(BANNER), 0, by + BANNER_H / 2 - img_h / 2, width=w, height=img_h)
    c.setFillColor(TINT)
    c.setFillAlpha(0.55)
    c.rect(0, by, w, BANNER_H, stroke=0, fill=1)
    c.restoreState()
    c.setStrokeColor(HEADER_RULE)
    c.line(0, y, w, y)


def _footer(c: Any, w: float, side: float, title: str, prepared: str, page: int) -> None:
    c.setFillColor(NAVY)
    c.rect(0, 0, w, FOOTER_H, stroke=0, fill=1)
    right_w = 62 * mm if w > 220 * mm else 50 * mm
    slot = (w - 2 * side - right_w) / 3
    slot = min(slot, 70 * mm)
    mid = FOOTER_H / 2
    for i, (kind, a, b) in enumerate(PROMISES):
        x = side + i * slot
        if i:
            c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.35))
            c.setLineWidth(0.5)
            c.line(x - 3 * mm, 3 * mm, x - 3 * mm, FOOTER_H - 3 * mm)
        _icon(c, kind, x + 3 * mm, mid, 2.6 * mm)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(x + 8 * mm, mid + 0.8 * mm, a)
        c.setFont("Helvetica", 7)
        c.drawString(x + 8 * mm, mid - 2.8 * mm, b)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(w - side, mid + 0.8 * mm, f"Page {page}")
    c.setFont("Helvetica", 7)
    tail = f"{title} · {prepared}" if prepared else title
    c.drawRightString(w - side, mid - 2.8 * mm, tail)


def brand_pages(title: str, prepared: str = "") -> Callable[[Any, Any], None]:
    """onFirstPage / onLaterPages: the header band, photo strip and footer band."""

    def draw(canvas: Any, d: Any) -> None:
        w, h = d.pagesize
        canvas.saveState()
        _header(canvas, w, h, d.leftMargin)
        _footer(canvas, w, d.leftMargin, title, prepared, d.page)
        canvas.restoreState()

    return draw


# --- Excel -------------------------------------------------------------------

X_HEADER_BG = "F3F7FC"
X_NAVY = "081F4D"
X_BLUE = "1D5FC4"
X_TAG = "1F4F9A"


def _safe(cell: Any, value: Any) -> Any:
    cell.value = value
    if is_risky(value):
        cell.data_type = "s"
        cell.quotePrefix = True
    return cell


def brand_sheet(
    ws: Any, title: str, meta: Sequence[tuple[str, str]], headers: Sequence[str]
) -> int:
    """Logo, tagline, title and facts, then the styled column-header row; returns its row."""
    ncols = max(len(headers), 8)
    fill = PatternFill("solid", fgColor=X_HEADER_BG)
    for r in range(1, 4):
        ws.row_dimensions[r].height = 14 if r == 3 else 20
        for col in range(1, ncols + 1):
            ws.cell(r, col).fill = fill
    logo = XLImage(str(LOGO))
    logo.width, logo.height = 225, 50
    ws.add_image(logo, "A1")
    tag = ws.cell(1, ncols, TAGLINE[0])
    tag.font = Font(bold=True, color=X_TAG, size=11)
    tag.alignment = Alignment(horizontal="right", vertical="bottom")
    tag2 = ws.cell(2, ncols, TAGLINE[1])
    tag2.font = Font(color=X_TAG, size=11)
    tag2.alignment = Alignment(horizontal="right", vertical="top")
    rule = Side(style="thin", color="D6E2F2")
    for col in range(1, ncols + 1):
        ws.cell(3, col).border = Border(bottom=rule)
    t = ws.cell(5, 1, title)
    t.font = Font(bold=True, size=16, color=X_BLUE)
    row = 6
    for k, v in meta:
        ws.cell(row, 1, k).font = Font(color="5F6B7D")
        _safe(ws.cell(row, 2), v).font = Font(bold=True)
        row += 1
    head_row = row + 1
    for col, h in enumerate(headers, start=1):
        _safe(ws.cell(head_row, col), h)
    ws.row_dimensions[head_row].height = 30
    for cell in ws[head_row][: len(headers)]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=X_BLUE)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = Border(bottom=Side(style="thin", color=X_NAVY))
    return head_row


def finish_sheet(ws: Any, head_row: int, title: str, freeze_col: str = "A") -> None:
    """After the data: filter, freeze, the navy promise row, and print setup."""
    ncols = len([c for c in ws[head_row] if c.value is not None])
    last = ws.max_row
    end = get_column_letter(ncols)
    ws.auto_filter.ref = f"A{head_row}:{end}{last}"
    ws.freeze_panes = f"{freeze_col}{head_row + 1}"
    foot = last + 2
    navy = PatternFill("solid", fgColor=X_NAVY)
    for col in range(1, ncols + 1):
        ws.cell(foot, col).fill = navy
    span = max(ncols // 3, 1)
    for i, (_, a, b) in enumerate(PROMISES):
        col = 1 + i * span
        if col > ncols:
            break
        cell = ws.cell(foot, col, f"{a} · {b}")
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(vertical="center")
    ws.row_dimensions[foot].height = 22
    ps = ws.page_setup
    ps.orientation = "landscape" if ncols > 8 else "portrait"
    ps.paperSize = ws.PAPERSIZE_A4
    ps.fitToWidth = 1
    ps.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{head_row}:{head_row}"
    ws.oddFooter.center.text = f"Excel Engineers · {title} · Page &P of &N"
