"""Small guards that sit outside any one feature: exports, search, imports, docs."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook  # type: ignore[import-untyped]
from pydantic import ValidationError

from app import main as app_main
from app.config import Settings
from app.schemas.inventory import StockAdjustRequest
from app.services import deal_tracker, history_export
from app.services.importer import runner
from app.services.like import contains


def test_exports_never_write_user_text_as_a_formula() -> None:
    evil = '=HYPERLINK("http://evil.example.com","x")'
    row = {
        "customer": evil,
        "number": "Q-1",
        "description": "+cmd|' /C calc'!A0",
        "quantity": 1,
        "quoted_paise": 100,
        "negotiations_paise": [None] * history_export.STAGES,
        "status": "open",
        "stage": 0,
        "decline_reason": "@SUM(1)",
    }
    sheet = load_workbook(io.BytesIO(history_export.to_xlsx([row]))).active
    # The branded header pushes the data down; look at every cell.
    cells = {c.value: c for row in sheet.iter_rows() for c in row if c.value is not None}
    for text in (evil, row["description"], row["decline_reason"]):
        assert cells[text].data_type == "s"
        assert cells[text].quotePrefix


def test_deal_tracker_export_uses_the_safe_append() -> None:
    row = {key: None for key, _, _ in deal_tracker.COLUMNS}
    row["customer"] = "=1+1"
    sheet = load_workbook(io.BytesIO(deal_tracker.to_xlsx([row]))).active
    cell = next(c for row in sheet.iter_rows() for c in row if c.value == "=1+1")
    assert cell.data_type == "s" and cell.quotePrefix


def test_search_terms_are_literal_inside_ilike() -> None:
    assert contains(" 50% off_x\\ ") == "%50\\% off\\_x\\\\%"


def test_stock_adjustment_is_bounded() -> None:
    assert StockAdjustRequest(delta=-1_000_000).delta == -1_000_000
    with pytest.raises(ValidationError):
        StockAdjustRequest(delta=1_000_001)


def test_a_zip_bomb_is_refused_before_openpyxl_reads_it() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/big.xml", b"0" * (runner.MAX_UNCOMPRESSED_BYTES + 1))
    with pytest.raises(runner.ImportAborted, match="too large"):
        runner.read_rows(buf.getvalue())


def test_an_oversized_sheet_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    for i in range(6):
        wb.active.append([f"SKU{i}", "Name"])
    out = io.BytesIO()
    wb.save(out)
    monkeypatch.setattr(runner, "MAX_ROWS", 4)
    with pytest.raises(runner.ImportAborted, match="more than 4 rows"):
        runner.read_rows(out.getvalue())


def test_api_docs_are_hidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    production = Settings(environment="production", jwt_secret="x" * 40)
    monkeypatch.setattr(app_main, "get_settings", lambda: production)
    client = TestClient(app_main.create_app())
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404


def test_environment_decides_production() -> None:
    assert Settings(environment="production", cors_origins="").is_production
    assert Settings(environment="production", cors_origins="http://x").is_production
    assert not Settings(environment="development").is_production
    assert not Settings(environment="test").is_production
