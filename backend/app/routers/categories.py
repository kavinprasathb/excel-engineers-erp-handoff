"""Categories — flat, small, and unpaginated by contract."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, owner_only
from ..models import User
from ..schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from ..services import categories as service

router = APIRouter(prefix="/categories", tags=["categories"])


def _out(category: object, product_count: int) -> CategoryOut:
    return CategoryOut.model_validate(category).model_copy(update={"product_count": product_count})


@router.get("", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CategoryOut]:
    return [_out(category, count) for category, count in service.list_categories(db)]


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CategoryOut:
    category, count = service.create_category(db, body)
    return _out(category, count)


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    body: CategoryUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CategoryOut:
    category, count = service.update_category(db, category_id, body)
    return _out(category, count)


@router.delete(
    "/{category_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(owner_only)]
)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    """A real delete: its products keep existing with `category: null`."""
    service.delete_category(db, category_id)
