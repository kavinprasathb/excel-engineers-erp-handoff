"""Importing someone else's spreadsheet.

The fixtures are built by `tests/fixtures/build_sample.py` rather than checked
in as opaque binaries — see that module for why. The sample deliberately
contains every awkward thing the client's real Tally export has: a letterhead
above the header, abbreviated headings, a column we do not map, Indian digit
grouping with a rupee sign, a percentage written as text, a missing supplier, a
repeated SKU, a negative quantity and a blank row.
"""

from collections.abc import Iterator
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import (
    IMPORT_MAX_STORED_ERRORS,
    ImportJobStatus,
    MovementType,
    ReferenceType,
    UserRole,
)
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import Category, ImportJob, Inventory, Product, StockMovement, Supplier, User
from app.security import hash_password
from app.services import stock
from app.services.importer import headers, runner, template

from .fixtures import build_sample


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="imports-admin@excelengineers.in",
        full_name="Admin",
        password_hash=hash_password("correct-horse-battery"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def client(db: Session, admin: User) -> Iterator[TestClient]:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    fastapi_app.dependency_overrides[get_current_user] = lambda: admin
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def sample_bytes() -> bytes:
    """Written to disk as well as returned, so the file exists to be opened in
    Excel when a failure needs looking at by hand."""
    data = build_sample.build_sample()
    build_sample.SAMPLE_PATH.write_bytes(data)
    return data


@pytest.fixture(scope="session")
def no_header_bytes() -> bytes:
    data = build_sample.build_no_header()
    build_sample.NO_HEADER_PATH.write_bytes(data)
    return data


def _run(db: Session, admin: User, data: bytes, filename: str = "stock.xlsx") -> ImportJob:
    """Run an import to completion against the test transaction.

    The worker opens its own session in production; here it is handed this
    test's, so everything it commits is still rolled back at the end.
    """
    job = runner.create_job(db, filename=filename, created_by_id=admin.id)
    runner.run_import(job.id, data, session_factory=lambda: nullcontext(db), actor_id=admin.id)
    db.refresh(job)
    return job


# --------------------------------------------------------------------------- the happy path


def test_the_sample_file_imports(db: Session, admin: User, sample_bytes: bytes) -> None:
    job = _run(db, admin, sample_bytes)

    assert job.status is ImportJobStatus.COMPLETED
    assert job.header_row_index == build_sample.HEADER_ROW_INDEX
    assert job.total_rows == build_sample.DATA_ROW_COUNT
    assert job.processed_rows == build_sample.DATA_ROW_COUNT
    assert job.created_count == 2
    assert job.updated_count == 1
    assert job.skipped_count == 1  # the blank row
    assert job.error_count == 1  # the negative quantity


def test_the_preamble_does_not_win_the_header_search(
    db: Session, admin: User, sample_bytes: bytes
) -> None:
    """A Tally letterhead sits above the real header and can match a field by
    accident; the true header always scores higher."""
    job = _run(db, admin, sample_bytes)
    assert job.column_mapping["sku"] == 0
    assert job.column_mapping["name"] == 1
    assert job.column_mapping["quantity"] == 2


def test_the_column_we_could_not_map_is_reported_rather_than_guessed(
    db: Session, admin: User, sample_bytes: bytes
) -> None:
    """This is what turns "harden the importer" into a config change: the
    operator can read which heading went unmapped and tell us the spelling."""
    job = _run(db, admin, sample_bytes)
    assert job.unmapped_headers == [build_sample.UNMAPPED_HEADER]


def test_indian_money_and_percent_strings_are_parsed(
    db: Session, admin: User, sample_bytes: bytes
) -> None:
    _run(db, admin, sample_bytes)
    product = db.execute(
        select(Product).where(func.lower(Product.sku) == "ksb-eta-65-200")
    ).scalar_one()
    assert product.purchase_cost == 12_500_000  # ₹1,25,000.00
    assert product.gst_rate_bp == 1800  # "18%"


def test_suppliers_and_categories_are_created_by_name(
    db: Session, admin: User, sample_bytes: bytes
) -> None:
    _run(db, admin, sample_bytes)
    supplier = db.execute(
        select(Supplier).where(func.lower(Supplier.name) == "ksb pumps ltd")
    ).scalar_one()
    category = db.execute(
        select(Category).where(func.lower(Category.name) == "centrifugal pumps")
    ).scalar_one()
    assert supplier.id and category.id


def test_a_blank_supplier_leaves_the_product_untagged(
    db: Session, admin: User, sample_bytes: bytes
) -> None:
    _run(db, admin, sample_bytes)
    product = db.execute(select(Product).where(Product.sku == "LJ-COUP-10")).scalar_one()
    assert product.supplier_id is None


def test_the_second_row_with_the_same_sku_is_an_update(
    db: Session, admin: User, sample_bytes: bytes
) -> None:
    """Matched on lower(sku): a file that spells its own code in two cases must
    not produce two products."""
    _run(db, admin, sample_bytes)
    matches = (
        db.execute(select(Product).where(func.lower(Product.sku) == "ksb-eta-65-200"))
        .scalars()
        .all()
    )
    assert len(matches) == 1
    assert matches[0].name == "KSB Etanorm 65-200 Mk II"


def test_a_blank_cell_means_leave_it_alone(db: Session, admin: User, sample_bytes: bytes) -> None:
    """The rule the whole importer turns on. The duplicate SKU row has a blank
    price; a partial Tally export must not wipe every price in the catalogue."""
    _run(db, admin, sample_bytes)
    product = db.execute(
        select(Product).where(func.lower(Product.sku) == "ksb-eta-65-200")
    ).scalar_one()
    assert product.purchase_cost == 12_500_000
    assert product.gst_rate_bp == 1800


def test_quantities_go_through_the_stock_service(
    db: Session, admin: User, sample_bytes: bytes
) -> None:
    job = _run(db, admin, sample_bytes)
    product = db.execute(
        select(Product).where(func.lower(Product.sku) == "ksb-eta-65-200")
    ).scalar_one()
    inventory = db.execute(select(Inventory).where(Inventory.product_id == product.id)).scalar_one()
    assert inventory.quantity_on_hand == 20  # the later row's absolute figure

    movements = (
        db.execute(select(StockMovement).where(StockMovement.product_id == product.id))
        .scalars()
        .all()
    )
    assert [m.movement_type for m in movements] == [MovementType.IMPORT, MovementType.IMPORT]
    assert {m.reference_type for m in movements} == {ReferenceType.IMPORT}
    # The note carries the job id, so a movement can be traced to the upload.
    assert {m.note for m in movements} == {str(job.id)}


def test_the_ledger_still_explains_the_counters(
    db: Session, admin: User, sample_bytes: bytes
) -> None:
    _run(db, admin, sample_bytes)
    assert stock.reconcile(db) == []


# --------------------------------------------------------------------------- bad rows


def test_a_bad_row_rolls_back_only_itself(db: Session, admin: User, sample_bytes: bytes) -> None:
    """v2 stopped the whole import on the first bad cell, and the operator's
    only recourse was to fix the file and start over."""
    job = _run(db, admin, sample_bytes)

    assert db.execute(select(Product).where(Product.sku == "NEG-1")).first() is None
    assert job.status is ImportJobStatus.COMPLETED
    assert job.created_count == 2

    error = job.errors[0]
    assert error["row"] == build_sample.HEADER_ROW_INDEX + build_sample.DATA_ROW_COUNT + 1
    assert "negative" in error["message"]


def test_error_detail_is_capped_but_the_count_is_not(db: Session, admin: User) -> None:
    """A file where every row is wrong must not put 5,000 error objects in a
    JSONB column the browser then has to download."""
    bad_rows = IMPORT_MAX_STORED_ERRORS + 5
    job = _run(db, admin, build_sample.build_bulk(bad_rows, bad_every=1))

    assert job.error_count == bad_rows
    assert len(job.errors) == IMPORT_MAX_STORED_ERRORS


def test_a_file_with_no_header_fails_with_a_comprehensible_message(
    db: Session, admin: User, no_header_bytes: bytes
) -> None:
    job = _run(db, admin, no_header_bytes, filename="not-a-stock-file.xlsx")
    assert job.status is ImportJobStatus.FAILED
    assert "column headings" in job.message
    assert job.finished_at is not None


def test_a_file_that_is_not_a_workbook_fails_rather_than_raising(db: Session, admin: User) -> None:
    job = _run(db, admin, b"this is not a zip archive at all", filename="broken.xlsx")
    assert job.status is ImportJobStatus.FAILED
    assert "Excel workbook" in job.message


# --------------------------------------------------------------------------- progress


def test_progress_reaches_every_row_of_a_file_longer_than_one_commit_window(
    db: Session, admin: User
) -> None:
    """Longer than COMMIT_EVERY, so the mid-run commits are exercised: progress
    and the data it describes are written in the same transaction, and the
    poller never sees a count for rows that were rolled back."""
    row_count = runner.COMMIT_EVERY + 50
    job = _run(db, admin, build_sample.build_bulk(row_count))

    assert job.total_rows == row_count
    assert job.processed_rows == row_count
    assert job.created_count == row_count
    assert job.status is ImportJobStatus.COMPLETED
    assert stock.reconcile(db) == []


def test_total_rows_is_known_before_the_rows_are_processed(
    db: Session, admin: User, sample_bytes: bytes
) -> None:
    """`total_rows` is 0 until header detection finishes — that is the signal the
    progress bar uses to stay indeterminate instead of jumping 0% to 100%."""
    job = runner.create_job(db, filename="stock.xlsx", created_by_id=admin.id)
    assert job.total_rows == 0
    runner.run_import(job.id, sample_bytes, session_factory=lambda: nullcontext(db))
    db.refresh(job)
    assert job.total_rows == build_sample.DATA_ROW_COUNT


def test_a_job_abandoned_by_a_restart_is_failed_at_startup(db: Session, admin: User) -> None:
    """Otherwise the row says "running" forever and the client's poller never
    reaches a terminal status."""
    job = runner.create_job(db, filename="interrupted.xlsx", created_by_id=admin.id)
    job.status = ImportJobStatus.RUNNING
    job.started_at = datetime.now(UTC) - timedelta(hours=4)
    db.commit()

    assert runner.fail_stale_jobs(db) >= 1
    db.refresh(job)
    assert job.status is ImportJobStatus.FAILED
    assert "restarted" in job.message


def test_a_running_job_that_is_still_young_is_left_alone(db: Session, admin: User) -> None:
    job = runner.create_job(db, filename="in-flight.xlsx", created_by_id=admin.id)
    job.status = ImportJobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    db.commit()

    runner.fail_stale_jobs(db)
    db.refresh(job)
    assert job.status is ImportJobStatus.RUNNING


# --------------------------------------------------------------------------- the endpoints


def test_upload_returns_202_and_a_pollable_id(
    client: TestClient, db: Session, sample_bytes: bytes
) -> None:
    response = client.post(
        "/api/imports/products",
        files={"file": ("stock.xlsx", sample_bytes, "application/vnd.ms-excel")},
    )
    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"id", "status"}

    polled = client.get(f"/api/imports/{body['id']}")
    assert polled.status_code == 200
    assert polled.json()["filename"] == "stock.xlsx"


