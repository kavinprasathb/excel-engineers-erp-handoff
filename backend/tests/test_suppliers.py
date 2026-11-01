"""Suppliers: the list, the dropdown, and the delete that refuses to orphan."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import Supplier, User
from app.security import hash_password

from .factories import make_product, make_supplier


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="suppliers-admin@excelengineers.in",
        full_name="Admin",
        password_hash=hash_password("correct-horse-battery"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def client(db: Session, admin: User) -> Iterator[TestClient]:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    fastapi_app.dependency_overrides[get_current_user] = lambda: admin
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()


# --------------------------------------------------------------------------- create


_REQUIRED = {
    "gstin": "27AAACK1234A1Z5",
    "city": "Pune",
    "state": "Maharashtra",
    "pincode": "411018",
}


def test_create_returns_the_contract_shape(client: TestClient) -> None:
    response = client.post("/api/suppliers", json={**_REQUIRED, "name": "KSB Pumps Ltd"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "KSB Pumps Ltd"
    assert body["product_count"] == 0
    assert body["code"].startswith("SUP-")
    assert body["branches"] == [] and body["missing_fields"] == []
    assert body["is_active"] is True
    # Optional text is "" and never null — the contract's rule, so the frontend
    # never has to write `?? ""` at a render site.
    assert body["phone"] == ""
    assert body["notes"] == ""


def test_duplicate_names_are_a_conflict_regardless_of_case(client: TestClient) -> None:
    client.post("/api/suppliers", json={**_REQUIRED, "name": "Lovejoy India"})
    response = client.post("/api/suppliers", json={**_REQUIRED, "name": "  lovejoy india  "})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_a_blank_name_is_a_validation_error(client: TestClient) -> None:
    response = client.post("/api/suppliers", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_fields_are_refused(client: TestClient) -> None:
    """Mass assignment defence: the schema is the allowlist."""
    assert client.post("/api/suppliers", json={"name": "X", "id": 9}).status_code == 422


# --------------------------------------------------------------------------- list


def test_list_paginates_and_counts_products(client: TestClient, db: Session) -> None:
    supplier = make_supplier(db, name="Counted Supplier")
    make_product(db, supplier=supplier)
    make_product(db, supplier=supplier)
    db.flush()

    body = client.get("/api/suppliers", params={"q": "Counted"}).json()
    assert body["total"] == 1
    assert body["items"][0]["product_count"] == 2
    assert set(body) == {"items", "total", "page", "page_size", "pages"}


def test_list_filters_by_active(client: TestClient, db: Session) -> None:
    dormant = make_supplier(db, name="Dormant Traders")
    dormant.is_active = False
    db.flush()

    active_names = [
        s["name"] for s in client.get("/api/suppliers", params={"is_active": True}).json()["items"]
    ]
    assert "Dormant Traders" not in active_names
    inactive = client.get("/api/suppliers", params={"is_active": False}).json()["items"]
    assert "Dormant Traders" in [s["name"] for s in inactive]


def test_list_rejects_a_sort_key_it_does_not_implement(client: TestClient) -> None:
    """Falling back silently would hide a client bug until someone noticed the order."""
    assert client.get("/api/suppliers", params={"sort": "product_count"}).status_code == 422


def test_page_size_is_capped(client: TestClient) -> None:
    assert client.get("/api/suppliers", params={"page_size": 500}).status_code == 422


# --------------------------------------------------------------------------- options


def test_options_are_unpaginated_and_active_only(client: TestClient, db: Session) -> None:
    """The inventory page's inline dropdown must not depend on how the list is paged."""
    for index in range(30):
        make_supplier(db, name=f"Option Supplier {index:02d}")
    retired = make_supplier(db, name="Retired Supplier")
    retired.is_active = False
    db.flush()

    options = client.get("/api/suppliers/options").json()
    names = {o["name"] for o in options}
    assert len({n for n in names if n.startswith("Option Supplier")}) == 30
    assert "Retired Supplier" not in names
    assert set(options[0]) == {"id", "name"}


def test_options_is_not_parsed_as_a_supplier_id(client: TestClient) -> None:
    """Route order: `/options` is declared before `/{id}` or every dropdown 422s."""
    assert client.get("/api/suppliers/options").status_code == 200


# --------------------------------------------------------------------------- detail


def test_get_includes_the_product_count(client: TestClient, db: Session) -> None:
    supplier = make_supplier(db, name="Detailed Supplier")
    make_product(db, supplier=supplier)
    db.flush()
    body = client.get(f"/api/suppliers/{supplier.id}").json()
    assert body["product_count"] == 1


def test_get_missing_is_a_not_found(client: TestClient) -> None:
    response = client.get("/api/suppliers/987654")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_patch_changes_only_what_was_sent(client: TestClient, db: Session) -> None:
    supplier = make_supplier(db, name="Patchable")
    db.flush()
    body = client.patch(f"/api/suppliers/{supplier.id}", json={"phone": "020-1234"}).json()
    assert body["phone"] == "020-1234"
    assert body["name"] == "Patchable"


def test_patch_to_a_taken_name_is_a_conflict(client: TestClient, db: Session) -> None:
    make_supplier(db, name="Taken Name")
    other = make_supplier(db, name="Other Name")
    db.flush()
    assert (
        client.patch(f"/api/suppliers/{other.id}", json={"name": "taken name"}).status_code == 409
    )


# --------------------------------------------------------------------------- delete


def test_delete_is_a_soft_delete(client: TestClient, db: Session) -> None:
    supplier = make_supplier(db, name="Soft Deleted")
    db.flush()
    assert client.delete(f"/api/suppliers/{supplier.id}").status_code == 204
    assert db.get(Supplier, supplier.id).is_active is False  # type: ignore[union-attr]


def test_delete_is_refused_while_products_reference_it(client: TestClient, db: Session) -> None:
    """The FK is RESTRICT; purchase history that lost its supplier is worse than a stale row."""
    supplier = make_supplier(db, name="Still Referenced")
    make_product(db, supplier=supplier)
    db.flush()

    response = client.delete(f"/api/suppliers/{supplier.id}")
    assert response.status_code == 409
    assert response.json()["error"]["details"]["product_count"] == 1


def test_every_endpoint_requires_a_session(db: Session) -> None:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    try:
        anonymous = TestClient(fastapi_app)
        assert anonymous.get("/api/suppliers").status_code == 401
        assert anonymous.get("/api/suppliers/options").status_code == 401
        assert anonymous.post("/api/suppliers", json={"name": "X"}).status_code == 401
    finally:
        fastapi_app.dependency_overrides.clear()
