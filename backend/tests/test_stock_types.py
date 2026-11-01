"""Items not kept in stock: "to order" items and services."""

# The fixtures are imported from test_orders and named as test parameters.
# ruff: noqa: F811

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Customer
from app.services.stock import reconcile
from tests.factories import make_supplier
from tests.test_orders import (  # noqa: F401  (fixtures)
    _accept,
    _line,
    _quote,
    admin,
    client,
    customer,
    stocked,
)


def _new_item(client: TestClient, **body: object) -> dict:
    r = client.post("/api/products", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_an_item_added_from_a_quote_gets_its_sku_and_type(client: TestClient) -> None:
    a = _new_item(client, name="ETN 125-100-250 GG", stock_type="to_order")
    b = _new_item(client, name="ETN 150-125-315 GG", stock_type="to_order")
    s = _new_item(client, name="Service charges", stock_type="service")
    plain = _new_item(client, name="Gland packing")
    assert (a["sku"], b["sku"], s["sku"], plain["sku"]) == (
        "ORD-0001",
        "ORD-0002",
        "SRV-0001",
        "ITM-0001",
    )
    assert plain["stock_type"] == "stocked"
    found = client.get("/api/products/lookup", params={"q": "ETN 125"}).json()
    assert found[0]["stock_type"] == "to_order" and found[0]["quantity_available"] == 0


def test_a_service_cannot_have_opening_stock(client: TestClient) -> None:
    r = client.post(
        "/api/products", json={"name": "Labour", "stock_type": "service", "opening_quantity": 2}
    )
    assert r.status_code == 422


def test_items_not_on_the_shelf_raise_no_stock_alert(client: TestClient, db: Session) -> None:
    stocked(db, sku="SHELF", name="Coupling", qty=0)
    _new_item(client, name="ETN to order", stock_type="to_order")
    _new_item(client, name="Transport", stock_type="service")
    summary = client.get("/api/inventory/summary").json()
    assert summary["total_products"] == 3
    assert summary["out_of_stock_count"] == 1  # only the shelf item
    rows = client.get("/api/inventory", params={"stock_type": "to_order"}).json()["items"]
    assert [r["name"] for r in rows] == ["ETN to order"]
    assert rows[0]["stock_type"] == "to_order" and rows[0]["is_out_of_stock"] is False


def test_order_waits_for_the_to_order_item_and_never_holds_stock_for_a_service(
    client: TestClient, customer: Customer, db: Session
) -> None:
    ksb = make_supplier(db, name="KSB")
    pump = _new_item(client, name="ETN 125-100-250 GG", stock_type="to_order", supplier_id=ksb.id)
    service = _new_item(client, name="Service charges", stock_type="service")
    lines = [
        {"product_id": pump["id"], "description": pump["name"], "quantity": 1, "rate_paise": 100},
        {"product_id": service["id"], "description": "Service", "quantity": 1, "rate_paise": 50},
    ]
    order = _accept(client, _quote(client, customer, lines)["id"])
    assert order["status"] == "waiting_stock"
    short = {ln["product_id"]: ln["short"] for ln in order["lines"]}
    assert short == {pump["id"]: 1, service["id"]: 0}

    # The purchase order is drafted for the pump only, to its supplier.
    pos = client.get(f"/api/orders/{order['id']}/purchase-orders").json()
    assert len(pos) == 1 and pos[0]["supplier"]["name"] == "KSB"
    assert [ln["product_id"] for ln in pos[0]["lines"]] == [pump["id"]]

    client.post(f"/api/purchase-orders/{pos[0]['id']}/sent")
    r = client.post(f"/api/purchase-orders/{pos[0]['id']}/received")
    assert r.status_code == 200, r.text
    assert client.get(f"/api/orders/{order['id']}").json()["status"] == "ready"

    delivered = client.post(f"/api/orders/{order['id']}/deliver")
    assert delivered.status_code == 200, delivered.text
    inv = client.get("/api/inventory", params={"q": "Service"}).json()["items"][0]
    assert (inv["quantity_on_hand"], inv["quantity_reserved"]) == (0, 0)
    assert reconcile(db) == []


def test_existing_shelf_items_behave_as_before(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    order = _accept(client, _quote(client, customer, [_line(a, 2)])["id"])
    assert order["status"] == "ready"
    assert client.get(f"/api/products/{a.id}").json()["stock_type"] == "stocked"
