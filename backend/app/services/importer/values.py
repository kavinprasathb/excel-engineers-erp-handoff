"""Turning spreadsheet cells into the types the database wants.

Cells arrive as whatever Excel felt like: a float, an int, a Decimal, a string
with a rupee sign and Indian digit grouping, an empty string, or None. These
functions are total — they either return a clean value or raise `CellError`
with a message an operator can act on.

The one rule worth stating out loud: **money never touches a float**. Excel
happily hands us 19.99, and `19.99 * 100` is 1998.9999999999998, which rounds
to 1998 paise and loses a paisa on every line. Everything goes through Decimal.
"""

from decimal import Decimal, InvalidOperation
from typing import Final

# Characters that show up inside real Indian price cells and mean nothing
# numerically. Written as code points because Excel emits U+00A0 and U+202F
# in formatted numbers, and those are invisible — and indistinguishable from
# a plain space — in source.
_NOISE: Final = (
    0x20B9,  # rupee sign
    0x002C,  # comma
    0x0020,  # space
    0x00A0,  # no-break space
    0x202F,  # narrow no-break space
    0x0009,  # tab
)
_STRIP: Final = dict.fromkeys(_NOISE, None)
_PREFIXES: Final = ("rs.", "rs", "inr")


class CellError(ValueError):
    """A cell could not be read. The message is shown to the operator."""


def is_blank(value: object) -> bool:
    """Blank means 'leave whatever is already there'.

    This distinction matters: a partial Tally export that omits the price
    column must not wipe every price in the catalogue.
    """
    return value is None or (isinstance(value, str) and not value.strip())


def to_text(value: object, *, max_length: int | None = None) -> str:
    if is_blank(value):
        return ""
    text = str(value).strip()
    # Excel stores a bare number as a float, so an SKU of 1234 arrives as
    # "1234.0". Nobody's part number ends in .0.
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    return text[:max_length] if max_length else text


def _clean_number(value: object) -> str:
    text = str(value).strip().lower()
    for prefix in _PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.translate(_STRIP)
    # Accounting style: (1,200) means negative.
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    return text


def to_decimal(value: object, *, field: str) -> Decimal:
    if is_blank(value):
        raise CellError(f"{field} is empty")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, float):
        # str() of a float is the shortest repr that round-trips, which is what
        # the user typed; Decimal(float) would expose binary noise.
        return Decimal(str(value))

    text = _clean_number(value)
    if not text:
        raise CellError(f"{field} is empty")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise CellError(f"{field} '{value}' is not a number") from None


def to_paise(value: object, *, field: str) -> int:
    """Rupees (however written) to integer paise."""
    amount = to_decimal(value, field=field)
    if amount < 0:
        raise CellError(f"{field} cannot be negative")
    paise = int((amount * 100).to_integral_value())
    if paise > 10**15:
        raise CellError(f"{field} is implausibly large")
    return paise


def to_quantity(value: object, *, field: str = "quantity") -> int:
    """A whole number of units.

    Tally exports fractional quantities for weight-based items; this app counts
    pieces, so a fraction is a real mismatch the operator should see rather
    than something to silently truncate.
    """
    amount = to_decimal(value, field=field)
    if amount != amount.to_integral_value():
        raise CellError(f"{field} '{value}' is not a whole number")
    quantity = int(amount)
    if quantity < 0:
        raise CellError(f"{field} cannot be negative")
    if quantity > 10**7:
        raise CellError(f"{field} is implausibly large")
    return quantity


def to_basis_points(value: object, *, field: str = "GST rate") -> int:
    """A tax rate to basis points: 18, "18%" and 0.18 all mean 1800.

    Values at or below 1 are read as fractions, which is how a percentage
    formatted cell reaches us. That makes a genuine 1% rate ambiguous — but
    Indian GST has no 1% slab, while fraction-formatted cells are common.
    """
    if is_blank(value):
        raise CellError(f"{field} is empty")

    text = str(value).strip()
    had_percent = text.endswith("%")
    amount = to_decimal(text.rstrip("%") if had_percent else value, field=field)

    if not had_percent and 0 < amount <= 1:
        amount *= 100

    if amount < 0 or amount > 100:
        raise CellError(f"{field} '{value}' is not between 0 and 100")
    return int((amount * 100).to_integral_value())
