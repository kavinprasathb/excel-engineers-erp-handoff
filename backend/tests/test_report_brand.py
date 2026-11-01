"""Report downloads carry the login page's branding: logo, tagline, promises."""

import io
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from openpyxl import load_workbook  # type: ignore[import-untyped]
from pypdf import PdfReader

from app.services import deal_tracker, history_export
from app.services.report_brand import PROMISES, TAGLINE
from tests.test_orders import admin, client  # noqa: F401  (fixtures)


def _history_rows() -> list[dict[str, Any]]:
    return [
        {
            "quotation_id": i // 2,
            "customer": "=HYPERLINK(1)" if i == 0 else f"Customer {i}",
            "number": f"ESQSP-26-{i // 2}N1",
            "description": "RNS 125/100 Coupling",
            "quantity": 2,
            "quoted_paise": 1476000,
            "negotiations_paise": [1340000] + [None] * 9,
            "status": "won",
            "stage": 1,
            "decline_reason": None,
        }
        for i in range(120)
    ]


def _deal_rows() -> list[dict[str, Any]]:
    kinds = {"text": "x", "date": date(2026, 9, 1), "money": 1234500, "int": 3}
    return [{k: kinds.get(kind, 1) for k, _, kind in deal_tracker.COLUMNS}] * 90


def _assert_branded(pdf: bytes, title: str) -> None:
    pages = PdfReader(io.BytesIO(pdf)).pages
    assert len(pages) > 1
    for page in (pages[0], pages[-1]):  # continuation pages carry the bands too
        text = page.extract_text()
        assert TAGLINE[0] in text and TAGLINE[1] in text
        for _, a, b in PROMISES:
            assert a in text and b in text
        assert title in text
    assert "Page 2" in pages[1].extract_text()


def _header_row(ws: Any, first: str) -> int:
    return next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == first)


def test_history_pdf_and_xlsx_are_branded() -> None:
    rows = _history_rows()
    _assert_branded(history_export.to_pdf(rows, company="EE", filters="All"), "Quote History")
    ws = load_workbook(io.BytesIO(history_export.to_xlsx(rows, filters="All"))).active
    assert ws._images
    head = _header_row(ws, "Company")
    assert head > 3 and ws.cell(5, 1).value == "Quote History"
    assert [c.value for c in ws[head]][:5] == history_export.HEADERS[:5]
    first = ws.cell(head + 1, 1)
    assert first.value == "=HYPERLINK(1)" and first.data_type == "s"
    assert ws.cell(head + 1, 5).value == 14760
    assert ws.auto_filter.ref.startswith(f"A{head}:")
    assert ws.freeze_panes == f"D{head + 1}"
    values = [c.value for row in ws.iter_rows() for c in row]
    assert any(isinstance(v, str) and PROMISES[0][1] in v for v in values)
    assert "Page &P of &N" in ws.oddFooter.center.text


def test_deal_tracker_pdf_and_xlsx_are_branded() -> None:
    rows = _deal_rows()
    _assert_branded(deal_tracker.to_pdf(rows, company="EE", filters="All"), "Deal Tracker")
    ws = load_workbook(io.BytesIO(deal_tracker.to_xlsx(rows, filters="All"))).active
    assert ws._images
    head = _header_row(ws, "Client")
    assert ws.cell(head + 1, 4).value == "x"
    assert ws.page_setup.orientation == "landscape"
    assert ws.print_title_rows == f"${head}:${head}"


def test_analytics_pdf_is_branded(client: TestClient) -> None:  # noqa: F811
    r = client.get("/api/analytics/pdf", params={"from": "2026-09-01", "to": "2026-09-30"})
    text = PdfReader(io.BytesIO(r.content)).pages[0].extract_text()
    assert TAGLINE[0] in text and PROMISES[2][1] in text and "Sales Analytics" in text
