"""Description suggestions: what was quoted before, from past letters and the app."""

# The fixtures are imported from test_orders and named as test parameters.
# ruff: noqa: F811

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Customer, PastOfferItem
from tests.test_orders import (  # noqa: F401  (fixtures)
    _quote,
    admin,
    client,
    customer,
    stocked,
)


def _past(
    db: Session, desc: str, rate: int, when: date, customer: Customer | None = None, **kw: str
) -> None:
    db.add(
        PastOfferItem(
            description=desc,
            rate_paise=rate,
            offer_date=when,
            offer_no="ESQSP-25-160",
            customer_name=customer.name if customer else "Other Mills",
            customer_id=customer.id if customer else None,
            **kw,
        )
    )
    db.flush()


def test_every_word_matches_and_the_customer_comes_first(
    client: TestClient, customer: Customer, db: Session
) -> None:
    _past(
        db,
        "Mechanical seal for ETN 65-50-160",
        1080000,
        date(2025, 3, 1),
        moc="Std",
        hsn_code="84139120",
    )
    _past(db, "Mechanical seal K6BM ETN", 1450000, date(2025, 1, 1), customer, part_no="433")
    _past(db, "Shaft ETN 65-50-160", 447500, date(2025, 6, 1))
    r = client.get(
        "/api/quotations/item-suggestions", params={"q": "seal etn", "customer_id": customer.id}
    )
    assert r.status_code == 200, r.text
    got = r.json()
    assert [s["description"] for s in got] == [
        "Mechanical seal K6BM ETN",
        "Mechanical seal for ETN 65-50-160",
    ]
    first = got[0]
    assert first["same_customer"] is True and first["customer_name"] == customer.name
    assert (first["part_no"], first["rate_paise"], first["offer_date"]) == (
        "433",
        1450000,
        "2025-01-01",
    )
    assert got[1]["hsn_code"] == "84139120" and got[1]["source"] == "past offer"


def test_items_quoted_in_the_app_are_suggested_too(
    client: TestClient, customer: Customer, db: Session
) -> None:
    p = stocked(db, sku="CPL", name="Coupling", qty=1)
    _quote(
        client,
        customer,
        [
            {
                "product_id": p.id,
                "description": "Spacer coupling 38 mm",
                "quantity": 1,
                "rate_paise": 250000,
            }
        ],
    )
    got = client.get("/api/quotations/item-suggestions", params={"q": "spacer"}).json()
    assert len(got) == 1 and got[0]["source"] == "quotation"
    assert got[0]["rate_paise"] == 250000 and got[0]["offer_no"].startswith("ESQSP")


def test_same_item_at_same_rate_shows_once(client: TestClient, db: Session) -> None:
    _past(db, "Gland packing set", 145000, date(2025, 1, 1))
    _past(db, "Gland  packing set", 145000, date(2025, 5, 1))
    _past(db, "Gland packing set", 160000, date(2025, 9, 1))
    got = client.get("/api/quotations/item-suggestions", params={"q": "gland"}).json()
    assert [s["rate_paise"] for s in got] == [160000, 145000]
    assert client.get("/api/quotations/item-suggestions", params={"q": "x"}).json() == []
