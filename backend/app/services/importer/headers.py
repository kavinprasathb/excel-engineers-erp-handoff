"""Working out what the columns of someone else's spreadsheet mean.

The client keeps stock in Tally and exports to Excel, so the file we receive is
not a form we designed: it has a letterhead, a report title, a date range, then
a header row somewhere around row 4, with column names nobody agreed with us.

Two jobs here, both pure functions over cell values so they can be tested
without a database or a file:

  find_header_row  — locate the row that is actually the header
  map_headers      — decide which canonical field each column holds

Everything is deliberately conservative. A column we fail to map is recorded
and shown to the operator, who can tell us the spelling. A column we map
*wrongly* silently writes purchase prices into the selling price field, and
nobody notices until a quote goes out at cost. So when in doubt, do not map.
"""

import difflib
import re
from typing import Final

# Canonical field -> the spellings we accept for it, all pre-normalised.
#
# "manufacturer", "make" and "brand" stay here as *input* synonyms even though
# this codebase calls the entity a supplier: the rename is about our schema, not
# about refusing to read a file that says Manufacturer.
CANONICAL_FIELDS: Final[dict[str, set[str]]] = {
    "sku": {
        "sku",
        "item code",
        "itemcode",
        "product code",
        "code",
        "part no",
        "part number",
        "part code",
        "alias",
        "item alias",
        "stock item code",
        "model",
        "model no",
        "model number",
    },
    "name": {
        "name",
        "product name",
        "item name",
        "description",
        "particulars",
        "stock item name",
        "item",
        "item description",
        "material description",
    },
    "model_number": {"model", "model no", "model number", "type", "size"},
    "unit": {"unit", "uom", "units", "base unit", "unit of measure", "per"},
    "supplier_name": {
        "supplier",
        "supplier name",
        "vendor",
        "vendor name",
        "manufacturer",
        "make",
        "brand",
        "party",
        "party name",
        "company",
    },
    "category_name": {
        "category",
        "group",
        "stock group",
        "item group",
        "product type",
        "type",
        "class",
    },
    "purchase_cost": {
        "purchase price",
        "purchase cost",
        "cost",
        "cost price",
        "buying price",
        "purchase rate",
        "landed cost",
        "landing price",
        "landing cost",
        "rate",
    },
    "sell_price": {
        "selling price",
        "sale price",
        "sell price",
        "mrp",
        "list price",
        "selling rate",
        "sales rate",
        "price",
    },
    "gst_rate": {"gst", "gst %", "gst rate", "tax", "tax rate", "gst percentage"},
    "hsn_code": {"hsn", "hsn code", "hsn/sac", "hsn sac", "hsn number"},
    "quantity": {
        "quantity",
        "qty",
        "stock",
        "closing stock",
        "closing balance",
        "opening stock",
        "opening balance",
        "balance",
        "on hand",
        "current stock",
        "closing qty",
        "stock qty",
    },
}

# A row must map at least this many columns before we believe it is the header.
# One is not enough: a letterhead line containing the word "Type" would win.
MIN_HEADER_MATCHES: Final = 2

# How far into the sheet to look. Tally preambles are short; beyond this we are
# almost certainly reading data rows.
MAX_HEADER_SCAN_ROWS: Final = 25

# Fuzzy matching threshold. Deliberately high — see the module docstring. At
# 0.85 "qauntity" still matches "quantity" but "rate" does not reach "date".
FUZZY_CUTOFF: Final = 0.85

# Some spellings are ambiguous across fields ("rate" could be cost or selling
# price; "type" could be a category or a model). When a header matches more than
# one field, the field earlier in this order wins.
_PRIORITY: Final[tuple[str, ...]] = (
    "sku",
    "name",
    "quantity",
    "supplier_name",
    "category_name",
    "purchase_cost",
    "sell_price",
    "unit",
    "hsn_code",
    "gst_rate",
    "model_number",
)

_TRAILING_UNITS = re.compile(r"\s*\((?:rs|inr|₹|nos|qty)\.?\)\s*$")
_PUNCT = re.compile(r"[.:_\-/\\]+")
_WS = re.compile(r"\s+")


def normalise(header: object) -> str:
    """Reduce a header cell to the form used for matching.

    Lowercase, strip punctuation and a trailing unit hint, collapse whitespace.
    `"  Closing_Stock (Nos.) "` becomes `"closing stock"`.
    """
    if header is None:
        return ""
    text = str(header).strip().lower()
    text = _TRAILING_UNITS.sub("", text)
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


def _match_field(normalised: str) -> str | None:
    """Which canonical field, if any, this header names."""
    if not normalised:
        return None

    exact = [field for field in _PRIORITY if normalised in CANONICAL_FIELDS[field]]
    if exact:
        return exact[0]

    # Only now, and only close matches: this catches typos, not guesses.
    for field in _PRIORITY:
        if difflib.get_close_matches(normalised, CANONICAL_FIELDS[field], n=1, cutoff=FUZZY_CUTOFF):
            return field
    return None


def map_headers(row: tuple[object, ...]) -> tuple[dict[str, int], list[str]]:
    """Map one row of header cells.

    Returns `(field -> column index, unmapped header texts)`. The first column
    claiming a field keeps it, so a sheet with two "Rate" columns does not have
    the second silently overwrite the first.

    The unmapped list is persisted on the import job and shown in the UI. That
    is what makes adapting to a new export format a matter of adding a synonym
    rather than debugging.
    """
    mapping: dict[str, int] = {}
    unmapped: list[str] = []

    for index, cell in enumerate(row):
        normalised = normalise(cell)
        if not normalised:
            continue
        field = _match_field(normalised)
        if field is None:
            unmapped.append(str(cell).strip())
        elif field not in mapping:
            mapping[field] = index
        else:
            unmapped.append(str(cell).strip())

    return mapping, unmapped


def score_row(row: tuple[object, ...]) -> int:
    """How many canonical fields this row appears to name."""
    return len(map_headers(row)[0])


def find_header_row(rows: list[tuple[object, ...]]) -> int | None:
    """Index of the most header-like row in the first `MAX_HEADER_SCAN_ROWS`.

    Scores every candidate rather than taking the first plausible one: a Tally
    preamble line such as "Stock Summary" sits above the real header and can
    match a field by accident, and the true header will always score higher.
    """
    best_index: int | None = None
    best_score = 0

    for index, row in enumerate(rows[:MAX_HEADER_SCAN_ROWS]):
        score = score_row(row)
        if score > best_score:
            best_index, best_score = index, score

    return best_index if best_score >= MIN_HEADER_MATCHES else None


def missing_required(mapping: dict[str, int]) -> list[str]:
    """Which required fields the mapping lacks.

    Only a product identifier is genuinely required: everything else can be
    defaulted, and refusing a whole file because it has no HSN column would be
    obstructive. A row needs a name or an SKU to be a product at all.
    """
    if "sku" in mapping or "name" in mapping:
        return []
    return ["sku or name"]
