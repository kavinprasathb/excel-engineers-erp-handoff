"""Notifications are worked out from the data and clear once the work is done."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Customer, Quotation
from tests.test_orders import (  # noqa: F401  (fixtures)
    _accept,
    _line,
    _quote,
    admin,
    client,
    customer,
    stocked,
)


def _keys(api: TestClient) -> dict[str, str]:
    body = api.get("/api/notifications").json()
    return {i["key"]: i["severity"] for i in body["items"]}


def test_notifications_cover_quotes_orders_pos_and_stock(
    client: TestClient,  # noqa: F811
    customer: Customer,  # noqa: F811
    db: Session,
) -> None:
    empty = stocked(db, sku="E", name="Seal", qty=0)
    ready = stocked(db, sku="R", name="Pump", qty=5)

    stale = _quote(client, customer, [_line(ready, 1)])
    db.get(Quotation, stale["id"]).updated_at = datetime.now(UTC) - timedelta(days=20)  # type: ignore[union-attr]
    db.flush()

    ok_order = _accept(client, _quote(client, customer, [_line(ready, 1)])["id"])
    short_order = _accept(client, _quote(client, customer, [_line(empty, 2)])["id"])

    keys = _keys(client)
    assert keys[f"quote-noreply-{stale['id']}"] == "warning"
    assert keys[f"order-ready-{ok_order['id']}"] == "info"
    assert keys[f"stock-critical-{empty.id}"] == "critical"
    po = client.get(f"/api/orders/{short_order['id']}/purchase-orders").json()[0]
    assert f"po-nosupplier-{po['id']}" in keys or f"po-unsent-{po['id']}" in keys

    # Doing the work clears it.
    client.post(f"/api/orders/{ok_order['id']}/deliver")
    client.post(
        f"/api/quotations/{stale['id']}/status",
        json={"status": "declined", "reason": "Price too high"},
    )
    keys = _keys(client)
    assert f"order-ready-{ok_order['id']}" not in keys
    assert f"quote-noreply-{stale['id']}" not in keys
