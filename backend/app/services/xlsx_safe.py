"""Spreadsheet cells a user typed must never run as formulas.

A customer named "=HYPERLINK(...)" or "+cmd|..." is text in our database but
a formula to Excel. Every openpyxl export appends through `append_safe`, which
stores such values as plain strings with the quote prefix Excel itself uses
for "this is text", so the cell shows exactly what was typed and never runs.
"""

from collections.abc import Iterable
from typing import Any

FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def is_risky(value: object) -> bool:
    return isinstance(value, str) and value.startswith(FORMULA_TRIGGERS)


def append_safe(ws: Any, values: Iterable[Any]) -> None:
    """`ws.append(values)`, with formula-looking text neutralised."""
    row = list(values)
    ws.append(row)
    for cell, value in zip(ws[ws.max_row], row, strict=False):
        if is_risky(value):
            cell.value = value
            cell.data_type = "s"
            cell.quotePrefix = True
