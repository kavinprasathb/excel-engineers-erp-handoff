"""The blank workbook `GET /imports/template.xlsx` hands out.

Built from the header spellings `headers.py` maps most confidently, so the one
file we ship is guaranteed to import cleanly. `tests/test_imports.py` asserts
that every column here maps to a distinct canonical field — a synonym edit that
broke the template would otherwise only be discovered by a client.

One spelling is not the obvious one: the model column is headed **Size**, not
"Model Number", because "model number" is also an accepted spelling of *sku*
and the SKU column claims it first. Renaming the synonym would change how real
Tally exports are read, which is a worse trade than a slightly odd heading on
our own template.
"""

import io

# openpyxl ships no type stubs.
from openpyxl import Workbook  # type: ignore[import-untyped]
from openpyxl.styles import Alignment, Font  # type: ignore[import-untyped]
from openpyxl.utils import get_column_letter  # type: ignore[import-untyped]

# (heading, canonical field it maps to, example value, column width)
COLUMNS: tuple[tuple[str, str, object, int], ...] = (
    ("SKU", "sku", "KSB-ETA-65-200", 22),
    ("Name", "name", "KSB Etanorm 65-200", 34),
    ("Size", "model_number", "65-200", 14),
    ("Unit", "unit", "piece", 10),
    ("Supplier", "supplier_name", "KSB Pumps Ltd", 22),
    ("Category", "category_name", "Centrifugal Pumps", 22),
    ("Purchase Price", "purchase_cost", 42500, 16),
    ("Selling Price", "sell_price", 51000, 16),
    ("GST %", "gst_rate", 18, 10),
    ("HSN Code", "hsn_code", "84137010", 14),
    ("Quantity", "quantity", 12, 12),
)

FILENAME = "excel-engineers-product-import-template.xlsx"


def build_template() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Products"

    sheet.append([heading for heading, _field, _example, _width in COLUMNS])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="left")

    # One example row, so the operator can see that money is written in rupees
    # and GST as a percentage rather than guessing and having a row rejected.
    sheet.append([example for _heading, _field, example, _width in COLUMNS])

    for index, (_heading, _field, _example, width) in enumerate(COLUMNS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"

    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()
