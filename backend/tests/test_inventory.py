"""The inventory page: what it shows, what it lets you change, and what it costs.

The statement-count test is the one that matters most here. v2's version of
this screen read the settings singleton once per row to decide the colour of a
badge, so the page got slower in exact proportion to how much stock the client
had — and nothing in the test suite could tell, because the output was correct.
Correct output is not the property under test; the number of round-trips is.
"""

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
from app.models import AppSettings, User
from app.security import hash_password
from app.services import inventory as service
from app.services import stock

from .factories import make_product, make_supplier


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="inventory-admin@excelengineers.in",
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


@pytest.fixture
def threshold(db: Session) -> int:
    settings = db.get(AppSettings, 1)
    assert settings is not None
    settings.low_stock_threshold = 5
    db.flush()
    return 5


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


# --------------------------------------------------------------------------- performance


@pytest.mark.parametrize("page_size", [1, 25, 100])
def test_the_list_costs_the_same_number_of_queries_at_every_page_size(
    db: Session, threshold: int, page_size: int
) -> None:
    """No more than 3 statements: the count, the page, and room for one more.

    Parametrised over page sizes because that is what an N+1 looks like — the
    cost tracks the number of rows, not the number of things being asked for.
    """
    supplier = make_supplier(db, name="Perf Supplier")
    for index in range(120):
        make_product(db, sku=f"PERF-{index:03d}", on_hand=index % 9, supplier=supplier)
    # Flush the fixture data before counting; only the list's own statements
    # are under test.
    db.flush()
    db.expire_all()

    connection = db.get_bind()
    assert isinstance(connection, Connection)
    with StatementCounter(connection) as counter:
        items, total = service.list_inventory(db, limit=page_size, sort="name")

    assert len(items) == min(page_size, total)
    assert len(counter) <= 3, "\n".join(counter.statements)


def test_a_row_knows_its_supplier_and_category_without_a_second_query(
    db: Session, threshold: int
) -> None:
    """Every relationship is lazy="raise", so a missing loader option is a hard
    error rather than a silent extra round-trip. This is that guarantee, tested."""
    supplier = make_supplier(db, name="Eager Supplier")
    make_product(db, sku="EAGER-1", on_hand=3, supplier=supplier)
    db.flush()
    db.expire_all()

    items, _ = service.list_inventory(db, q="EAGER-1")
    assert items[0].supplier is not None
    assert items[0].supplier.name == "Eager Supplier"


# --------------------------------------------------------------------------- the rules


def test_low_and_out_are_computed_server_side(
    client: TestClient, db: Session, threshold: int
) -> None:
    """The client maps two booleans to a colour and never learns the rule."""
    make_product(db, sku="OUT-1", on_hand=0)
    make_product(db, sku="LOW-1", on_hand=threshold)
    make_product(db, sku="OK-1", on_hand=threshold + 1)
    db.flush()

    rows = {
        r["sku"]: r for r in client.get("/api/inventory", params={"page_size": 200}).json()["items"]
    }
    assert (rows["OUT-1"]["is_out_of_stock"], rows["OUT-1"]["is_low_stock"]) == (True, False)
    assert (rows["LOW-1"]["is_out_of_stock"], rows["LOW-1"]["is_low_stock"]) == (False, True)
    assert (rows["OK-1"]["is_out_of_stock"], rows["OK-1"]["is_low_stock"]) == (False, False)


def test_the_threshold_is_read_from_settings_not_hardcoded(
    client: TestClient, db: Session, threshold: int
) -> None:
    make_product(db, sku="MOVES-1", on_hand=8)
    db.flush()
    assert (
        client.get("/api/inventory", params={"q": "MOVES-1"}).json()["items"][0]["is_low_stock"]
        is False
    )

    client.patch("/api/settings", json={"low_stock_threshold": 10})
    assert (
        client.get("/api/inventory", params={"q": "MOVES-1"}).json()["items"][0]["is_low_stock"]
        is True
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [("low", {"LOW-1"}), ("out", {"OUT-1"}), ("ok", {"OK-1"})],
)
def test_stock_status_filter(
    client: TestClient, db: Session, threshold: int, status: str, expected: set[str]
) -> None:
    make_product(db, sku="OUT-1", on_hand=0)
    make_product(db, sku="LOW-1", on_hand=2)
    make_product(db, sku="OK-1", on_hand=50)
    db.flush()

    items = client.get(
        "/api/inventory", params={"stock_status": status, "q": "-1", "page_size": 200}
    ).json()["items"]
    assert {i["sku"] for i in items} & {"OUT-1", "LOW-1", "OK-1"} == expected


def test_has_supplier_false_finds_the_untagged(client: TestClient, db: Session) -> None:
    """Same filter as on products, and for the same reason: after an import,
    untagged rows are the ones that will block an order."""
    supplier = make_supplier(db, name="Inv Supplier")
    make_product(db, sku="INV-TAGGED", supplier=supplier)
    make_product(db, sku="INV-UNTAGGED")
    db.flush()

    skus = {
        i["sku"]
        for i in client.get(
            "/api/inventory", params={"has_supplier": False, "page_size": 200}
        ).json()["items"]
    }
    assert "INV-UNTAGGED" in skus
    assert "INV-TAGGED" not in skus


def test_sorting_by_available(client: TestClient, db: Session) -> None:
    make_product(db, sku="SORT-LOW", name="zzz sort low", on_hand=1)
    make_product(db, sku="SORT-HIGH", name="aaa sort high", on_hand=900)
    db.flush()

    items = client.get(
        "/api/inventory", params={"sort": "-available", "q": "sort", "page_size": 200}
    ).json()["items"]
    assert items[0]["sku"] == "SORT-HIGH"


