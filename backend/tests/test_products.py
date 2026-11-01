"""Products: the create that is one transaction, and the patch that must not move stock."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import MovementType, UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import Inventory, Product, StockMovement, User
from app.security import hash_password
from app.services import stock

from .factories import make_product, make_supplier


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="products-admin@excelengineers.in",
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


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "sku": "KSB-ETA-65-200",
        "name": "KSB Etanorm 65-200",
        "model_number": "65-200",
        "hsn_code": "84137010",
        "purchase_cost": 4250000,
        "sell_price": 5100000,
        "gst_rate_bp": 1800,
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------- create


def test_create_makes_product_inventory_and_opening_movement(
    client: TestClient, db: Session, admin: User
) -> None:
    """One transaction. A product without an inventory row would refuse every
    later stock operation with no way to fix it from the UI."""
    response = client.post("/api/products", json=_payload(opening_quantity=12))
    assert response.status_code == 201
    body = response.json()
    assert body["inventory"] == {
        "quantity_on_hand": 12,
        "quantity_reserved": 0,
        "quantity_available": 12,
    }

    movements = (
        db.execute(select(StockMovement).where(StockMovement.product_id == body["id"]))
        .scalars()
        .all()
    )
    assert len(movements) == 1
    assert movements[0].movement_type is MovementType.RECEIVE
    assert movements[0].created_by_id == admin.id
    assert stock.reconcile(db) == []


def test_create_without_opening_stock_writes_no_movement(client: TestClient, db: Session) -> None:
    """Zero stock is not an event; a movement of nothing would be noise in the ledger."""
    body = client.post("/api/products", json=_payload(opening_quantity=0)).json()
    assert body["inventory"]["quantity_on_hand"] == 0
    assert (
        db.execute(select(StockMovement).where(StockMovement.product_id == body["id"])).first()
        is None
    )


def test_create_rolls_everything_back_when_the_supplier_does_not_exist(
    client: TestClient, db: Session
) -> None:
    response = client.post("/api/products", json=_payload(supplier_id=987654, opening_quantity=5))
    assert response.status_code == 404
    assert db.execute(select(Product).where(Product.sku == "KSB-ETA-65-200")).first() is None


def test_duplicate_sku_is_a_conflict_regardless_of_case(client: TestClient) -> None:
    client.post("/api/products", json=_payload())
    assert client.post("/api/products", json=_payload(sku="ksb-eta-65-200")).status_code == 409


def test_money_is_integer_paise(client: TestClient) -> None:
    """A float here would reintroduce exactly the rounding drift the importer
    goes through Decimal to avoid."""
    assert client.post("/api/products", json=_payload(purchase_cost=42.5)).status_code == 422
    assert client.post("/api/products", json=_payload(sell_price=-1)).status_code == 422


def test_gst_outside_the_slab_range_is_refused(client: TestClient) -> None:
    assert client.post("/api/products", json=_payload(gst_rate_bp=10001)).status_code == 422


# --------------------------------------------------------------------------- read


def test_get_returns_the_contract_shape(client: TestClient, db: Session) -> None:
    supplier = make_supplier(db, name="KSB Pumps Ltd")
    db.flush()
    created = client.post("/api/products", json=_payload(supplier_id=supplier.id)).json()

    body = client.get(f"/api/products/{created['id']}").json()
    assert body["supplier"] == {"id": supplier.id, "name": "KSB Pumps Ltd"}
    assert body["category"] is None
    assert set(body["inventory"]) == {
        "quantity_on_hand",
        "quantity_reserved",
        "quantity_available",
    }


def test_search_covers_sku_name_and_model_number(client: TestClient, db: Session) -> None:
    make_product(db, sku="PUMP-A-1", name="Alpha pump")
    make_product(db, sku="ZZZ-9", name="Unrelated")
    db.flush()

    for query in ("PUMP-A", "Alpha"):
        items = client.get("/api/products", params={"q": query}).json()["items"]
        assert [i["sku"] for i in items] == ["PUMP-A-1"]


def test_has_supplier_false_finds_the_untagged(client: TestClient, db: Session) -> None:
    """The filter that matters after an import: an untagged product is invisible
    until it silently blocks an order."""
    supplier = make_supplier(db, name="Tagged Supplier")
    make_product(db, sku="TAGGED-1", supplier=supplier)
    make_product(db, sku="UNTAGGED-1")
    db.flush()

    untagged = client.get("/api/products", params={"has_supplier": False}).json()
    assert "UNTAGGED-1" in [i["sku"] for i in untagged["items"]]
    assert "TAGGED-1" not in [i["sku"] for i in untagged["items"]]

    tagged = client.get("/api/products", params={"has_supplier": True}).json()
    assert "UNTAGGED-1" not in [i["sku"] for i in tagged["items"]]


# --------------------------------------------------------------------------- update


def test_patch_never_changes_stock(client: TestClient, db: Session) -> None:
    """Explicitly: a catalogue edit that moved a counter would leave the ledger
    unable to explain it."""
    created = client.post("/api/products", json=_payload(opening_quantity=7)).json()

    body = client.patch(f"/api/products/{created['id']}", json={"name": "Renamed"}).json()
    assert body["name"] == "Renamed"
    assert body["inventory"]["quantity_on_hand"] == 7
    assert stock.reconcile(db) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"quantity_on_hand": 99},
        {"opening_quantity": 99},
        {"inventory": {"quantity_on_hand": 99}},
    ],
    ids=["counter", "opening", "nested"],
)
def test_patch_refuses_any_field_that_looks_like_stock(
    client: TestClient, payload: dict[str, object]
) -> None:
    created = client.post("/api/products", json=_payload()).json()
    assert client.patch(f"/api/products/{created['id']}", json=payload).status_code == 422


def test_patch_can_clear_a_relation_but_not_a_text_field(client: TestClient, db: Session) -> None:
    """null on a relation means "remove the tag"; on optional text the contract
    says "" and an omitted field means "leave it alone"."""
    supplier = make_supplier(db, name="Removable Supplier")
    db.flush()
    created = client.post("/api/products", json=_payload(supplier_id=supplier.id)).json()

    cleared = client.patch(f"/api/products/{created['id']}", json={"supplier_id": None}).json()
    assert cleared["supplier"] is None
    assert cleared["hsn_code"] == "84137010"


def test_delete_is_a_soft_delete(client: TestClient, db: Session) -> None:
    """The ledger references this product forever."""
    created = client.post("/api/products", json=_payload(opening_quantity=1)).json()
    assert client.delete(f"/api/products/{created['id']}").status_code == 204

    row = db.get(Product, created["id"])
    assert row is not None and row.is_active is False
    # The inventory row and its movement survive: history that disappears when
    # someone tidies the catalogue is not history.
    assert (
        db.execute(select(Inventory).where(Inventory.product_id == created["id"])).first()
        is not None
    )


# --------------------------------------------------------------------------- movements


def test_movements_are_newest_first_and_name_their_actor(
    client: TestClient, db: Session, admin: User
) -> None:
    created = client.post("/api/products", json=_payload(opening_quantity=5)).json()
    client.post(
        f"/api/inventory/{created['id']}/adjust", json={"delta": -2, "note": "damaged in transit"}
    )

    body = client.get(f"/api/products/{created['id']}/movements").json()
    assert body["total"] == 2
    latest = body["items"][0]
    assert latest["movement_type"] == "adjust"
    assert latest["on_hand_delta"] == -2
    assert latest["quantity_on_hand_after"] == 3
    assert latest["note"] == "damaged in transit"
    assert latest["created_by"] == {"id": admin.id, "full_name": "Admin"}
    assert latest["created_at"].endswith("Z") or "+00:00" in latest["created_at"]


def test_movements_of_a_missing_product_is_a_not_found(client: TestClient) -> None:
    assert client.get("/api/products/987654/movements").status_code == 404


# --------------------------------------------------------------------------- lookup


def test_lookup_returns_only_what_the_line_builder_needs(client: TestClient) -> None:
    """`purchase_cost` must never reach a customer-facing screen."""
    created = client.post("/api/products", json=_payload(**{"opening_quantity": 9})).json()

    rows = client.get("/api/products/lookup", params={"q": "Etanorm"}).json()
    assert [r["id"] for r in rows] == [created["id"]]
    assert set(rows[0]) == {
        "id",
        "sku",
        "name",
        "model_number",
        "unit",
        "hsn_code",
        "sell_price",
        "quantity_available",
        # stocked / to order / service: the picker labels items not on the shelf.
        "stock_type",
    }
    assert rows[0]["sell_price"] == 5100000
    assert rows[0]["quantity_available"] == 9


def test_lookup_hides_inactive_products(client: TestClient) -> None:
    created = client.post("/api/products", json=_payload()).json()
    client.delete(f"/api/products/{created['id']}")
    assert client.get("/api/products/lookup", params={"q": "Etanorm"}).json() == []


def test_lookup_matches_sku_and_model_number(client: TestClient) -> None:
    client.post("/api/products", json=_payload())
    assert len(client.get("/api/products/lookup", params={"q": "KSB-ETA"}).json()) == 1
    assert len(client.get("/api/products/lookup", params={"q": "65-200"}).json()) == 1


def test_lookup_limit_defaults_to_20_and_caps_at_50(client: TestClient, db: Session) -> None:
    for index in range(60):
        make_product(db, sku=f"LOOK-{index:03d}", name=f"Lookup pump {index:03d}")
    db.flush()

    assert len(client.get("/api/products/lookup", params={"q": "Lookup pump"}).json()) == 20
    assert (
        len(client.get("/api/products/lookup", params={"q": "Lookup pump", "limit": 50}).json())
        == 50
    )
    assert client.get("/api/products/lookup", params={"limit": 51}).status_code == 422
    assert client.get("/api/products/lookup", params={"limit": 0}).status_code == 422


def test_lookup_is_not_parsed_as_a_product_id(client: TestClient) -> None:
    """Route order: `/lookup` is declared before `/{id}` or every keystroke 422s."""
    assert client.get("/api/products/lookup").status_code == 200


def test_lookup_requires_a_session(db: Session) -> None:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    try:
        assert TestClient(fastapi_app).get("/api/products/lookup").status_code == 401
    finally:
        fastapi_app.dependency_overrides.clear()
