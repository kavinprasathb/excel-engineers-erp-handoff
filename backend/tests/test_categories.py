"""Categories: unpaginated, and a delete that leaves its products behind."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import Category, Product, User
from app.security import hash_password

from .factories import make_product


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="categories-admin@excelengineers.in",
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


def test_list_is_a_bare_array_not_a_page(client: TestClient) -> None:
    """The contract says unpaginated: the list is a dozen rows and a pager over
    it would be furniture the operator has to click through."""
    body = client.get("/api/categories").json()
    assert isinstance(body, list)


def test_create_and_count(client: TestClient, db: Session) -> None:
    created = client.post("/api/categories", json={"name": "Centrifugal Pumps"})
    assert created.status_code == 201
    assert created.json() == {
        "id": created.json()["id"],
        "name": "Centrifugal Pumps",
        "product_count": 0,
    }

    product = make_product(db)
    product.category_id = created.json()["id"]
    db.flush()

    counts = {c["name"]: c["product_count"] for c in client.get("/api/categories").json()}
    assert counts["Centrifugal Pumps"] == 1


def test_duplicate_names_are_a_conflict_regardless_of_case(client: TestClient) -> None:
    client.post("/api/categories", json={"name": "Valves"})
    assert client.post("/api/categories", json={"name": "valves"}).status_code == 409


def test_rename(client: TestClient) -> None:
    created = client.post("/api/categories", json={"name": "Spares"}).json()
    renamed = client.patch(f"/api/categories/{created['id']}", json={"name": "Spare Parts"})
    assert renamed.json()["name"] == "Spare Parts"


def test_delete_leaves_its_products_with_a_null_category(client: TestClient, db: Session) -> None:
    """Deleting a grouping must never delete the things grouped."""
    category = client.post("/api/categories", json={"name": "Temporary Group"}).json()
    product = make_product(db)
    product.category_id = category["id"]
    db.flush()

    assert client.delete(f"/api/categories/{category['id']}").status_code == 204
    db.expire_all()
    assert db.get(Category, category["id"]) is None
    survivor = db.get(Product, product.id)
    assert survivor is not None
    assert survivor.category_id is None


def test_delete_missing_is_a_not_found(client: TestClient) -> None:
    assert client.delete("/api/categories/987654").status_code == 404


def test_requires_a_session(db: Session) -> None:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    try:
        assert TestClient(fastapi_app).get("/api/categories").status_code == 401
    finally:
        fastapi_app.dependency_overrides.clear()