def test_an_unimplemented_sort_key_is_refused(client: TestClient) -> None:
    assert client.get("/api/inventory", params={"sort": "supplier"}).status_code == 422


# --------------------------------------------------------------------------- summary


def test_summary_is_the_header_cards(client: TestClient, db: Session, threshold: int) -> None:
    supplier = make_supplier(db, name="Summary Supplier")
    make_product(db, sku="SUM-OUT", on_hand=0, supplier=supplier)
    make_product(db, sku="SUM-LOW", on_hand=2, supplier=supplier)
    make_product(db, sku="SUM-UNTAGGED", on_hand=10)
    db.flush()

    body = client.get("/api/inventory/summary").json()
    assert set(body) == {
        "total_products",
        "low_stock_count",
        "out_of_stock_count",
        "missing_supplier_count",
        "total_stock_value_paise",
    }
    assert body["out_of_stock_count"] >= 1
    assert body["low_stock_count"] >= 1
    assert body["missing_supplier_count"] >= 1


def test_summary_values_stock_at_purchase_cost(client: TestClient, db: Session) -> None:
    """What the stock on the floor cost, which is the figure an accountant asks for."""
    before = client.get("/api/inventory/summary").json()["total_stock_value_paise"]
    product = make_product(db, sku="VALUED-1", on_hand=3)
    product.purchase_cost = 100_000
    db.flush()
    after = client.get("/api/inventory/summary").json()["total_stock_value_paise"]
    assert after - before == 300_000


def test_summary_is_not_parsed_as_a_product_id(client: TestClient) -> None:
    assert client.get("/api/inventory/summary").status_code == 200


# --------------------------------------------------------------------------- adjust


def test_adjust_moves_stock_and_returns_the_refreshed_row(
    client: TestClient, db: Session, admin: User, threshold: int
) -> None:
    product = make_product(db, sku="ADJ-1", on_hand=10)
    db.flush()

    body = client.post(
        f"/api/inventory/{product.id}/adjust", json={"delta": -8, "note": "recount"}
    ).json()
    assert body["quantity_on_hand"] == 2
    assert body["quantity_available"] == 2
    assert body["is_low_stock"] is True

    movements = client.get(f"/api/inventory/{product.id}/movements").json()["items"]
    assert movements[0]["note"] == "recount"
    assert movements[0]["created_by"]["id"] == admin.id


def test_adjust_below_zero_is_refused_with_the_stock_services_message(
    client: TestClient, db: Session
) -> None:
    product = make_product(db, sku="ADJ-2", on_hand=3)
    db.flush()

    response = client.post(f"/api/inventory/{product.id}/adjust", json={"delta": -5, "note": ""})
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "insufficient_stock"
    assert error["details"] == {"in_stock": 3, "requested": 5}


def test_adjust_of_zero_is_refused(client: TestClient, db: Session) -> None:
    """An adjustment that changes nothing would be a movement explaining nothing."""
    product = make_product(db, sku="ADJ-3", on_hand=3)
    db.flush()
    assert client.post(f"/api/inventory/{product.id}/adjust", json={"delta": 0}).status_code == 409


def test_adjust_leaves_the_ledger_able_to_explain_the_counters(
    client: TestClient, db: Session
) -> None:
    product = make_product(db, sku="ADJ-4", on_hand=0)
    db.flush()
    client.post(f"/api/inventory/{product.id}/adjust", json={"delta": 6, "note": "found"})
    client.post(f"/api/inventory/{product.id}/adjust", json={"delta": -1, "note": "damaged"})
    assert stock.reconcile(db, product.id) == []


def test_adjust_on_a_missing_product_is_a_not_found(client: TestClient) -> None:
    assert client.post("/api/inventory/987654/adjust", json={"delta": 1}).status_code == 404


# --------------------------------------------------------------------------- supplier


def test_setting_a_supplier_returns_the_whole_refreshed_row(
    client: TestClient, db: Session, threshold: int
) -> None:
    """Whole row, not an acknowledgement: the client patches one cache entry and
    the table does not flicker or lose the operator's scroll position."""
    supplier = make_supplier(db, name="Newly Tagged")
    product = make_product(db, sku="TAG-1", on_hand=2)
    db.flush()

    body = client.patch(
        f"/api/inventory/{product.id}/supplier", json={"supplier_id": supplier.id}
    ).json()
    assert body["supplier"] == {"id": supplier.id, "name": "Newly Tagged"}
    assert body["sku"] == "TAG-1"
    assert body["is_low_stock"] is True


def test_a_null_supplier_clears_the_tag(client: TestClient, db: Session) -> None:
    supplier = make_supplier(db, name="Wrongly Tagged")
    product = make_product(db, sku="TAG-2", supplier=supplier)
    db.flush()

    body = client.patch(f"/api/inventory/{product.id}/supplier", json={"supplier_id": None}).json()
    assert body["supplier"] is None


def test_an_unknown_supplier_is_a_not_found(client: TestClient, db: Session) -> None:
    product = make_product(db, sku="TAG-3")
    db.flush()
    response = client.patch(f"/api/inventory/{product.id}/supplier", json={"supplier_id": 987654})
    assert response.status_code == 404


def test_changing_the_supplier_never_moves_stock(client: TestClient, db: Session) -> None:
    supplier = make_supplier(db, name="Neutral Supplier")
    product = make_product(db, sku="TAG-4", on_hand=9)
    db.flush()

    body = client.patch(
        f"/api/inventory/{product.id}/supplier", json={"supplier_id": supplier.id}
    ).json()
    assert body["quantity_on_hand"] == 9


def test_the_list_requires_a_session(db: Session) -> None:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    try:
        assert TestClient(fastapi_app).get("/api/inventory").status_code == 401
    finally:
        fastapi_app.dependency_overrides.clear()
