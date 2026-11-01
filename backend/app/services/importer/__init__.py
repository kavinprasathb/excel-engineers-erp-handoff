"""Reading someone else's spreadsheet.

`headers` and `values` are pure functions over cell values; `runner` is the
background job that uses them; `template` builds the blank workbook we hand
out. Nothing here imports a router, so the whole import path is testable
without an HTTP client.
"""

from . import headers, runner, template, values

__all__ = ["headers", "runner", "template", "values"]