def test_the_upload_is_read_inside_the_request(
    client: TestClient, sample_bytes: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Starlette closes the UploadFile the moment the response is sent.

    A background task handed the file object itself fails with "I/O operation on
    closed file" — after the client has been told 202 and started polling, so
    the only symptom is a job that never leaves "pending". The worker therefore
    receives plain bytes, which is what this asserts.
    """
    captured: dict[str, object] = {}

    def _capture(job_id: object, data: object, **kwargs: object) -> None:
        captured["data"] = data

    monkeypatch.setattr(runner, "run_import", _capture)
    response = client.post(
        "/api/imports/products",
        files={"file": ("stock.xlsx", sample_bytes, "application/vnd.ms-excel")},
    )

    assert response.status_code == 202
    assert isinstance(captured["data"], bytes)
    assert captured["data"] == sample_bytes


@pytest.mark.parametrize("filename", ["stock.csv", "stock.xls", "stock.xlsx.exe", "stock"])
def test_only_excel_files_are_accepted(
    client: TestClient, sample_bytes: bytes, filename: str
) -> None:
    response = client.post(
        "/api/imports/products", files={"file": (filename, sample_bytes, "text/csv")}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_an_oversized_file_is_refused(client: TestClient) -> None:
    oversized = b"x" * (runner.MAX_UPLOAD_BYTES + 1)
    response = client.post(
        "/api/imports/products",
        files={"file": ("huge.xlsx", oversized, "application/vnd.ms-excel")},
    )
    assert response.status_code == 422
    assert "MB" in response.json()["error"]["message"]


def test_history_is_paginated_newest_first(client: TestClient, db: Session, admin: User) -> None:
    older = runner.create_job(db, filename="older.xlsx", created_by_id=admin.id)
    runner.create_job(db, filename="newer.xlsx", created_by_id=admin.id)
    # Both rows are inserted in one transaction, so server-side now() gives them
    # the same stamp; the age is set explicitly to test the ordering, not the clock.
    older.created_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()

    body = client.get("/api/imports", params={"page_size": 5}).json()
    assert set(body) == {"items", "total", "page", "page_size", "pages"}
    assert body["items"][0]["filename"] == "newer.xlsx"


def test_polling_an_unknown_job_is_a_not_found(client: TestClient) -> None:
    response = client.get("/api/imports/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_requires_a_session(db: Session, sample_bytes: bytes) -> None:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    try:
        anonymous = TestClient(fastapi_app)
        assert anonymous.get("/api/imports").status_code == 401
        assert (
            anonymous.post(
                "/api/imports/products", files={"file": ("s.xlsx", sample_bytes, "application/x")}
            ).status_code
            == 401
        )
    finally:
        fastapi_app.dependency_overrides.clear()


# --------------------------------------------------------------------------- template


def test_every_template_column_maps_to_a_distinct_field(client: TestClient) -> None:
    """The one file we ship must import cleanly. A synonym edit that broke it
    would otherwise be discovered by a client, not by CI."""
    response = client.get("/api/imports/template.xlsx")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]

    rows = runner.read_rows(response.content)
    index = headers.find_header_row(rows)
    assert index == 0
    mapping, unmapped = headers.map_headers(rows[0])

    assert unmapped == []
    assert set(mapping) == {field for _heading, field, _example, _width in template.COLUMNS}


def test_the_template_can_itself_be_imported(db: Session, admin: User) -> None:
    """The strongest form of the previous test: run the file we hand out."""
    job = _run(db, admin, template.build_template(), filename="template.xlsx")
    assert job.status is ImportJobStatus.COMPLETED
    assert job.error_count == 0
    assert job.created_count == 1
    assert stock.reconcile(db) == []
