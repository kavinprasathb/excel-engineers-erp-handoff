"""Orders from accepted quotations: stock held, purchase drafts, Product Delivery."""

import re
from collections.abc import Iterator
from io import BytesIO

import pypdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import Customer, Product, User
from app.services.stock import reconcile
from tests.factories import inventory_of, make_product, make_supplier


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="orders-admin@excelengineers.in",
        full_name="Admin",
        password_hash="x",
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
def customer(db: Session) -> Customer:
    c = Customer(name="IE-Emmvee Photovoltaic Power")
    db.add(c)
    db.flush()
    return c


def stocked(db: Session, *, sku: str, name: str, qty: int, supplier=None) -> Product:  # type: ignore[no-untyped-def]
    """A product whose stock came in through the ledger, so reconcile() holds."""
    from app.constants import ReferenceType
    from app.services import stock
    from app.services.stock import StockRef

    p = make_product(db, sku=sku, name=name, on_hand=0, supplier=supplier)
    if qty:
        stock.receive(db, product_id=p.id, qty=qty, ref=StockRef(ReferenceType.MANUAL))
        db.flush()
    return p


def _quote(client: TestClient, customer: Customer, lines: list[dict[str, object]]) -> dict:
    r = client.post(
        "/api/quotations",
        json={
            "type": "spares",
            "customer_id": customer.id,
            "quote_date": "2026-09-26",
            "subject": "Offer",
            "lines": lines,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _line(p: Product, qty: int) -> dict[str, object]:
    return {"product_id": p.id, "description": p.name, "quantity": qty, "rate_paise": 100000}


def _accept(client: TestClient, qid: int) -> dict:
    r = client.post(f"/api/quotations/{qid}/status", json={"status": "accepted"})
    assert r.status_code == 200, r.text
    return client.get(f"/api/quotations/{qid}/order").json()


def test_all_in_stock_is_ready_and_stock_is_held(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    b = stocked(db, sku="B", name="Spblock", qty=3)
    q = _quote(client, customer, [_line(a, 3), _line(b, 3)])
    order = _accept(client, q["id"])
    assert order["status"] == "ready"
    assert order["number"] == "ORD-ESQSP-26-1"
    assert [(ln["reserved"], ln["short"]) for ln in order["lines"]] == [(3, 0), (3, 0)]
    assert inventory_of(db, a).quantity_reserved == 3
    assert inventory_of(db, b).quantity_available == 0
    assert client.get(f"/api/orders/{order['id']}/purchase-orders").json() == []
    assert reconcile(db) == []


def test_part_stock_waits_and_drafts_purchase_orders_per_supplier(
    client: TestClient, customer: Customer, db: Session
) -> None:
    ksb = make_supplier(db, name="KSB")
    lj = make_supplier(db, name="Lovejoy")
    a = stocked(db, sku="A", name="Coupling", qty=1, supplier=ksb)
    b = stocked(db, sku="B", name="Spblock", qty=0, supplier=lj)
    c = stocked(db, sku="C", name="Seal", qty=10, supplier=ksb)
    a.purchase_cost = 50000
    db.flush()
    q = _quote(client, customer, [_line(a, 3), _line(b, 2), _line(c, 1)])
    order = _accept(client, q["id"])

    # Nothing ships until everything is in: waiting, even though C is covered.
    assert order["status"] == "waiting_stock"
    assert [(ln["reserved"], ln["short"]) for ln in order["lines"]] == [(1, 2), (0, 2), (1, 0)]
    # What is on the shelf is held for this order.
    assert inventory_of(db, a).quantity_available == 0

    pos = client.get(f"/api/orders/{order['id']}/purchase-orders").json()
    by_supplier = {p["supplier"]["name"]: p for p in pos}
    assert set(by_supplier) == {"KSB", "Lovejoy"}
    assert [
        (ln["description"], ln["quantity"], ln["rate_paise"]) for ln in by_supplier["KSB"]["lines"]
    ] == [("Coupling", 2, 50000)]
    assert [(ln["description"], ln["quantity"]) for ln in by_supplier["Lovejoy"]["lines"]] == [
        ("Spblock", 2)
    ]
    assert all(p["status"] == "draft" and re.fullmatch(r"ESPO-\d{2}-\d+", p["number"]) for p in pos)
    seqs = sorted(int(p["number"].rsplit("-", 1)[1]) for p in pos)
    assert seqs[1] == seqs[0] + 1

    # Delivery is refused while waiting.
    r = client.post(f"/api/orders/{order['id']}/deliver")
    assert r.status_code == 409


def test_recheck_after_goods_arrive_makes_it_ready_then_delivery_ships(
    client: TestClient, customer: Customer, db: Session
) -> None:
    from app.constants import ReferenceType
    from app.services import stock
    from app.services.stock import StockRef

    a = stocked(db, sku="A", name="Coupling", qty=1)
    q = _quote(client, customer, [_line(a, 3)])
    order = _accept(client, q["id"])
    assert order["status"] == "waiting_stock"

    stock.receive(db, product_id=a.id, qty=5, ref=StockRef(ReferenceType.MANUAL))
    db.flush()
    order = client.post(f"/api/orders/{order['id']}/recheck").json()
    assert order["status"] == "ready"
    assert order["lines"][0]["reserved"] == 3

    delivered = client.post(f"/api/orders/{order['id']}/deliver").json()
    assert delivered["status"] == "delivered" and delivered["delivered_at"]
    inv = inventory_of(db, a)
    assert (inv.quantity_on_hand, inv.quantity_reserved) == (3, 0)
    assert client.post(f"/api/orders/{order['id']}/deliver").status_code == 409
    assert reconcile(db) == []


def test_free_text_items_block_accepting(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    q = _quote(
        client,
        customer,
        [_line(a, 1), {"description": "Something new", "quantity": 1, "rate_paise": 100}],
    )
    r = client.post(f"/api/quotations/{q['id']}/status", json={"status": "accepted"})
    assert r.status_code == 422
    assert "Something new" in r.json()["error"]["message"]
    # Nothing happened: still pending, no stock held.
    assert client.get(f"/api/quotations/{q['id']}").json()["status"] == "pending"
    assert inventory_of(db, a).quantity_reserved == 0


def test_purchase_order_without_supplier_needs_one_before_sending(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=0)
    q = _quote(client, customer, [_line(a, 2)])
    order = _accept(client, q["id"])
    po = client.get(f"/api/orders/{order['id']}/purchase-orders").json()[0]
    assert po["supplier"] is None
    assert client.post(f"/api/purchase-orders/{po['id']}/sent").status_code == 422
    s = make_supplier(db, name="KSB")
    po = client.post(f"/api/purchase-orders/{po['id']}/supplier", json={"supplier_id": s.id}).json()
    assert po["supplier"]["name"] == "KSB"
    sent = client.post(f"/api/purchase-orders/{po['id']}/sent").json()
    assert sent["status"] == "sent"
    listed = client.get("/api/purchase-orders", params={"q": "KSB"}).json()
    assert listed["total"] == 1


def test_orders_list_filters(client: TestClient, customer: Customer, db: Session) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=10)
    b = stocked(db, sku="B", name="Spblock", qty=0)
    _accept(client, _quote(client, customer, [_line(a, 1)])["id"])
    _accept(client, _quote(client, customer, [_line(b, 1)])["id"])
    assert client.get("/api/orders").json()["total"] == 2
    assert client.get("/api/orders", params={"status": "ready"}).json()["total"] == 1
    assert client.get("/api/orders", params={"q": "emmvee"}).json()["total"] == 2


def test_purchase_order_pdf_splits_gst_into_sgst_and_cgst(
    client: TestClient, customer: Customer, db: Session
) -> None:
    ksb = make_supplier(db, name="KSB Ltd")
    pump = stocked(db, sku="P1", name="MCPK 125-80-200", qty=0, supplier=ksb)
    pump.purchase_cost = 10000000  # Rs. 1,00,000
    pump.gst_rate_bp = 0  # the PO is 18% whatever the product says
    db.flush()
    order = _accept(client, _quote(client, customer, [_line(pump, 2)])["id"])
    po = client.get(f"/api/orders/{order['id']}/purchase-orders").json()[0]
    assert po["lines"][0]["gst_rate_bp"] == 1800

    r = client.get(f"/api/purchase-orders/{po['id']}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    text = " ".join(
        " ".join(pg.extract_text().split()) for pg in pypdf.PdfReader(BytesIO(r.content)).pages
    )
    assert "Purchase Order" in text
    assert po["number"] in text
    assert "M/s. KSB Ltd" in text
    assert "Sub Total Rs. 2,00,000.00" in text
    assert "SGST @ 9% Rs. 18,000.00" in text
    assert "CGST @ 9% Rs. 18,000.00" in text
    assert "Total Rs. 2,36,000.00" in text
    assert "INR Two Lakh Thirty Six Thousand Only" in text
    assert "Authorized Signatory" in text


def test_receiving_a_purchase_order_stocks_inventory_then_readies_the_order(
    client: TestClient, customer: Customer, db: Session
) -> None:
    ksb = make_supplier(db, name="KSB")
    pump = stocked(db, sku="P", name="Pump", qty=1, supplier=ksb)
    order = _accept(client, _quote(client, customer, [_line(pump, 3)])["id"])
    assert order["status"] == "waiting_stock"
    po = client.get(f"/api/orders/{order['id']}/purchase-orders").json()[0]

    received = client.post(f"/api/purchase-orders/{po['id']}/received").json()
    assert received["status"] == "received"
    assert received["received_at"]
    # Into inventory first (1 + 2 on hand), then held for the order.
    inv = inventory_of(db, pump)
    db.refresh(inv)
    assert (inv.quantity_on_hand, inv.quantity_reserved) == (3, 3)
    after = client.get(f"/api/orders/{order['id']}").json()
    assert after["status"] == "ready"
    assert [(ln["reserved"], ln["short"]) for ln in after["lines"]] == [(3, 0)]

    assert client.post(f"/api/purchase-orders/{po['id']}/received").status_code == 409
    assert reconcile(db) == []


def test_adding_stock_in_inventory_fills_waiting_orders_oldest_first(
    client: TestClient, customer: Customer, db: Session
) -> None:
    seal = stocked(db, sku="S", name="Seal", qty=0)
    first = _accept(client, _quote(client, customer, [_line(seal, 2)])["id"])
    second = _accept(client, _quote(client, customer, [_line(seal, 2)])["id"])

    r = client.post(f"/api/inventory/{seal.id}/adjust", json={"delta": 3, "note": "arrived"})
    assert r.status_code == 200
    one = client.get(f"/api/orders/{first['id']}").json()
    two = client.get(f"/api/orders/{second['id']}").json()
    assert (one["status"], one["lines"][0]["reserved"]) == ("ready", 2)
    assert (two["status"], two["lines"][0]["reserved"]) == ("waiting_stock", 1)
    assert reconcile(db) == []
