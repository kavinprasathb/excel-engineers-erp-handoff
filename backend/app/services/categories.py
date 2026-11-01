"""Categories: a flat list with a product count, and a delete that never orphans.

`GET /categories` is unpaginated by contract — the list is a dozen rows and a
pager over it would be furniture.
"""

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..errors import Conflict, NotFound
from ..models import Category, Product
from ..schemas.category import CategoryCreate, CategoryUpdate

_product_count = (
    select(func.count(Product.id))
    .where(Product.category_id == Category.id)
    .correlate(Category)
    .scalar_subquery()
)


def list_categories(db: Session) -> list[tuple[Category, int]]:
    rows = db.execute(
        select(Category, _product_count.label("product_count")).order_by(Category.name.asc())
    ).all()
    return [(row[0], row[1]) for row in rows]


def get_category(db: Session, category_id: int) -> tuple[Category, int]:
    row = db.execute(
        select(Category, _product_count.label("product_count")).where(Category.id == category_id)
    ).first()
    if row is None:
        raise NotFound(f"Category {category_id} was not found.", category_id=category_id)
    return row[0], row[1]


def _reject_duplicate_name(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    stmt = select(Category.id).where(func.lower(Category.name) == name.strip().lower())
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise Conflict(f"A category named '{name.strip()}' already exists.", name=name.strip())


def create_category(db: Session, body: CategoryCreate) -> tuple[Category, int]:
    _reject_duplicate_name(db, body.name)
    category = Category(name=body.name.strip())
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(f"A category named '{body.name.strip()}' already exists.") from exc
    db.refresh(category)
    return category, 0


def update_category(db: Session, category_id: int, body: CategoryUpdate) -> tuple[Category, int]:
    category, _ = get_category(db, category_id)
    if body.name is not None:
        _reject_duplicate_name(db, body.name, exclude_id=category_id)
        category.name = body.name.strip()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("A category with that name already exists.") from exc
    return get_category(db, category_id)


def delete_category(db: Session, category_id: int) -> None:
    """A real delete: its products fall back to `category: null`.

    Written as an explicit UPDATE rather than left to the FK's ON DELETE SET
    NULL, so the consequence is visible in the file someone will read when they
    ask what deleting a category does to its products.
    """
    category, _ = get_category(db, category_id)
    db.execute(update(Product).where(Product.category_id == category_id).values(category_id=None))
    db.delete(category)
    db.commit()
