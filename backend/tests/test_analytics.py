"""Analytics: conversion, decline reasons, sales, customers, pipeline."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Customer
from app.services.analytics import reason_bucket, with_gst
from tests.test_orders import (  # noqa: F401  (fixtures)
    _accept,
    _line,
    _quote,
    admin,
    client,
    customer,
    stocked,
)

# Quotes are dated 2026-09-26 but delivered today, so the period runs to today.
PERIOD = {"from": "2026-09-01", "to": date.today().isoformat()}


def test_reason_bucket() -> None:
    assert reason_bucket("Price too high") == "Price too high"
    assert reason_bucket("Other: owner travelling") == "Other"
    assert reason_bucket("some old free text") == "Other"


def test_conversion_sales_customers_and_pipeline(
    client: TestClient,  # noqa: F811
    customer: Customer,  # noqa: F811
    db: Session,
) -> None:
    pump = stocked(db, sku="P", name="Pump", qty=10)
    won = _quote(client, customer, [_line(pump, 2)])  # 2 x Rs 1,000
    lost = _quote(client, customer, [_line(pump, 1)])
    open_ = _quote(client, customer, [_line(pump, 1)])

    # Won after one negotiation at a lower rate.
    r = client.post(f"/api/quotations/{won['id']}/revise")
    assert r.status_code == 201, r.text
    n1 = r.json()
    r = client.patch(
        f"/api/quotations/{n1['id']}",
        json={"lines": [{**_line(pump, 2), "rate_paise": 90000}]},
    )
    assert r.status_code == 200, r.text
    order = _accept(client, n1["id"])
    assert client.post(f"/api/orders/{order['id']}/deliver").status_code == 200
    r = client.post(
        f"/api/quotations/{lost['id']}/status",
        json={"status": "declined", "reason": "Price too high"},
    )
    assert r.status_code == 200, r.text

    a = client.get("/api/analytics", params=PERIOD).json()
    conv = a["conversion"]
    assert (conv["quoted"], conv["accepted_count"], conv["declined_count"]) == (3, 1, 1)
    assert conv["pending_count"] == 1
    assert conv["rate_answered"] == 50.0
    assert conv["reasons"] == [{"reason": "Price too high", "count": 1}]

    assert a["sales"]["orders"] == 1
    assert a["sales"]["value_paise"] == with_gst(2 * 90000) == 212400

    [c] = a["customers"]
    assert (c["quotes"], c["accepted"], c["repeat"]) == (3, 1, True)

    assert a["discount"]["discount_paise"] == with_gst(2 * 100000) - with_gst(2 * 90000)
    assert a["discount"]["rows"][0]["rounds"] == 1

    assert a["pipeline"]["count"] == 1
    assert a["pipeline"]["rows"][0]["id"] == open_["id"]

    [p] = a["products"]
    assert (p["times_quoted"], p["times_won"]) == (3, 1)

    # Outside the period: nothing quoted, nothing sold; the pipeline stays.
    b = client.get("/api/analytics", params={"from": "2025-01-01", "to": "2025-12-31"}).json()
    assert b["conversion"]["quoted"] == 0 and b["sales"]["orders"] == 0
    assert b["pipeline"]["count"] == 1


def test_analytics_pdf(client: TestClient) -> None:  # noqa: F811
    r = client.get("/api/analytics/pdf", params=PERIOD)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert f"analytics-2026-09-01-to-{PERIOD['to']}.pdf" in r.headers["content-disposition"]
