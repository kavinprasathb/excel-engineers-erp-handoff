"""Build the import test workbooks programmatically.

Checked-in binary fixtures rot: nobody can read a diff of an .xlsx, so when a
test starts failing there is no way to tell whether the file or the code
changed. Building them here means the awkward cases are *readable* — the row
that carries `₹1,25,000.00` is a line of Python with a comment on it.

Run as a script to write the files into this directory:

    uv run python -m tests.fixtures.build_sample
"""

import io
import pathlib
from typing import Any

from openpyxl import Workbook

HERE = pathlib.Path(__file__).resolve().parent
SAMPLE_PATH = HERE / "products_sample.xlsx"
NO_HEADER_PATH = HERE / "no_header.xlsx"

# A Tally export's letterhead: three rows above the real header, none of which
# names a field we recognise.
PREAMBLE: tuple[tuple[Any, ...], ...] = (
    ("Excel Engineers Pvt Ltd", None, None, None, None, None, None, None),
    ("Stock Summary", None, None, None, None, None, None, None),
    ("1-Apr-2026 to 30-Aug-2026", None, None, None, None, None, None, None),
)

# Mixed case, abbreviations, and one column ("Godown") we deliberately do not
# map — it should be reported to the operator, not guessed at.
HEADER: tuple[str, ...] = (
    "Item Code",
    "PRODUCT NAME",
    "Qty",
    "Supplier",
    "Purchase Rate",
    "GST %",
    "Godown",
    "Stock Group",
)

UNMAPPED_HEADER = "Godown"

DATA: tuple[tuple[Any, ...], ...] = (
    # Indian digit grouping, a rupee sign and a percent string — all of which
    # arrive as text, and none of which may touch a float on the way in.
    (
        "KSB-ETA-65-200",
        "KSB Etanorm 65-200",
        12,
        "KSB Pumps Ltd",
        "₹1,25,000.00",
        "18%",
        "Main",
        "Centrifugal Pumps",
    ),
    # Blank supplier: imports leave products untagged, which is what
    # has_supplier=false exists to find.
    ("LJ-COUP-10", "Lovejoy Coupling 10", 5, None, 250.5, 18, "Main", "Spares"),
    # A completely blank row. Skipped, never an error.
    (None, None, None, None, None, None, None, None),
    # The same SKU again in different case: an update, not a second product.
    # Its price and GST cells are blank, which must leave both unchanged.
    (
        "ksb-eta-65-200",
        "KSB Etanorm 65-200 Mk II",
        20,
        "KSB Pumps Ltd",
        None,
        None,
        "Main",
        None,
    ),
    # A negative quantity: one row's error, and the rest of the file still runs.
    ("NEG-1", "Impossible Stock", -4, "KSB Pumps Ltd", 100, 18, "Main", "Spares"),
)

HEADER_ROW_INDEX = len(PREAMBLE)
DATA_ROW_COUNT = len(DATA)


def _workbook(rows: tuple[tuple[Any, ...], ...]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Stock"
    for row in rows:
        sheet.append(list(row))
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def build_sample() -> bytes:
    return _workbook((*PREAMBLE, HEADER, *DATA))


def build_no_header() -> bytes:
    """A sheet with no heading row at all.

    Must fail with a message that tells the operator what is missing, rather
    than importing the first row as if it named the columns.
    """
    return _workbook(
        (
            ("some value", 1, "another"),
            ("more", 2, "values"),
        )
    )


def build_bulk(row_count: int, *, bad_every: int = 0) -> bytes:
    """A larger file, for the commit-cadence and error-cap tests."""
    rows: list[tuple[Any, ...]] = [HEADER]
    for index in range(row_count):
        bad = bad_every and index % bad_every == 0
        rows.append(
            (
                f"BULK-{index:04d}",
                f"Bulk product {index}",
                "not a number" if bad else index % 7,
                "Bulk Supplier",
                1000,
                18,
                "Main",
                "Bulk Group",
            )
        )
    return _workbook(tuple(rows))


if __name__ == "__main__":
    SAMPLE_PATH.write_bytes(build_sample())
    NO_HEADER_PATH.write_bytes(build_no_header())
    print(f"wrote {SAMPLE_PATH}\nwrote {NO_HEADER_PATH}")
