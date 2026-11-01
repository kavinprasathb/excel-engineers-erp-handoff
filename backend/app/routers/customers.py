"""Customers: the companies we sell to.

`/customers/options` is declared before `/customers/{id}` on purpose — FastAPI
matches in declaration order, and the other way round "options" is read as an
id and every dropdown gets a 422.
"""

from pathlib import PurePath
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import Pagination, get_current_user, get_pagination, owner_only
from ..errors import ValidationFailed
from ..models import User
from ..schemas.common import Page
from ..schemas.contact_import import CustomerImportCommit, ImportCommitResult, ImportPreview
from ..schemas.customer import (
    CustomerBranchCreate,
    CustomerBranchUpdate,
    CustomerCreate,
    CustomerOption,
    CustomerOut,
    CustomerUpdate,
)
from ..services import contact_import
from ..services import customers as service

router = APIRouter(prefix="/customers", tags=["customers"])

CustomerSort = Literal["name", "-name", "created_at", "-created_at"]


@router.get("", response_model=Page[CustomerOut])
def list_customers(
    q: str | None = Query(default=None, max_length=200),
    is_active: bool | None = None,
    sort: CustomerSort = "name",
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[CustomerOut]:
    rows, total = service.list_customers(
        db, q=q, is_active=is_active, sort=sort, offset=page.offset, limit=page.limit
    )
    return Page.build(
        [CustomerOut.model_validate(c) for c in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/options", response_model=list[CustomerOption])
def customer_options(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CustomerOption]:
    """Unpaginated and active-only.

    A customer picker reads this. Deriving it from the paged
    list would silently offer only the customers on the current page.
    """
    return [CustomerOption.model_validate(c) for c in service.list_options(db)]


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    body: CustomerCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CustomerOut:
    return CustomerOut.model_validate(service.create_customer(db, body))


MAX_IMPORT_BYTES = 10 * 1024 * 1024


@router.post("/import/preview", response_model=ImportPreview)
async def import_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ImportPreview:
    """Parse an .xlsx or .pdf into proposed customers. Writes nothing."""
    filename = PurePath(file.filename or "upload").name
    data = await file.read(MAX_IMPORT_BYTES + 1)
    if len(data) > MAX_IMPORT_BYTES:
        raise ValidationFailed("That file is larger than the 10 MB limit.")
    if not data:
        raise ValidationFailed("That file is empty.")
    return ImportPreview.model_validate(
        contact_import.preview(db, kind="customer", filename=filename, data=data)
    )


@router.post("/import/commit", response_model=ImportCommitResult, status_code=201)
def import_commit(
    body: CustomerImportCommit,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ImportCommitResult:
    """Create every reviewed record in one transaction."""
    created = contact_import.commit(db, kind="customer", bodies=list(body.records))
    return ImportCommitResult(created=created)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CustomerOut:
    return CustomerOut.model_validate(service.get_customer(db, customer_id))


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CustomerOut:
    return CustomerOut.model_validate(service.update_customer(db, customer_id, body))


@router.delete(
    "/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(owner_only)]
)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    """Soft delete."""
    service.deactivate_customer(db, customer_id)


# --- branches --------------------------------------------------------------------


@router.post(
    "/{customer_id}/branches", response_model=CustomerOut, status_code=status.HTTP_201_CREATED
)
def create_branch(
    customer_id: int,
    body: CustomerBranchCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CustomerOut:
    """Add a branch; answers with the customer and all its branches."""
    return CustomerOut.model_validate(service.create_branch(db, customer_id, body))


@router.patch("/{customer_id}/branches/{branch_id}", response_model=CustomerOut)
def update_branch(
    customer_id: int,
    branch_id: int,
    body: CustomerBranchUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CustomerOut:
    return CustomerOut.model_validate(service.update_branch(db, customer_id, branch_id, body))


@router.delete(
    "/{customer_id}/branches/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(owner_only)],
)
def delete_branch(
    customer_id: int,
    branch_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    """Soft delete, like the customer itself."""
    service.remove_branch(db, customer_id, branch_id)
