"""Header detection and cell parsing — pure functions, no database.

These are the parts of the import that will meet the client's real Tally export
first, so they are tested hardest. Every case below is something a real
spreadsheet does.
"""

from decimal import Decimal

import pytest

from app.services.importer import headers, values
from app.services.importer.values import CellError

# --------------------------------------------------------------------------
# Header normalisation and mapping
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Closing_Stock (Nos.) ", "closing stock"),
        ("HSN/SAC", "hsn sac"),
        ("Purchase  Price", "purchase price"),
        ("Rate (Rs.)", "rate"),
        ("PARTICULARS", "particulars"),
        (None, ""),
        (12345, "12345"),
    ],
)
def test_normalise(raw: object, expected: str) -> None:
    assert headers.normalise(raw) == expected


def test_maps_a_tidy_header_row() -> None:
    row = ("Item Code", "Item Name", "Supplier", "Qty", "Purchase Price", "Selling Price")
    mapping, unmapped = headers.map_headers(row)
    assert mapping == {
        "sku": 0,
        "name": 1,
        "supplier_name": 2,
        "quantity": 3,
        "purchase_cost": 4,
        "sell_price": 5,
    }
    assert unmapped == []


def test_maps_tally_vocabulary() -> None:
    """Tally says Particulars and Closing Balance, not Name and Quantity."""
    mapping, _ = headers.map_headers(("Particulars", "Closing Balance", "Rate", "Value"))
    assert mapping["name"] == 0
    assert mapping["quantity"] == 1


def test_unmapped_columns_are_reported_not_ignored() -> None:
    """The operator needs to see what we could not understand."""
    _, unmapped = headers.map_headers(("Item Code", "Godown", "Batch No"))
    assert unmapped == ["Godown", "Batch No"]


def test_a_close_typo_still_maps() -> None:
    mapping, _ = headers.map_headers(("Item Code", "Qauntity"))
    assert mapping["quantity"] == 1


def test_an_unrelated_word_does_not_map() -> None:
    """The fuzzy threshold must not turn a guess into a mapping."""
    mapping, unmapped = headers.map_headers(("Item Code", "Date"))
    assert "quantity" not in mapping
    assert unmapped == ["Date"]


def test_first_column_wins_a_duplicate_field() -> None:
    """Two 'Rate' columns must not have the second overwrite the first."""
    mapping, unmapped = headers.map_headers(("Item Code", "Rate", "Rate"))
    assert mapping["purchase_cost"] == 1
    assert unmapped == ["Rate"]


def test_supplier_synonyms_still_accepted_despite_the_rename() -> None:
    """We call it a supplier; the client's file may well say Manufacturer."""
    for spelling in ("Supplier", "Manufacturer", "Make", "Brand", "Vendor"):
        mapping, _ = headers.map_headers(("Item Code", spelling))
        assert mapping.get("supplier_name") == 1, spelling


# --------------------------------------------------------------------------
# Finding the header row inside a real export
# --------------------------------------------------------------------------


def test_finds_the_header_below_a_letterhead() -> None:
    rows: list[tuple[object, ...]] = [
        ("Excel Engineers", None, None),
        ("Stock Summary", None, None),
        ("1-Apr-2026 to 31-Mar-2027", None, None),
        (None, None, None),
        ("Item Code", "Item Name", "Closing Stock"),
        ("KSB-1", "Etanorm 65-200", 4),
    ]
    assert headers.find_header_row(rows) == 4


def test_prefers_the_best_scoring_row_not_the_first_plausible_one() -> None:
    """A preamble line can match one field by accident; the real header
    matches several, so scoring beats first-match."""
    rows: list[tuple[object, ...]] = [
        ("Stock Summary by Group", None, None, None),
        ("Item Code", "Item Name", "Supplier", "Closing Stock"),
    ]
    assert headers.find_header_row(rows) == 1


def test_no_header_row_returns_none() -> None:
    rows: list[tuple[object, ...]] = [("some notes",), ("more prose",), (None,)]
    assert headers.find_header_row(rows) is None


def test_a_single_weak_match_is_not_a_header() -> None:
    rows: list[tuple[object, ...]] = [("Type of report", None), ("prose", None)]
    assert headers.find_header_row(rows) is None


