"""Plain-words descriptions of changes, and the activity log listing."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from ..models import (
    ActivityLog,
    Category,
    Customer,
    Order,
    Product,
    PurchaseOrder,
    Quotation,
    Supplier,
    User,
)
from .like import LIKE_ESCAPE, contains

IST = timezone(timedelta(hours=5, minutes=30))

# Which model a path parameter names, the label column, the area and the link.
_ENTITIES: dict[str, tuple[Any, str, str, str]] = {
    "quotation_id": (Quotation, "number", "Quotations", "/quotations/{id}"),
    "order_id": (Order, "number", "Orders", "/orders/{id}"),
    "po_id": (PurchaseOrder, "number", "Purchase orders", "/purchase-orders/{id}"),
    "product_id": (Product, "name", "Products", "/products"),
    "customer_id": (Customer, "name", "Customers", "/customers"),
    "supplier_id": (Supplier, "name", "Suppliers", "/suppliers"),
    "category_id": (Category, "name", "Products", "/products"),
    "user_id": (User, "full_name", "Staff", "/staff"),
}

# (method, route template) -> what happened, in plain words.
_ACTIONS: dict[tuple[str, str], str] = {
    ("POST", "/quotations"): "Created a quotation",
    ("PATCH", "/quotations/{quotation_id}"): "Edited quotation {label}",
    ("DELETE", "/quotations/{quotation_id}"): "Deleted quotation {label}",
    ("POST", "/quotations/{quotation_id}/revise"): "Started a negotiation on {label}",
    ("POST", "/quotations/{quotation_id}/status"): "Marked {label} {status}",
    ("POST", "/quotations/{quotation_id}/order"): "Created the order for {label}",
    ("POST", "/orders/{order_id}/recheck"): "Checked stock for {label}",
    ("POST", "/orders/{order_id}/deliver"): "Product Delivery done for {label}",
    ("POST", "/purchase-orders/{po_id}/supplier"): "Set the supplier on {label}",
    ("POST", "/purchase-orders/{po_id}/sent"): "Marked {label} sent",
    ("POST", "/purchase-orders/{po_id}/received"): "Received goods on {label}",
    ("POST", "/products"): "Added a product",
    ("PATCH", "/products/{product_id}"): "Edited product {label}",
    ("DELETE", "/products/{product_id}"): "Removed product {label}",
    ("POST", "/inventory/{product_id}/adjust"): "Adjusted stock of {label} by {delta}",
    ("PATCH", "/inventory/{product_id}/supplier"): "Changed the supplier of {label}",
    ("POST", "/customers"): "Added a customer",
    ("PATCH", "/customers/{customer_id}"): "Edited customer {label}",
    ("DELETE", "/customers/{customer_id}"): "Removed customer {label}",
    ("POST", "/suppliers"): "Added a supplier",
    ("PATCH", "/suppliers/{supplier_id}"): "Edited supplier {label}",
    ("DELETE", "/suppliers/{supplier_id}"): "Removed supplier {label}",
    ("POST", "/customers/{customer_id}/branches"): "Added a branch to customer {label}",
    ("PATCH", "/customers/{customer_id}/branches/{branch_id}"): "Edited a branch of {label}",
    ("DELETE", "/customers/{customer_id}/branches/{branch_id}"): "Removed a branch of {label}",
    ("POST", "/suppliers/{supplier_id}/branches"): "Added a branch to supplier {label}",
    ("PATCH", "/suppliers/{supplier_id}/branches/{branch_id}"): "Edited a branch of {label}",
    ("DELETE", "/suppliers/{supplier_id}/branches/{branch_id}"): "Removed a branch of {label}",
    ("POST", "/categories"): "Added a category",
    ("PATCH", "/categories/{category_id}"): "Edited category {label}",
    ("DELETE", "/categories/{category_id}"): "Removed category {label}",
    ("PATCH", "/settings"): "Changed settings",
    ("POST", "/imports/products"): "Imported products from a spreadsheet",
    ("POST", "/users"): "Added a staff login",
    ("PATCH", "/users/{user_id}"): "Changed the login of {label}",
    ("POST", "/users/{user_id}/password"): "Reset the password of {label}",
    ("POST", "/auth/change-password"): "Changed own password",
}


def _entity_key(params: dict[str, Any]) -> str | None:
    return next((k for k in _ENTITIES if k in params), None)


def label_for(db: Session, template: str, params: dict[str, Any]) -> str:
    key = _entity_key(params)
    if key is None:
        return ""
    model, column, _, _ = _ENTITIES[key]
    try:
        row = db.get(model, int(params[key]))
    except (TypeError, ValueError):
        return ""
    return str(getattr(row, column, "") or "") if row is not None else f"#{params[key]}"


def describe(
    method: str, template: str, params: dict[str, Any], body: dict[str, Any], label: str
) -> tuple[str, str, int | None, str]:
    """(action, area, entity id, link) for one change."""
    key = _entity_key(params)
    entity_id = int(params[key]) if key and str(params[key]).isdigit() else None
    area, link = "", ""
    if key:
        _, _, area, link_t = _ENTITIES[key]
        link = link_t.format(id=entity_id) if entity_id and method != "DELETE" else ""
    else:
        first = template.strip("/").split("/", 1)[0]
        area = {
            "quotations": "Quotations",
            "products": "Products",
            "customers": "Customers",
            "suppliers": "Suppliers",
            "categories": "Products",
            "settings": "Settings",
            "imports": "Products",
            "users": "Staff",
            "auth": "Sign-in",
        }.get(first, first.title())
    text = _ACTIONS.get((method, template), f"{method} {template}")
    if template == "/quotations/{quotation_id}/revise" and body.get("kind") == "revision":
        text = "Started a revised quotation on {label}"
    delta = body.get("delta")
    words = {
        "label": label or "",
        "status": str(body.get("status", "")),
        "delta": f"{delta:+d}" if isinstance(delta, int) else "",
    }
    return " ".join(text.format(**words).split()), area, entity_id, link


def record(db: Session, *, user: User | None, action: str, area: str, ip: str = "") -> None:
    """For events outside a signed-in request, such as signing in."""
    db.add(
        ActivityLog(
            user_id=user.id if user else None,
            user_name=(user.full_name or user.email) if user else "",
            action=action,
            area=area,
            ip=ip,
        )
    )


def list_activity(
    db: Session,
    *,
    q: str | None,
    user_id: int | None,
    area: str | None,
    date_from: date | None,
    date_to: date | None,
    offset: int,
    limit: int,
) -> tuple[list[ActivityLog], int]:
    stmt: Select[tuple[ActivityLog]] = select(ActivityLog)
    if q:
        pattern = contains(q)
        stmt = stmt.where(
            or_(
                ActivityLog.action.ilike(pattern, escape=LIKE_ESCAPE),
                ActivityLog.user_name.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )
    if user_id is not None:
        stmt = stmt.where(ActivityLog.user_id == user_id)
    if area:
        stmt = stmt.where(ActivityLog.area == area)
    if date_from is not None:
        stmt = stmt.where(ActivityLog.created_at >= datetime.combine(date_from, time.min, IST))
    if date_to is not None:
        stmt = stmt.where(
            ActivityLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min, IST)
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return list(rows), total
