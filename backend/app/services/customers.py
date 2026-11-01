"""Customer queries and mutations.

The near-twin of `suppliers`. Nothing references a customer yet — the modules
that will (quotations, orders, challans) are still to be built — so there is
no dependant count to carry and no reason to refuse a soft delete. When the
first of those lands, this is where the count and the refusal go, and
`suppliers.py` shows the shape: a correlated scalar subquery in the same
statement as the rows, never a per-row query.
"""

from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..errors import Conflict, NotFound
from ..models import Customer, CustomerBranch
from ..schemas.contacts import splice_first
from ..schemas.customer import (
    CustomerBranchCreate,
    CustomerBranchUpdate,
    CustomerCreate,
    CustomerUpdate,
)
from ..schemas.party import CUSTOMER_REQUIRED, PARTY_REQUIRED
from .like import LIKE_ESCAPE, contains
from .party import validate_party

# The sort keys the contract names. Anything else is a client bug, and falling
# back silently would hide it, so the router validates against these.
SORTS: dict[str, Any] = {
    "name": Customer.name.asc(),
    "-name": Customer.name.desc(),
    "created_at": Customer.created_at.asc(),
    "-created_at": Customer.created_at.desc(),
}


def _filtered(q: str | None, is_active: bool | None) -> Select[tuple[Customer]]:
    stmt = select(Customer)
    if q:
        # ilike with a leading % is answered by the gin_trgm index on name; a
        # Python-side filter would have to materialise the whole table.
        pattern = contains(q)
        stmt = stmt.where(
            or_(
                Customer.name.ilike(pattern, escape=LIKE_ESCAPE),
                Customer.code.ilike(pattern, escape=LIKE_ESCAPE),
                Customer.billing_city.ilike(pattern, escape=LIKE_ESCAPE),
                func.array_to_string(Customer.emails, " ").ilike(pattern, escape=LIKE_ESCAPE),
                func.array_to_string(Customer.phones, " ").ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    if is_active is not None:
        stmt = stmt.where(Customer.is_active.is_(is_active))
    return stmt


def list_customers(
    db: Session,
    *,
    q: str | None = None,
    is_active: bool | None = None,
    sort: str = "name",
    offset: int = 0,
    limit: int = 25,
) -> tuple[list[Customer], int]:
    stmt = _filtered(q, is_active)
    total = db.execute(
        select(func.count()).select_from(stmt.with_only_columns(Customer.id).subquery())
    ).scalar_one()
    # id as a tiebreak: without it two customers sharing a sort key can swap
    # places between page 1 and page 2, and the operator sees one of them twice.
    rows = (
        db.execute(
            stmt.options(selectinload(Customer.branches))
            .order_by(SORTS[sort], Customer.id.asc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def list_options(db: Session) -> list[Customer]:
    """Every active customer, unpaginated.

    A customer picker must offer every customer regardless of how the list
    beside it happens to be paged.
    """
    return list(
        db.execute(
            select(Customer).where(Customer.is_active.is_(True)).order_by(Customer.name.asc())
        )
        .scalars()
        .all()
    )


def get_customer(db: Session, customer_id: int) -> Customer:
    customer = db.execute(
        select(Customer)
        .where(Customer.id == customer_id)
        .options(selectinload(Customer.branches))
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if customer is None:
        raise NotFound(f"Customer {customer_id} was not found.", customer_id=customer_id)
    return customer


def _reject_duplicate_name(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    """Check before the insert as well as catching the IntegrityError after it.

    The check produces a message naming the customer; the unique index is what
    makes it correct under concurrency. Both, not either.
    """
    stmt = select(Customer.id).where(func.lower(Customer.name) == name.strip().lower())
    if exclude_id is not None:
        stmt = stmt.where(Customer.id != exclude_id)
    if db.execute(stmt).first() is not None:
        raise Conflict(f"A customer named '{name.strip()}' already exists.", name=name.strip())


def create_customer(db: Session, body: CustomerCreate) -> Customer:
    _reject_duplicate_name(db, body.name)
    values = validate_party(body.model_dump(), CUSTOMER_REQUIRED)
    customer = Customer(**{**values, "name": body.name.strip()})
    db.add(customer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(f"A customer named '{body.name.strip()}' already exists.") from exc
    return get_customer(db, customer.id)


def update_customer(db: Session, customer_id: int, body: CustomerUpdate) -> Customer:
    customer = get_customer(db, customer_id)
    changes = validate_party(
        body.model_dump(exclude_unset=True), CUSTOMER_REQUIRED, stored=customer
    )
    if changes.get("name") is not None:
        changes["name"] = changes["name"].strip()
        _reject_duplicate_name(db, changes["name"], exclude_id=customer_id)
    # A legacy single email/phone without its list replaces the first entry.
    for plural, single in (("emails", "email"), ("phones", "phone")):
        if changes.get(plural) is None and changes.get(single) is not None:
            changes[plural] = splice_first(list(getattr(customer, plural) or []), changes[single])
    for field, value in changes.items():
        if value is not None:
            setattr(customer, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("A customer with that name already exists.") from exc
    return get_customer(db, customer_id)


def deactivate_customer(db: Session, customer_id: int) -> None:
    """Soft delete. Nothing references customers yet, so nothing can refuse it."""
    customer = get_customer(db, customer_id)
    customer.is_active = False
    db.commit()


# --- branches --------------------------------------------------------------------


def _branch(db: Session, customer_id: int, branch_id: int) -> CustomerBranch:
    branch = db.get(CustomerBranch, branch_id)
    if branch is None or branch.customer_id != customer_id:
        raise NotFound(f"Branch {branch_id} was not found.", branch_id=branch_id)
    return branch


def create_branch(db: Session, customer_id: int, body: CustomerBranchCreate) -> Customer:
    """Add a branch. Its code is the customer's code plus the next BR number.

    The customer row is locked while the number is taken, so two branches added
    at once never get the same one; the counter never goes back, so a removed
    branch's number is not issued again.
    """
    parent = db.execute(
        select(Customer).where(Customer.id == customer_id).with_for_update()
    ).scalar_one_or_none()
    if parent is None:
        raise NotFound(f"Customer {customer_id} was not found.", customer_id=customer_id)
    values = validate_party(body.model_dump(), PARTY_REQUIRED)
    parent.branch_seq += 1
    db.add(
        CustomerBranch(
            customer_id=parent.id,
            seq=parent.branch_seq,
            code=f"{parent.code}-BR{parent.branch_seq:02d}",
            **values,
        )
    )
    db.commit()
    return get_customer(db, customer_id)


def update_branch(
    db: Session, customer_id: int, branch_id: int, body: CustomerBranchUpdate
) -> Customer:
    branch = _branch(db, customer_id, branch_id)
    changes = validate_party(body.model_dump(exclude_unset=True), PARTY_REQUIRED, stored=branch)
    for field, value in changes.items():
        if value is not None:
            setattr(branch, field, value)
    db.commit()
    return get_customer(db, customer_id)


def remove_branch(db: Session, customer_id: int, branch_id: int) -> None:
    """Soft delete: a quotation that named the branch still prints it."""
    _branch(db, customer_id, branch_id).is_active = False
    db.commit()
