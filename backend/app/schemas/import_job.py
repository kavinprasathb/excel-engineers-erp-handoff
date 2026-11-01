"""The import job as the browser's poller sees it.

Every counter is present from the first poll — `total_rows` is 0 until header
detection finishes, which is the signal the progress bar uses to stay
indeterminate rather than jumping from 0% to 100%.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ..constants import ImportJobStatus


class ImportJobAccepted(BaseModel):
    """The 202 body: just enough to start polling."""

    id: UUID
    status: ImportJobStatus


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ImportJobStatus
    filename: str
    total_rows: int
    processed_rows: int
    created_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    # Capped at IMPORT_MAX_STORED_ERRORS; `error_count` stays the true total.
    errors: list[dict[str, Any]]
    column_mapping: dict[str, int]
    unmapped_headers: list[str]
    header_row_index: int | None = None
    message: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


__all__ = ["ImportJobAccepted", "ImportJobOut"]
