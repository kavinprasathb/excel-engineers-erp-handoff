"""Deal Tracker follows one item from quote to delivery."""

from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from app.models import Customer
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


def test_item_is_followed_end_to_end(
    client: TestClient,  # noqa: F811
    customer: Customer,  # noqa: F811
    db: Session,
) -> None:
    ksb = make_supplier(db, name="KSB Ltd")
    frame = stocked(db, sku="BF", name="Base frame", qty=1, supplier=ksb)
    q = _quote(client, customer, [_line(frame, 3)])  # 3 x Rs 1,000
    n1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    client.patch(
        f"/api/quotations/{n1['id']}", json={"lines": [{**_line(frame, 3), "rate_paise": 90000}]}
    )
    order = _accept(client, n1["id"])

    [row] = client.get("/api/deal-tracker").json()
    assert row["stage"] == "Waiting for stock"
    assert (row["quoted_paise"], row["final_paise"], row["discount_paise"]) == (
        100000,
        90000,
        30000,
    )
    assert (row["from_stock"], row["bought_in"], row["supplier"]) == (1, 2, "KSB Ltd")
    assert row["order_no"] == order["number"] and row["po_no"].startswith("ESPO-")

    po_id = row["po_id"]
    client.post(f"/api/purchase-orders/{po_id}/sent")
    client.post(f"/api/purchase-orders/{po_id}/received")
    client.post(f"/api/orders/{order['id']}/deliver")
    [row] = client.get("/api/deal-tracker").json()
    assert row["stage"] == "Delivered"
    assert row["po_sent"] and row["goods_received"] and row["delivered_on"]
    assert row["days_to_deliver"] is not None

    assert client.get("/api/deal-tracker", params={"stage": "Declined"}).json() == []
    assert len(client.get("/api/deal-tracker", params={"q": "base frame"}).json()) == 1

    x = client.get("/api/deal-tracker/export", params={"format": "xlsx"})
    ws = load_workbook(BytesIO(x.content)).active
    # The branding sits above the column headers.
    head = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Client")
    assert ws.cell(head + 1, 4).value == "Base frame"
    p = client.get("/api/deal-tracker/export", params={"format": "pdf"})
    assert p.status_code == 200 and p.content.startswith(b"%PDF")
