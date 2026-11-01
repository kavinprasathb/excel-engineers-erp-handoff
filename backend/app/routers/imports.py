"""Uploading a spreadsheet, and watching it run.

Two things here are load-bearing and easy to get wrong.

**The bytes are read inside the request.** Starlette closes an `UploadFile` as
soon as the response is sent, so a background task handed the `UploadFile`
itself fails with "I/O operation on closed file" — after the client has already
been told 202 and started polling. `await file.read()` happens here; the worker
receives plain bytes.

**Stale jobs are swept at startup.** The router carries its own lifespan, which
FastAPI merges into the app's when the router is included. If the API restarts
mid-import, the row left saying "running" would never change and the browser's
poller would spin until someone closed the tab.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import PurePath
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, File, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..constants import ImportJobStatus
from ..db import SessionLocal, get_db
from ..deps import Pagination, get_current_user, get_pagination, owner_only
from ..errors import AppError, NotFound
from ..models import ImportJob, User
from ..schemas.common import Page
from ..schemas.import_job import ImportJobAccepted, ImportJobOut
from ..services.importer import runner, template

log = logging.getLogger(__name__)


class UnsupportedUpload(AppError):
    """The file is not one we can even try to read. Defined here rather than in
    errors.py for the same reason security.py defines its own: the error belongs
    with the code that raises it."""

    code = "validation_error"
    status = 422


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    with SessionLocal() as db:
        swept = runner.fail_stale_jobs(db)
    if swept:
        log.warning("Marked %s abandoned import job(s) as failed on startup", swept)
    yield


# Owner-only, all of it: an import writes purchase cost, which staff may
# neither see nor set, and a job's row errors can echo the costs back.
router = APIRouter(
    prefix="/imports",
    tags=["imports"],
    lifespan=_lifespan,
    dependencies=[Depends(owner_only)],
)


@router.get("/template.xlsx")
def download_template(_user: User = Depends(get_current_user)) -> Response:
    """A blank workbook with the headings this importer maps most confidently."""
    return Response(
        content=template.build_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{template.FILENAME}"'},
    )


@router.post("/products", response_model=ImportJobAccepted, status_code=status.HTTP_202_ACCEPTED)
async def import_products(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImportJobAccepted:
    filename = PurePath(file.filename or "upload.xlsx").name
    if PurePath(filename).suffix.lower() not in runner.ALLOWED_SUFFIXES:
        raise UnsupportedUpload(
            "Only Excel files (.xlsx or .xlsm) can be imported. "
            "If this is a CSV, open it in Excel and save it as .xlsx.",
            filename=filename,
        )

    # Read here, not in the worker: see the module docstring.
    data = await file.read()
    if len(data) > runner.MAX_UPLOAD_BYTES:
        raise UnsupportedUpload(
            f"That file is larger than the {runner.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            size=len(data),
        )
    if not data:
        raise UnsupportedUpload("That file is empty.")

    job = runner.create_job(db, filename=filename, created_by_id=user.id)
    background.add_task(runner.run_import, job.id, data, actor_id=user.id)
    return ImportJobAccepted(id=job.id, status=ImportJobStatus(job.status))


@router.get("", response_model=Page[ImportJobOut])
def list_imports(
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[ImportJobOut]:
    total = db.execute(select(func.count(ImportJob.id))).scalar_one()
    rows = (
        db.execute(
            select(ImportJob)
            .order_by(ImportJob.created_at.desc())
            .offset(page.offset)
            .limit(page.limit)
        )
        .scalars()
        .all()
    )
    return Page.build(
        [ImportJobOut.model_validate(job) for job in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/{job_id}", response_model=ImportJobOut)
def get_import(
    job_id: UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ImportJobOut:
    """The poll target. The client stops when `status` is terminal."""
    job = db.get(ImportJob, job_id)
    if job is None:
        raise NotFound("That import was not found.", job_id=str(job_id))
    # Expired so a poll during a run reads the worker's committed progress
    # rather than this session's snapshot of it.
    db.refresh(job)
    return ImportJobOut.model_validate(job)
