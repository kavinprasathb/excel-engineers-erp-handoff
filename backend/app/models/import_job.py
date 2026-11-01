from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..constants import ImportJobStatus
from .base import Base
from .types import StrEnumType


class ImportJob(Base):
    """State of one spreadsheet import, polled by the browser for the progress bar.

    `column_mapping` and `unmapped_headers` are persisted and shown in the UI.
    That is what turns "harden the importer against the client's real Tally
    export" into a config change: upload it, read which columns went unmapped,
    extend the synonym table.
    """

    __tablename__ = "import_jobs"

    # UUID so the id can go to the client without leaking a row count.
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, server_default="products")
    status: Mapped[ImportJobStatus] = mapped_column(
        StrEnumType(ImportJobStatus, 20),
        nullable=False,
        server_default=ImportJobStatus.PENDING.value,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # NB: these are JSONB. SQLAlchemy does not track in-place mutation, so
    # always reassign (job.errors = job.errors + [...]), never .append().
    errors: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    column_mapping: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    unmapped_headers: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    header_row_index: Mapped[int | None] = mapped_column(Integer)

    message: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
