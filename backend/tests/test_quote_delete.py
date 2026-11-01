"""Deleting quotes: a whole number, or just its latest negotiation."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Customer
from tests.test_orders import (  # noqa: F401  (fixtures)
    _accept,
    _line,
    _quote,
    admin,
    client,
    customer,
    stocked,
)


def test_delete_latest_negotiation_reopens_the_one_before(
    client: TestClient,  # noqa: F811
    customer: Customer,  # noqa: F811
    db: Session,
) -> None:
    pump = stocked(db, sku="P", name="Pump", qty=5)
    q = _quote(client, customer, [_line(pump, 1)])
    n1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    assert client.get(f"/api/quotations/{q['id']}").json()["status"] == "superseded"

    # Not the initial quote from the negotiation side, and not an older version.
    assert client.delete(f"/api/quotations/{q['id']}", params={"whole": False}).status_code == 409

    assert client.delete(f"/api/quotations/{n1['id']}", params={"whole": False}).status_code == 204
    assert client.get(f"/api/quotations/{n1['id']}").status_code == 404
    assert client.get(f"/api/quotations/{q['id']}").json()["status"] == "pending"


def test_delete_whole_number_removes_every_version(
    client: TestClient,  # noqa: F811
    customer: Customer,  # noqa: F811
    db: Session,
) -> None:
    pump = stocked(db, sku="P", name="Pump", qty=5)
    q = _quote(client, customer, [_line(pump, 1)])
    n1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    assert client.delete(f"/api/quotations/{n1['id']}").status_code == 204
    assert client.get(f"/api/quotations/{q['id']}").status_code == 404
    assert client.get(f"/api/quotations/{n1['id']}").status_code == 404


def test_accepted_quote_cannot_be_deleted(
    client: TestClient,  # noqa: F811
    customer: Customer,  # noqa: F811
    db: Session,
) -> None:
    pump = stocked(db, sku="P", name="Pump", qty=5)
    q = _quote(client, customer, [_line(pump, 1)])
    _accept(client, q["id"])
    r = client.delete(f"/api/quotations/{q['id']}")
    assert r.status_code == 409
    assert "order" in r.text
