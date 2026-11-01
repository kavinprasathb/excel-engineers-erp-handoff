"""Customers: the list, the dropdown, and the delete that refuses to orphan an offer."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, event
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import Customer, User
from app.security import hash_password
from app.services import customers as service


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="customers-admin@excelengineers.in",
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


def make_customer(db: Session, *, name: str, **fields: object) -> Customer:
    customer = Customer(name=name, **fields)
    db.add(customer)
    db.flush()
    return customer


class StatementCounter:
    """Counts every statement the connection executes, via before_cursor_execute."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.statements: list[str] = []

    def _record(self, _conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        self.statements.append(statement)

    def __enter__(self) -> "StatementCounter":
        event.listen(self.connection, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *_exc: object) -> None:
        event.remove(self.connection, "before_cursor_execute", self._record)

    def __len__(self) -> int:
        return len(self.statements)


# --------------------------------------------------------------------------- create


_REQUIRED = {
    "gstin": "33AAIFE2328P1Z9",
    "billing_city": "Salem",
    "billing_state": "Tamil Nadu",
    "billing_pincode": "636016",
}


def test_create_returns_the_contract_shape(client: TestClient) -> None:
    response = client.post(
        "/api/customers",
        json={
            "name": "Chemplast Sanmar Limited",
            "contact_person": "Mr. B. Prathap",
            "designation": "Purchase",
            "gstin": "33aaife2328p1z9",
            "billing_address_line1": "Chloro Chemical Division",
            "billing_city": "Mettur Dam",
            "billing_state": "Tamil Nadu",
            "billing_pincode": "636403",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Chemplast Sanmar Limited"
    assert body["is_active"] is True
    assert body["code"].startswith("CUST-")
    assert body["gstin"] == "33AAIFE2328P1Z9"  # normalised to capitals
    assert body["branches"] == [] and body["missing_fields"] == []
    # Optional text is "" and never null — the contract's rule, so the frontend
    # never has to write `?? ""` at a render site.
    assert body["phone"] == ""
    assert body["notes"] == ""
    # Blank shipping means "same as billing"; nothing copies one into the other.
    assert body["shipping_city"] == ""


def test_duplicate_names_are_a_conflict_regardless_of_case(client: TestClient) -> None:
    client.post("/api/customers", json={**_REQUIRED, "name": "IE-Emmvee"})
    response = client.post("/api/customers", json={**_REQUIRED, "name": "  ie-emmvee  "})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_a_blank_name_is_a_validation_error(client: TestClient) -> None:
    response = client.post("/api/customers", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_fields_are_refused(client: TestClient) -> None:
    """Mass assignment defence: the schema is the allowlist."""
    assert client.post("/api/customers", json={"name": "X", "id": 9}).status_code == 422


# --------------------------------------------------------------------------- list


def test_list_returns_the_pagination_envelope(client: TestClient, db: Session) -> None:
    make_customer(db, name="Counted Customer")
    db.flush()

    body = client.get("/api/customers", params={"q": "Counted"}).json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Counted Customer"
    assert set(body) == {"items", "total", "page", "page_size", "pages"}


def test_q_searches_the_billing_city_as_well_as_the_name(client: TestClient, db: Session) -> None:
    make_customer(db, name="Unrelated Name", billing_city="Mettur Dam")
    db.flush()
    names = [
        c["name"] for c in client.get("/api/customers", params={"q": "Mettur"}).json()["items"]
    ]
    assert "Unrelated Name" in names


def test_list_filters_by_active(client: TestClient, db: Session) -> None:
    dormant = make_customer(db, name="Dormant Buyers")
    dormant.is_active = False
    db.flush()

    active_names = [
        c["name"] for c in client.get("/api/customers", params={"is_active": True}).json()["items"]
    ]
    assert "Dormant Buyers" not in active_names
    inactive = client.get("/api/customers", params={"is_active": False}).json()["items"]
    assert "Dormant Buyers" in [c["name"] for c in inactive]


def test_list_rejects_a_sort_key_it_does_not_implement(client: TestClient) -> None:
    """Falling back silently would hide a client bug until someone noticed the order."""
    assert client.get("/api/customers", params={"sort": "phone"}).status_code == 422


def test_page_size_is_capped(client: TestClient) -> None:
    assert client.get("/api/customers", params={"page_size": 500}).status_code == 422
    assert client.get("/api/customers", params={"page": 0}).status_code == 422


# --------------------------------------------------------------------------- performance


@pytest.mark.parametrize("page_size", [1, 25, 100])
def test_the_list_costs_the_same_number_of_queries_at_every_page_size(
    db: Session, page_size: int
) -> None:
    """No more than 3 statements: the count, the page, and room for one more.

    Parametrised over page sizes because that is what an N+1 looks like — the
    cost tracks the number of rows, not the number of things being asked for.
    Nothing is counted per customer today; this guards the day something is
    and someone reaches for a loop.
    """
    for index in range(120):
        make_customer(db, name=f"Perf Customer {index:03d}")
    db.flush()
    db.expire_all()

    connection = db.get_bind()
    assert isinstance(connection, Connection)
    with StatementCounter(connection) as counter:
        rows, total = service.list_customers(db, limit=page_size, sort="name")

    assert len(rows) == min(page_size, total)
    assert len(counter) <= 3, "\n".join(counter.statements)


# --------------------------------------------------------------------------- options


def test_options_are_unpaginated_and_active_only(client: TestClient, db: Session) -> None:
    """A customer picker must not depend on how the list is paged."""
    for index in range(30):
        make_customer(db, name=f"Option Customer {index:02d}")
    retired = make_customer(db, name="Retired Customer")
    retired.is_active = False
    db.flush()

    options = client.get("/api/customers/options").json()
    names = {o["name"] for o in options}
    assert len({n for n in names if n.startswith("Option Customer")}) == 30
    assert "Retired Customer" not in names
    assert set(options[0]) == {"id", "name"}


def test_options_is_not_parsed_as_a_customer_id(client: TestClient) -> None:
    """Route order: `/options` is declared before `/{id}` or every dropdown 422s."""
    assert client.get("/api/customers/options").status_code == 200


# --------------------------------------------------------------------------- detail


def test_get_missing_is_a_not_found(client: TestClient) -> None:
    response = client.get("/api/customers/987654")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_patch_changes_only_what_was_sent(client: TestClient, db: Session) -> None:
    customer = make_customer(db, name="Patchable", billing_city="Salem")
    db.flush()
    body = client.patch(f"/api/customers/{customer.id}", json={"phone": "0427-244"}).json()
    assert body["phone"] == "0427-244"
    assert body["name"] == "Patchable"
    assert body["billing_city"] == "Salem"


def test_patch_to_a_taken_name_is_a_conflict(client: TestClient, db: Session) -> None:
    make_customer(db, name="Taken Customer")
    other = make_customer(db, name="Other Customer")
    db.flush()
    assert (
        client.patch(f"/api/customers/{other.id}", json={"name": "taken customer"}).status_code
        == 409
    )


# --------------------------------------------------------------------------- delete


def test_delete_is_a_soft_delete(client: TestClient, db: Session) -> None:
    customer = make_customer(db, name="Soft Deleted Customer")
    db.flush()
    assert client.delete(f"/api/customers/{customer.id}").status_code == 204
    assert db.get(Customer, customer.id).is_active is False  # type: ignore[union-attr]


def test_every_endpoint_requires_a_session(db: Session) -> None:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    try:
        anonymous = TestClient(fastapi_app)
        assert anonymous.get("/api/customers").status_code == 401
        assert anonymous.get("/api/customers/options").status_code == 401
        assert anonymous.get("/api/customers/1").status_code == 401
        assert anonymous.post("/api/customers", json={"name": "X"}).status_code == 401
        assert anonymous.delete("/api/customers/1").status_code == 401
    finally:
        fastapi_app.dependency_overrides.clear()
