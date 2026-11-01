"""Running one spreadsheet import to completion, in the background.

The shape of this module is dictated by what the browser is doing while it
runs: polling `GET /imports/{id}` every second and drawing a progress bar. That
turns three otherwise-invisible details into requirements.

**The worker owns its own session.** The request's session is closed the moment
the response is sent; a background task holding it would fail on its first
statement. So `run_import` opens one from `SessionLocal` and closes it itself.

**Progress and data commit together.** The poller must never see
`processed_rows = 400` for rows that a later rollback threw away, so the
counters are written in the same transaction as the products they describe —
every `COMMIT_EVERY` rows, not on a timer.

**One bad row is one bad row.** Each row runs inside a savepoint; a failure
rolls back that savepoint, appends to `job.errors`, and the run continues. An
import of 1,300 rows that dies on row 12 because a quantity said "n/a" is how
v2's importer behaved, and the operator's only recourse was to fix the file and
start again.

`job.errors` is JSONB. SQLAlchemy does not track in-place mutation of a JSONB
list, so every write here reassigns it. `.append()` looks like it works and
then silently does not persist.
"""

import io
import logging
import zipfile
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

# openpyxl ships no type stubs.
from openpyxl import load_workbook  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...constants import (
    IMPORT_MAX_STORED_ERRORS,
    IMPORT_STALE_MINUTES,
    ImportJobStatus,
    ReferenceType,
)
from ...db import SessionLocal
from ...errors import AppError
from ...models import Category, ImportJob, Inventory, Product, Supplier
from .. import stock
from . import headers, values

log = logging.getLogger(__name__)

# How often progress reaches the database. Small enough that the bar moves,
# large enough that a 5,000-row file is not 5,000 commits.
COMMIT_EVERY = 200

SessionFactory = Callable[[], AbstractContextManager[Session]]

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = (".xlsx", ".xlsm")
# An .xlsx is a zip: 10 MB on the wire can inflate to gigabytes. Checked from
# the zip directory before openpyxl touches a byte of it.
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
# Data rows, not counting the header. The whole catalogue is a few thousand.
MAX_ROWS = 20_000


class ImportAborted(Exception):
    """The file as a whole cannot be read. Ends the job; never raised per row."""


