"""The technical offer format: one column per item, one row per parameter."""

# The fixtures are imported from test_orders and named as test parameters.
# ruff: noqa: F811

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Customer
from tests.test_orders import (  # noqa: F401  (fixtures)
    _accept,
    admin,
    client,
    customer,
    stocked,
)

ROWS = [
    {"section": "Duty", "label": "Capacity (m³/hr)"},
    {"section": "Duty", "label": "Total Head (m)"},
    {"section": "Material Of Construction", "label": "Impeller"},
]


def _tech_quote(client: TestClient, customer: Customer, pid: int) -> dict:
    r = client.post(
        "/api/quotations",
        json={
            "type": "pumps",
            "customer_id": customer.id,
            "quote_date": "2026-06-16",
            "subject": "Offer for ETN pumps",
            "format": "technical",
            "tech_rows": ROWS,
            "scope": "Motor not in our scope",
            "lines": [
                {
                    "product_id": pid,
                    "description": "ETN 100-80-160 CC",
                    "quantity": 2,
                    "rate_paise": 16430000,
                    "service": "MGF feed",
                    "tech_values": ["111", "35", "CF8M"],
                },
                {
                    "product_id": pid,
                    "description": "ETN 65-40-160 CC",
                    "quantity": 2,
                    "rate_paise": 10440000,
                    "service": "UF Feed",
                    "tech_values": ["38", "30", "CF8M"],
                },
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _body(q: dict) -> list[dict]:
    keys = ("kind", "product_id", "description", "quantity", "rate_paise", "service", "tech_values")
    return [{k: ln[k] for k in keys} for ln in q["lines"]]


def test_saved_and_printed_as_a_sheet(client: TestClient, customer: Customer, db: Session) -> None:
    p = stocked(db, sku="ETN", name="ETN pump", qty=10)
    q = _tech_quote(client, customer, p.id)
    assert q["format"] == "technical"
    assert q["tech_rows"] == ROWS and q["scope"] == "Motor not in our scope"
    assert [ln["service"] for ln in q["lines"]] == ["MGF feed", "UF Feed"]
    assert q["lines"][1]["tech_values"] == ["38", "30", "CF8M"]
    # Total = unit price x qty per column, as in the standard format.
    assert q["total_paise"] == 2 * 16430000 + 2 * 10440000
    pdf = client.get(f"/api/quotations/{q['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_pump_offer_is_the_default(client: TestClient, customer: Customer, db: Session) -> None:
    p = stocked(db, sku="A", name="Coupling", qty=5)
    r = client.post(
        "/api/quotations",
        json={
            "type": "spares",
            "customer_id": customer.id,
            "quote_date": "2026-06-16",
            "lines": [{"product_id": p.id, "description": "Coupling", "rate_paise": 100}],
        },
    )
    assert r.json()["format"] == "pump" and r.json()["tech_rows"] == []


def test_revision_copies_the_sheet_and_may_change_it(
    client: TestClient, customer: Customer, db: Session
) -> None:
    p = stocked(db, sku="ETN", name="ETN pump", qty=10)
    q = _tech_quote(client, customer, p.id)
    r1 = client.post(f"/api/quotations/{q['id']}/revise", json={"kind": "revision"}).json()
    assert (r1["format"], r1["tech_rows"], r1["scope"]) == (q["format"], ROWS, q["scope"])
    assert r1["lines"][0]["tech_values"] == ["111", "35", "CF8M"]
    lines = _body(r1)
    lines[0]["tech_values"] = ["120", "35", "CF8M"]
    r = client.patch(f"/api/quotations/{r1['id']}", json={"lines": lines})
    assert r.status_code == 200, r.text
    changes = client.get(f"/api/quotations/{r1['id']}/compare?against={q['id']}").json()
    assert {
        "section": "Technical sheet",
        "item": "MGF feed",
        "field": "Capacity (m³/hr)",
        "before": "111",
        "after": "120",
    } in changes["changes"]


def test_negotiation_changes_prices_only(
    client: TestClient, customer: Customer, db: Session
) -> None:
    p = stocked(db, sku="ETN", name="ETN pump", qty=10)
    q = _tech_quote(client, customer, p.id)
    n1 = client.post(f"/api/quotations/{q['id']}/revise", json={"kind": "negotiation"}).json()
    assert n1["format"] == "technical"
    lines = _body(n1)
    lines[0]["rate_paise"] = 15000000
    ok = client.patch(f"/api/quotations/{n1['id']}", json={"lines": lines})
    assert ok.status_code == 200, ok.text
    lines[0]["tech_values"] = ["999", "35", "CF8M"]
    assert client.patch(f"/api/quotations/{n1['id']}", json={"lines": lines}).status_code == 422
    rows = client.patch(f"/api/quotations/{n1['id']}", json={"tech_rows": ROWS[:1]})
    assert rows.status_code == 422
    assert client.patch(f"/api/quotations/{n1['id']}", json={"scope": "x"}).status_code == 422
    # The negotiated sheet prints, with the old prices beside the new.
    assert client.get(f"/api/quotations/{n1['id']}/pdf").content.startswith(b"%PDF")


def test_accepting_a_sheet_makes_its_order(
    client: TestClient, customer: Customer, db: Session
) -> None:
    p = stocked(db, sku="ETN", name="ETN pump", qty=10)
    q = _tech_quote(client, customer, p.id)
    order = _accept(client, q["id"])
    assert sum(ln["quantity"] for ln in order["lines"]) == 4


def test_sheet_prints_like_a_data_sheet(
    client: TestClient, customer: Customer, db: Session
) -> None:
    """Duty point under each heading, what the price covers, common rows once, no letter text."""
    from io import BytesIO

    import pypdf

    p = stocked(db, sku="ETN", name="ETN pump", qty=10)
    q = _tech_quote(client, customer, p.id)
    r = client.patch(
        f"/api/quotations/{q['id']}",
        json={
            "price_label": "Pump with accessories (without motor)",
            "tech_rows": [*ROWS, {"section": "Motor Data", "label": "Make"}],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["price_label"] == "Pump with accessories (without motor)"
    pdf = client.get(f"/api/quotations/{q['id']}/pdf").content
    text = " ".join(
        " ".join(pg.extract_text() for pg in pypdf.PdfReader(BytesIO(pdf)).pages).split()
    )
    assert "111 m³/hr @ 35 m" in text.replace("\xa0", " ")
    assert "Pump with accessories (without motor)" in text
    assert text.count("CF8M") == 1  # the same for both pumps: printed once, across
    assert "Make" not in text  # empty for every pump
    assert "We thank you" not in text  # a data sheet, not a letter