def test_missing_required_needs_a_product_identifier() -> None:
    assert headers.missing_required({"quantity": 0}) == ["sku or name"]
    assert headers.missing_required({"sku": 0}) == []
    assert headers.missing_required({"name": 0}) == []


# --------------------------------------------------------------------------
# Cell values
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "paise"),
    [
        (1250, 125_000),
        (19.99, 1999),  # the float trap: 19.99 * 100 is 1998.9999... as binary
        ("1,25,000.00", 12_500_000),  # Indian digit grouping
        ("₹ 4,250.50", 425_050),
        ("Rs. 99", 9_900),
        ("INR1000", 100_000),
        (Decimal("0.01"), 1),
        (0, 0),
    ],
)
def test_to_paise(raw: object, paise: int) -> None:
    assert values.to_paise(raw, field="price") == paise


def test_money_never_loses_a_paisa_to_binary_floats() -> None:
    """Guards the specific bug: float arithmetic would give 1998 here."""
    assert values.to_paise(19.99, field="price") == 1999


def test_negative_money_is_refused() -> None:
    with pytest.raises(CellError, match="cannot be negative"):
        values.to_paise("-5", field="price")


@pytest.mark.parametrize("raw", ["n/a", "TBC", "-", "abc"])
def test_unreadable_money_names_the_field_and_the_value(raw: str) -> None:
    with pytest.raises(CellError) as exc:
        values.to_paise(raw, field="Selling price")
    assert "Selling price" in str(exc.value)
    assert raw in str(exc.value)


@pytest.mark.parametrize(("raw", "qty"), [(4, 4), ("4", 4), (4.0, 4), ("1,200", 1200), (0, 0)])
def test_to_quantity(raw: object, qty: int) -> None:
    assert values.to_quantity(raw) == qty


def test_fractional_quantity_is_an_error_not_a_truncation() -> None:
    """Tally exports fractions for weight-based items. Silently flooring that
    would quietly lose stock; the operator should see it."""
    with pytest.raises(CellError, match="whole number"):
        values.to_quantity(2.5)


def test_negative_quantity_is_refused() -> None:
    with pytest.raises(CellError, match="cannot be negative"):
        values.to_quantity(-3)


@pytest.mark.parametrize(
    ("raw", "bp"),
    [
        (18, 1800),
        ("18", 1800),
        ("18%", 1800),
        (0.18, 1800),
        (Decimal("0.5"), 5000),  # a bare fraction is a percentage-formatted cell
        (0, 0),
        (5, 500),
    ],
)
def test_to_basis_points(raw: object, bp: int) -> None:
    assert values.to_basis_points(raw) == bp


def test_gst_above_a_hundred_percent_is_refused() -> None:
    with pytest.raises(CellError, match="between 0 and 100"):
        values.to_basis_points(180)


def test_quarter_percent_slab_survives() -> None:
    """0.25% is a real GST slab and is exactly why the column is basis points
    rather than an integer percentage."""
    assert values.to_basis_points("0.25%") == 25


def test_a_bare_fraction_is_read_as_a_percentage_formatted_cell() -> None:
    """The documented, deliberate ambiguity.

    A cell holding 0.25 with no percent sign is far more likely to be a
    percentage-formatted 25% than the 0.25% diamond slab, so that is how it is
    read. Sub-1% rates must carry an explicit "%" to be unambiguous — which is
    why the error messages name the field and the raw value.
    """
    assert values.to_basis_points(Decimal("0.25")) == 2500
    assert values.to_basis_points("0.25%") == 25


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_blank_detection(raw: object) -> None:
    assert values.is_blank(raw)


def test_blank_is_distinct_from_zero() -> None:
    """Blank means 'leave unchanged'; zero means 'set it to zero'. Conflating
    them lets a partial export wipe every price in the catalogue."""
    assert not values.is_blank(0)
    assert values.to_paise(0, field="price") == 0


def test_numeric_sku_does_not_arrive_with_a_trailing_point_zero() -> None:
    """Excel hands back 1234.0 for a bare number; no part code ends in .0."""
    assert values.to_text(1234.0) == "1234"


def test_text_is_trimmed_and_truncated() -> None:
    assert values.to_text("  Etanorm  ") == "Etanorm"
    assert values.to_text("x" * 300, max_length=255) == "x" * 255


def test_accounting_negative_is_understood() -> None:
    with pytest.raises(CellError, match="cannot be negative"):
        values.to_paise("(1,200)", field="price")
