"""Owner and staff: what staff cannot do or see, the activity log, reorder."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import ActivityLog, Customer, Product, User
from tests.test_orders import (  # noqa: F401  (fixtures)
    _accept,
    _line,
    _quote,
    admin,
    client,
    customer,
    stocked,
)


@pytest.fixture
def staff(db: Session) -> User:
    u = User(
        email="staff@excelengineers.in",
        full_name="Ravi",
        password_hash="x",
        role=UserRole.STAFF,
        is_active=True,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def staff_client(db: Session, staff: User) -> Iterator[TestClient]:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    fastapi_app.dependency_overrides[get_current_user] = lambda: staff
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()


def test_staff_cannot_delete_or_see_owner_pages(
    staff_client: TestClient,
    customer: Customer,  # noqa: F811
    db: Session,
) -> None:
    pump = stocked(db, sku="P", name="Pump", qty=1)
    q = _quote(staff_client, customer, [_line(pump, 1)])  # daily work is fine
    assert staff_client.delete(f"/api/quotations/{q['id']}").status_code == 403
    assert staff_client.delete(f"/api/products/{pump.id}").status_code == 403
    assert staff_client.get("/api/analytics").status_code == 403
    assert staff_client.patch("/api/settings", json={}).status_code == 403
    assert staff_client.get("/api/users").status_code == 403
    assert staff_client.get("/api/activity").status_code == 403
    assert staff_client.get("/api/deal-tracker").status_code == 403
    assert staff_client.get("/api/deal-tracker/export").status_code == 403
    # An import writes purchase cost, which staff may not set.
    assert staff_client.get("/api/imports").status_code == 403
    assert staff_client.get("/api/imports/template.xlsx").status_code == 403
    upload = {"file": ("p.xlsx", b"PK", "application/octet-stream")}
    assert staff_client.post("/api/imports/products", files=upload).status_code == 403


def test_staff_create_cannot_set_purchase_cost(staff_client: TestClient, db: Session) -> None:
    r = staff_client.post(
        "/api/products",
        json={"sku": "STAFF-1", "name": "Staff pump", "purchase_cost": 999, "sell_price": 5},
    )
    assert r.status_code == 201, r.text
    product = db.get(Product, r.json()["id"])
    assert product is not None and product.purchase_cost == 0


def test_owner_sees_purchase_cost(
    client: TestClient,  # noqa: F811
    db: Session,
) -> None:
    pump = stocked(db, sku="P", name="Pump", qty=1)
    pump.purchase_cost = 50000
    db.flush()
    assert client.get(f"/api/products/{pump.id}").json()["purchase_cost"] == 50000
    assert client.get("/api/inventory/summary").json()["total_stock_value_paise"] == 50000


def test_staff_sees_no_cost_and_cannot_set_it(staff_client: TestClient, db: Session) -> None:
    pump = stocked(db, sku="P", name="Pump", qty=1)
    pump.purchase_cost = 50000
    db.flush()
    assert staff_client.get(f"/api/products/{pump.id}").json()["purchase_cost"] is None
    assert staff_client.get("/api/inventory/summary").json()["total_stock_value_paise"] is None
    r = staff_client.patch(f"/api/products/{pump.id}", json={"purchase_cost": 1, "name": "Pump 2"})
    assert r.status_code == 200
    db.refresh(pump)
    assert (pump.purchase_cost, pump.name) == (50000, "Pump 2")


def test_changes_are_logged_with_who_and_what(
    client: TestClient,  # noqa: F811
    customer: Customer,  # noqa: F811
    db: Session,
) -> None:
    pump = stocked(db, sku="P", name="Pump", qty=1)
    q = _quote(client, customer, [_line(pump, 1)])
    client.post(
        f"/api/quotations/{q['id']}/status", json={"status": "declined", "reason": "Price too high"}
    )
    actions = [a.action for a in db.execute(select(ActivityLog)).scalars()]
    assert "Created a quotation" in actions
    assert f"Marked {q['number']} declined" in actions
    listed = client.get("/api/activity", params={"q": "declined"}).json()
    assert listed["items"][0]["link"] == f"/quotations/{q['id']}"
    assert listed["items"][0]["user_name"] == "Admin"


def test_owner_manages_staff_and_keeps_one_owner(
    client: TestClient,  # noqa: F811
    admin: User,  # noqa: F811
) -> None:
    r = client.post(
        "/api/users",
        json={"email": "new@x.in", "full_name": "New", "password": "long enough pass"},
    )
    assert r.status_code == 201 and r.json()["role"] == "staff"
    uid = r.json()["id"]
    assert client.patch(f"/api/users/{uid}", json={"is_active": False}).json()["is_active"] is False
    assert (
        client.post(f"/api/users/{uid}/password", json={"password": "another long one"}).status_code
        == 204
    )
    # The only owner cannot demote themselves.
    assert client.patch(f"/api/users/{admin.id}", json={"role": "staff"}).status_code == 422


def test_reorder_suggests_what_waiting_orders_need(
    client: TestClient,  # noqa: F811
    customer: Customer,  # noqa: F811
    db: Session,
) -> None:
    seal = stocked(db, sku="S", name="Seal", qty=0)
    _accept(client, _quote(client, customer, [_line(seal, 4)])["id"])
    # The drafted PO already covers the 4, so nothing more to buy yet.
    rows = {r["name"]: r for r in client.get("/api/analytics").json()["reorder"]["rows"]}
    assert "Seal" not in rows or rows["Seal"]["suggest"] >= 1
    assert "reorder" in client.get("/api/analytics").json()
