"""Multi-item quotation lines (a pump set): one line on the letter, stock per item.

Stock moves only through the order: held on accepting, taken out on Product
Delivery, each item by its quantity per set x the sets quoted. Nothing else
(saving, editing, revising, reopening) touches it, and nothing is done twice.
"""

# The fixtures are imported from test_orders and named as test parameters.
# ruff: noqa: F811

from io import BytesIO

from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models import Customer, Product
from tests.factories import inventory_of
from tests.test_orders import (  # noqa: F401  (fixtures)
    _accept,
    admin,
    client,
    customer,
    stocked,
)


def _set_line(parts: list[tuple[Product, int]], sets: int = 1, **over: object) -> dict:
    line: dict[str, object] = {
        "description": ", ".join(p.name for p, _ in parts),
        "quantity": sets,
        "unit_label": "Set",
        "rate_paise": 5000000,
        "components": [{"product_id": p.id, "name": p.name, "quantity": q} for p, q in parts],
    }
    line.update(over)
    return line


def _create(client: TestClient, customer: Customer, lines: list[dict]) -> dict:
    r = client.post(
        "/api/quotations",
        json={
            "type": "pumps",
            "customer_id": customer.id,
            "quote_date": "2026-10-01",
            "lines": lines,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _stock(db: Session, *products: Product) -> list[tuple[int, int]]:
    """(on hand, reserved) per product."""
    out = []
    for p in products:
        inv = inventory_of(db, p)
        out.append((inv.quantity_on_hand, inv.quantity_reserved))
    return out


def _parts(db: Session) -> tuple[Product, Product, Product]:
    return (
        stocked(db, sku="PMP", name="Pump", qty=10),
        stocked(db, sku="BF", name="Pump Base Frame", qty=10),
        stocked(db, sku="CPL", name="Coupling", qty=10),
    )


def test_saving_editing_and_revising_never_move_stock(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump, frame, coupling = _parts(db)
    before = _stock(db, pump, frame, coupling)
    q = _create(client, customer, [_set_line([(pump, 1), (frame, 2), (coupling, 2)])])
    line = q["lines"][0]
    assert line["product_id"] is None and line["unit_label"] == "Set"
    assert [(c["product_id"], c["quantity"]) for c in line["components"]] == [
        (pump.id, 1),
        (frame.id, 2),
        (coupling.id, 2),
    ]
    # Edit the description freely, change the items: still a draft, no stock moves.
    edited = {
        **{k: line[k] for k in ("kind", "unit_label", "hsn_code", "product_id", "quantity")},
        "description": "Pump set with base frame and coupling, as per enclosed data sheet",
        "rate_paise": 4800000,
        "components": [{"product_id": pump.id, "name": "Pump", "quantity": 1}],
        "deviations": [],
    }
    assert client.patch(f"/api/quotations/{q['id']}", json={"lines": [edited]}).status_code == 200
    n1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    client.get(f"/api/quotations/{n1['id']}")
    assert _stock(db, pump, frame, coupling) == before


def test_accepting_holds_and_delivery_takes_each_item_by_its_own_quantity(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump, frame, coupling = _parts(db)
    q = _create(client, customer, [_set_line([(pump, 1), (frame, 2), (coupling, 2)], sets=2)])
    order = _accept(client, q["id"])

    # One order line per item: quantity per set x 2 sets.
    by_name = {ln["description"]: ln for ln in order["lines"]}
    assert {k: v["quantity"] for k, v in by_name.items()} == {
        "Pump": 2,
        "Pump Base Frame": 4,
        "Coupling": 4,
    }
    assert all(ln["set_description"] == "Pump, Pump Base Frame, Coupling" for ln in order["lines"])
    # The set's value, once: 2 sets x Rs. 50,000.
    assert order["total_paise"] == 2 * 5000000
    assert order["status"] == "ready"
    assert _stock(db, pump, frame, coupling) == [(10, 2), (10, 4), (10, 4)]

    # Accepting again, reopening, rechecking: nothing more is held.
    assert (
        client.post(f"/api/quotations/{q['id']}/status", json={"status": "accepted"}).status_code
        == 409
    )
    client.get(f"/api/quotations/{q['id']}/order")
    client.post(f"/api/orders/{order['id']}/recheck")
    assert _stock(db, pump, frame, coupling) == [(10, 2), (10, 4), (10, 4)]

    # Product Delivery takes each item out by its own quantity, exactly once.
    assert client.post(f"/api/orders/{order['id']}/deliver").status_code == 200
    assert _stock(db, pump, frame, coupling) == [(8, 0), (6, 0), (6, 0)]
    assert client.post(f"/api/orders/{order['id']}/deliver").status_code == 409
    assert _stock(db, pump, frame, coupling) == [(8, 0), (6, 0), (6, 0)]


def test_description_is_never_read_for_stock(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump, frame, coupling = _parts(db)
    # The text names all three, but the line holds only the pump.
    line = _set_line([(pump, 1)], description="Pump, Pump Base Frame, Coupling")
    order = _accept(client, _create(client, customer, [line])["id"])
    assert [ln["description"] for ln in order["lines"]] == ["Pump"]
    assert _stock(db, pump, frame, coupling) == [(10, 1), (10, 0), (10, 0)]


def test_a_short_item_waits_and_only_it_is_bought_in(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump = stocked(db, sku="PMP", name="Pump", qty=1)
    frame = stocked(db, sku="BF", name="Pump Base Frame", qty=0)  # out of stock
    q = _create(client, customer, [_set_line([(pump, 1), (frame, 2)])])
    order = _accept(client, q["id"])
    assert order["status"] == "waiting_stock"
    pos = client.get(f"/api/orders/{order['id']}/purchase-orders").json()
    assert [(ln["description"], ln["quantity"]) for p in pos for ln in p["lines"]] == [
        ("Pump Base Frame", 2)
    ]
    # Never below zero: only what is there is held.
    assert _stock(db, pump, frame) == [(1, 1), (0, 0)]


def test_an_item_removed_from_inventory_blocks_accepting(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump, frame, _ = _parts(db)
    q = _create(client, customer, [_set_line([(pump, 1), (frame, 2)])])
    frame.is_active = False
    db.flush()
    r = client.post(f"/api/quotations/{q['id']}/status", json={"status": "accepted"})
    assert r.status_code == 422 and "Pump Base Frame" in r.text
    assert client.get(f"/api/quotations/{q['id']}").json()["status"] == "pending"
    assert _stock(db, pump, frame) == [(10, 0), (10, 0)]


def test_repeated_items_are_merged_and_bad_ones_refused(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump, frame, _ = _parts(db)
    q = _create(client, customer, [_set_line([(pump, 1), (frame, 2), (pump, 1)])])
    assert [(c["product_id"], c["quantity"]) for c in q["lines"][0]["components"]] == [
        (pump.id, 2),
        (frame.id, 2),
    ]
    bad = _set_line([(pump, 1)])
    bad["components"] = [{"product_id": 999999, "name": "Ghost", "quantity": 1}]
    r = client.post(
        "/api/quotations",
        json={
            "type": "pumps",
            "customer_id": customer.id,
            "quote_date": "2026-10-01",
            "lines": [bad],
        },
    )
    assert r.status_code == 404
    zero = _set_line([(pump, 0)])
    r = client.post(
        "/api/quotations",
        json={
            "type": "pumps",
            "customer_id": customer.id,
            "quote_date": "2026-10-01",
            "lines": [zero],
        },
    )
    assert r.status_code == 422


def test_negotiation_cannot_change_the_items(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump, frame, _ = _parts(db)
    q = _create(client, customer, [_set_line([(pump, 1), (frame, 2)])])
    n1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    ln = n1["lines"][0]
    body = {
        **{k: ln[k] for k in ("kind", "unit_label", "hsn_code", "product_id", "description")},
        "quantity": ln["quantity"],
        "rate_paise": ln["rate_paise"],
        "deviations": ln["deviations"],
        "components": [{"product_id": pump.id, "name": "Pump", "quantity": 1}],
    }
    assert client.patch(f"/api/quotations/{n1['id']}", json={"lines": [body]}).status_code == 422
    body["components"] = ln["components"]
    body["rate_paise"] = 4500000
    assert client.patch(f"/api/quotations/{n1['id']}", json={"lines": [body]}).status_code == 200


def test_the_letter_prints_the_set_as_one_line(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump, frame, coupling = _parts(db)
    q = _create(client, customer, [_set_line([(pump, 1), (frame, 2), (coupling, 2)])])
    pdf = client.get(f"/api/quotations/{q['id']}/pdf").content
    text = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(BytesIO(pdf)).pages)
    assert "Pump, Pump Base Frame, Coupling" in text and "1 Set" in text
    assert "50,000.00" in text


def test_deal_tracker_shows_the_set_once_with_its_stock(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump, frame, coupling = _parts(db)
    q = _create(client, customer, [_set_line([(pump, 1), (frame, 2), (coupling, 2)])])
    _accept(client, q["id"])
    rows = client.get("/api/deal-tracker").json()
    assert len(rows) == 1
    assert rows[0]["description"] == "Pump, Pump Base Frame, Coupling"
    assert rows[0]["from_stock"] == 5 and rows[0]["bought_in"] is None