def create_job(db: Session, *, filename: str, created_by_id: int | None) -> ImportJob:
    """Persist the job before the response returns, so the id we hand out resolves.

    Committed here rather than in the worker: the client starts polling as soon
    as it has the id, and a job that does not exist yet is indistinguishable to
    it from one that failed.
    """
    job = ImportJob(
        kind="products",
        status=ImportJobStatus.PENDING,
        filename=filename[:255],
        created_by_id=created_by_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def fail_stale_jobs(db: Session) -> int:
    """Mark abandoned `running` jobs failed. Called once at startup.

    A restart mid-import leaves a row that says "running" and will never
    change, and the client's poller waits for a terminal status forever.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=IMPORT_STALE_MINUTES)
    stale = (
        db.execute(
            select(ImportJob).where(
                ImportJob.status == ImportJobStatus.RUNNING,
                func.coalesce(ImportJob.started_at, ImportJob.created_at) < cutoff,
            )
        )
        .scalars()
        .all()
    )
    for job in stale:
        job.status = ImportJobStatus.FAILED
        job.message = "The server restarted while this import was running."
        job.finished_at = datetime.now(UTC)
    if stale:
        db.commit()
    return len(stale)


# ---------------------------------------------------------------------------
# Reading the file
# ---------------------------------------------------------------------------


def read_rows(data: bytes) -> list[tuple[Any, ...]]:
    """Every cell value in the first worksheet.

    read_only keeps a large export off the heap; data_only asks for the cached
    result of a formula rather than the formula text, because "=B2*1.18" is not
    a price.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            inflated = sum(info.file_size for info in archive.infolist())
    except (zipfile.BadZipFile, ValueError) as exc:
        raise ImportAborted(
            "That file could not be opened as an Excel workbook. "
            "Please upload the original .xlsx export."
        ) from exc
    if inflated > MAX_UNCOMPRESSED_BYTES:
        raise ImportAborted(
            "That workbook is too large to import. Please split it into smaller files."
        )
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a wide variety for a bad file
        raise ImportAborted(
            "That file could not be opened as an Excel workbook. "
            "Please upload the original .xlsx export."
        ) from exc
    try:
        sheet = workbook.worksheets[0]
        rows: list[tuple[Any, ...]] = []
        for row in sheet.iter_rows(values_only=True):
            if len(rows) > MAX_ROWS:  # the header plus MAX_ROWS data rows
                raise ImportAborted(
                    f"That sheet has more than {MAX_ROWS:,} rows. "
                    "Please split it into smaller files."
                )
            rows.append(tuple(row))
        return rows
    finally:
        workbook.close()


def _resolve_named(db: Session, model: Any, name: str, cache: dict[str, int]) -> int:
    """Find a supplier or category by name, creating it if it is new.

    Auto-creation is the right default for an import: the alternative is
    rejecting rows for a supplier the operator obviously has, and asking them
    to type thirty names into a form before trying again. The name cache keeps
    a 2,000-row file from issuing 2,000 identical lookups.
    """
    key = name.strip().lower()
    if key in cache:
        return cache[key]

    found = db.execute(select(model.id).where(func.lower(model.name) == key)).scalar_one_or_none()
    if found is None:
        row = model(name=name.strip())
        db.add(row)
        db.flush()
        found = row.id
    cache[key] = int(found)
    return cache[key]


class _RowResult:
    """What one row did, so the counters can be updated after its savepoint closes."""

    __slots__ = ("created", "skipped", "updated")

    def __init__(
        self, *, created: bool = False, updated: bool = False, skipped: bool = False
    ) -> None:
        self.created = created
        self.updated = updated
        self.skipped = skipped


def _apply_row(
    db: Session,
    *,
    job: ImportJob,
    row: tuple[Any, ...],
    mapping: dict[str, int],
    caches: dict[str, dict[str, int]],
    actor_id: int | None,
) -> _RowResult:
    """One spreadsheet row. Raises `values.CellError` for anything the operator must fix."""

    def cell(field: str) -> Any:
        index = mapping.get(field)
        return None if index is None or index >= len(row) else row[index]

    sku = values.to_text(cell("sku"), max_length=100)
    name = values.to_text(cell("name"), max_length=255)
    if not sku and not name:
        # A completely blank row, or a Tally total line with only numbers on
        # it. Neither is an error worth showing anybody.
        return _RowResult(skipped=True)

    product = None
    if sku:
        product = db.execute(
            select(Product).where(func.lower(Product.sku) == sku.lower())
        ).scalar_one_or_none()
    if product is None and name:
        product = db.execute(
            select(Product).where(func.lower(Product.name) == name.lower())
        ).scalar_one_or_none()

    created = product is None
    if product is None:
        product = Product(sku=sku or name[:100], name=name or sku)
        db.add(product)

    # Everything below is "set only if the cell said something". A blank cell
    # means leave the existing value alone: a partial export that omits the
    # price column must not wipe every price in the catalogue.
    if name and not created:
        product.name = name
    for field, column, length in (
        ("model_number", "model_number", 120),
        ("unit", "unit", 20),
        ("hsn_code", "hsn_code", 15),
    ):
        raw = cell(column)
        if not values.is_blank(raw):
            setattr(product, field, values.to_text(raw, max_length=length))

    if not values.is_blank(cell("purchase_cost")):
        product.purchase_cost = values.to_paise(cell("purchase_cost"), field="purchase price")
    if not values.is_blank(cell("sell_price")):
        product.sell_price = values.to_paise(cell("sell_price"), field="selling price")
    if not values.is_blank(cell("gst_rate")):
        product.gst_rate_bp = values.to_basis_points(cell("gst_rate"))

    supplier_name = values.to_text(cell("supplier_name"), max_length=200)
    if supplier_name:
        product.supplier_id = _resolve_named(db, Supplier, supplier_name, caches["supplier"])
    category_name = values.to_text(cell("category_name"), max_length=120)
    if category_name:
        product.category_id = _resolve_named(db, Category, category_name, caches["category"])

    db.flush()

    if created:
        db.add(Inventory(product_id=product.id))
        db.flush()

    if not values.is_blank(cell("quantity")):
        quantity = values.to_quantity(cell("quantity"))
        stock.set_on_hand(
            db,
            product_id=product.id,
            qty=quantity,
            ref=stock.StockRef(ReferenceType.IMPORT, note=str(job.id)),
            actor_id=actor_id,
        )

    return _RowResult(created=created, updated=not created)


def _record_error(
    job: ImportJob, *, row_number: int, message: str, column: str, value: Any
) -> None:
    """Append to the capped list and always increment the true total."""
    job.error_count += 1
    if len(job.errors) < IMPORT_MAX_STORED_ERRORS:
        # A new list assigned to the attribute, never `.append()`: JSONB
        # mutation in place is not tracked and would simply not persist.
        job.errors = [
            *job.errors,
            {
                "row": row_number,
                "column": column,
                "message": message,
                "value": None if value is None else str(value)[:120],
            },
        ]


def run_import(
    job_id: UUID,
    data: bytes,
    *,
    session_factory: SessionFactory = SessionLocal,
    actor_id: int | None = None,
) -> None:
    """The background job. Never raises: a crash here has no one to catch it.

    `session_factory` is a seam for the tests, which pass the fixture's
    transaction so the run is rolled back with everything else.
    """
    with session_factory() as db:
        job = db.get(ImportJob, job_id)
        if job is None:  # deleted between accepting the upload and starting
            return
        try:
            _run(db, job, data, actor_id=actor_id)
        except ImportAborted as exc:
            db.rollback()
            _finish(db, job, ImportJobStatus.FAILED, str(exc))
        except SQLAlchemyError:
            log.exception("Import %s failed", job_id)
            db.rollback()
            _finish(
                db,
                job,
                ImportJobStatus.FAILED,
                "The import stopped because of a database error. No partial file was left behind.",
            )


def _finish(db: Session, job: ImportJob, status: ImportJobStatus, message: str) -> None:
    job.status = status
    job.message = message
    job.finished_at = datetime.now(UTC)
    db.commit()


def _run(db: Session, job: ImportJob, data: bytes, *, actor_id: int | None) -> None:
    job.status = ImportJobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    # Committed immediately: the client is already polling, and a job stuck at
    # "pending" for the length of a 3,000-row parse looks like a hung server.
    db.commit()

    rows = read_rows(data)
    header_index = headers.find_header_row(rows)
    if header_index is None:
        raise ImportAborted(
            "No column headings were found in this file. The sheet needs a row "
            "naming the columns — at least an item code or a product name."
        )

    mapping, unmapped = headers.map_headers(rows[header_index])
    missing = headers.missing_required(mapping)
    if missing:
        raise ImportAborted(
            f"The heading row is missing {', '.join(missing)}. "
            "Download the template to see the column names this import accepts."
        )

    data_rows = rows[header_index + 1 :]
    job.header_row_index = header_index
    job.column_mapping = dict(mapping)
    job.unmapped_headers = list(unmapped)
    job.total_rows = len(data_rows)
    # The second commit: with total_rows known the progress bar can stop being
    # indeterminate, and it should do so before the first 200 rows land.
    db.commit()

    caches: dict[str, dict[str, int]] = {"supplier": {}, "category": {}}

    for offset, row in enumerate(data_rows):
        # 1-based, and the header row is above this one: the number the
        # operator sees in Excel's left margin.
        row_number = header_index + offset + 2
        # Flush the counter updates from the previous iteration *before* the
        # savepoint opens: inside it, a rollback would take them with it.
        db.flush()
        try:
            with db.begin_nested():
                result = _apply_row(
                    db, job=job, row=row, mapping=mapping, caches=caches, actor_id=actor_id
                )
        except values.CellError as exc:
            _record_error(job, row_number=row_number, message=str(exc), column="", value=None)
        except AppError as exc:  # insufficient stock, missing inventory row
            _record_error(job, row_number=row_number, message=exc.message, column="", value=None)
        except SQLAlchemyError as exc:
            # A constraint the file violated — a duplicate SKU under a
            # different name, an over-long value. One row's problem, not the
            # file's, so it is reported and the run continues.
            log.info("Import %s row %s rejected: %s", job.id, row_number, exc)
            _record_error(
                job,
                row_number=row_number,
                message="This row was rejected by the database and was not imported.",
                column="",
                value=None,
            )
        else:
            job.created_count += int(result.created)
            job.updated_count += int(result.updated)
            job.skipped_count += int(result.skipped)

        job.processed_rows += 1
        if job.processed_rows % COMMIT_EVERY == 0:
            # Data and progress in one commit. Separately, the poller could see
            # a count for rows that were rolled back.
            db.commit()

    _finish(db, job, ImportJobStatus.COMPLETED, "")
