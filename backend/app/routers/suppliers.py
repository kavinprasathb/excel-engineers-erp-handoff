"""Suppliers: the companies we buy from.

`/suppliers/options` is declared before `/suppliers/{id}` on purpose — FastAPI
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
from ..schemas.contact_import import ImportCommitResult, ImportPreview, SupplierImportCommit
from ..schemas.supplier import (
    SupplierBranchCreate,
    SupplierBranchUpdate,
    SupplierCreate,
    SupplierOption,
    SupplierOut,
    SupplierUpdate,
)
from ..services import contact_import
from ..services import suppliers as service

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

SupplierSort = Literal["name", "-name", "created_at", "-created_at"]


def _out(supplier: object, product_count: int) -> SupplierOut:
    return SupplierOut.model_validate(supplier).model_copy(update={"product_count": product_count})


@router.get("", response_model=Page[SupplierOut])
def list_suppliers(
    q: str | None = Query(default=None, max_length=200),
    is_active: bool | None = None,
    sort: SupplierSort = "name",
    page: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page[SupplierOut]:
    rows, total = service.list_suppliers(
        db, q=q, is_active=is_active, sort=sort, offset=page.offset, limit=page.limit
    )
    return Page.build(
        [_out(supplier, count) for supplier, count in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/options", response_model=list[SupplierOption])
def supplier_options(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[SupplierOption]:
    """Unpaginated and active-only.

    The inventory page's inline supplier dropdown reads this. Deriving it from
    the paged list would silently offer only the suppliers on the current page.
    """
    return [SupplierOption.model_validate(s) for s in service.list_options(db)]


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(
    body: SupplierCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SupplierOut:
    supplier, count = service.create_supplier(db, body)
    return _out(supplier, count)


MAX_IMPORT_BYTES = 10 * 1024 * 1024


@router.post("/import/preview", response_model=ImportPreview)
async def import_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ImportPreview:
    """Parse an .xlsx or .pdf into proposed suppliers. Writes nothing."""
    filename = PurePath(file.filename or "upload").name
    data = await file.read(MAX_IMPORT_BYTES + 1)
    if len(data) > MAX_IMPORT_BYTES:
        raise ValidationFailed("That file is larger than the 10 MB limit.")
    if not data:
        raise ValidationFailed("That file is empty.")
    return ImportPreview.model_validate(
        contact_import.preview(db, kind="supplier", filename=filename, data=data)
    )


@router.post("/import/commit", response_model=ImportCommitResult, status_code=201)
def import_commit(
    body: SupplierImportCommit,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ImportCommitResult:
    """Create every reviewed record in one transaction."""
    created = contact_import.commit(db, kind="supplier", bodies=list(body.records))
    return ImportCommitResult(created=created)


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SupplierOut:
    supplier, count = service.get_supplier(db, supplier_id)
    return _out(supplier, count)


@router.patch("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    body: SupplierUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SupplierOut:
    supplier, count = service.update_supplier(db, supplier_id, body)
    return _out(supplier, count)


@router.delete(
    "/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(owner_only)]
)
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    """Soft delete. A supplier with products is refused, not cascaded."""
    service.deactivate_supplier(db, supplier_id)


# --- branches --------------------------------------------------------------------


@router.post(
    "/{supplier_id}/branches", response_model=SupplierOut, status_code=status.HTTP_201_CREATED
)
def create_branch(
    supplier_id: int,
    body: SupplierBranchCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SupplierOut:
    """Add a branch; answers with the supplier and all its branches."""
    supplier, count = service.create_branch(db, supplier_id, body)
    return _out(supplier, count)


@router.patch("/{supplier_id}/branches/{branch_id}", response_model=SupplierOut)
def update_branch(
    supplier_id: int,
    branch_id: int,
    body: SupplierBranchUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SupplierOut:
    supplier, count = service.update_branch(db, supplier_id, branch_id, body)
    return _out(supplier, count)


@router.delete(
    "/{supplier_id}/branches/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(owner_only)],
)
def delete_branch(
    supplier_id: int,
    branch_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    """Soft delete, like the supplier itself."""
    service.remove_branch(db, supplier_id, branch_id)
