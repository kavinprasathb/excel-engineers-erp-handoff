"""The three offer layouts: pump offer, spares & service, technical sheet."""

# The fixtures are imported from test_orders and named as test parameters.
# ruff: noqa: F811

import re
from io import BytesIO

import pypdf
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Customer
from tests.test_orders import (  # noqa: F401  (fixtures)
    admin,
    client,
    customer,
    stocked,
)


def _text(pdf: bytes) -> str:
    # Whitespace normalised: a wrapped column heading reads as one phrase.
    return " ".join(" ".join(p.extract_text() for p in pypdf.PdfReader(BytesIO(pdf)).pages).split())


def _create(client: TestClient, customer: Customer, **body: object) -> dict:
    r = client.post(
        "/api/quotations",
        json={"type": "spares", "customer_id": customer.id, "quote_date": "2026-10-15", **body},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _lines(q: dict) -> list[dict]:
    keys = (
        "kind",
        "product_id",
        "description",
        "quantity",
        "rate_paise",
        "unit_label",
        "part_no",
        "moc",
        "delivery",
        "supply_scope",
        "tech_values",
    )
    return [{k: ln[k] for k in keys} for ln in q["lines"]]


def test_spares_offer_groups_by_pump_model_with_chosen_columns(
    client: TestClient, customer: Customer, db: Session
) -> None:
    shaft = stocked(db, sku="S", name="Shaft", qty=5)
    seal = stocked(db, sku="M", name="Mech seal", qty=5)
    q = _create(
        client,
        customer,
        format="spares",
        print_columns=["part_no", "moc", "unit"],
        lines=[
            {"kind": "note", "description": "Model: ETN SYT 080-065-160 EG"},
            {
                "product_id": shaft.id,
                "description": "Shaft",
                "quantity": 1,
                "rate_paise": 447500,
                "part_no": "210",
                "moc": "SS 410",
                "unit_label": "No",
            },
            {
                "product_id": seal.id,
                "description": "Mech seal",
                "quantity": 1,
                "rate_paise": 1080000,
                "part_no": "433",
                "moc": "Std",
                "unit_label": "No",
            },
            {"kind": "note", "description": "Service"},
            {
                "product_id": seal.id,
                "description": "Service charges",
                "quantity": 1,
                "rate_paise": 350000,
                "unit_label": "Day",
            },
        ],
    )
    assert q["format"] == "spares" and q["print_columns"] == ["part_no", "moc", "unit"]
    assert q["lines"][1]["part_no"] == "210" and q["lines"][1]["moc"] == "SS 410"
    text = _text(client.get(f"/api/quotations/{q['id']}/pdf").content)
    for word in ("Part No", "MOC", "Model: ETN SYT 080-065-160 EG", "SS 410", "Subtotal", "15,275"):
        assert word in text, word
    # Switched off: no Delivery column in the item table (the terms may still say it).
    assert "Delivery" not in text.split("Commercial")[0].split("Sl.")[1]


def test_pump_offer_prints_datasheet_scope_and_price(
    client: TestClient, customer: Customer, db: Session
) -> None:
    pump = stocked(db, sku="P", name="ETB 065-040-250 GG", qty=0)
    q = _create(
        client,
        customer,
        type="pumps",
        format="pump",
        tech_rows=[
            {"section": "Duty", "label": "Capacity (m3/hr)"},
            {"section": "Duty", "label": "Total Head (m)"},
            {"section": "Material Of Construction", "label": "Impeller"},
            {"section": "Material Of Construction", "label": "Shaft"},
        ],
        lines=[
            {
                "product_id": pump.id,
                "description": "ETB 065-040-250 GG",
                "quantity": 1,
                "rate_paise": 31250000,
                "unit_label": "Set",
                "tech_values": ["18", "80", "CF8M", ""],
                "supply_scope": "Short coupled pump with 20 Hp 2 pole IE2 motor",
            }
        ],
    )
    text = _text(client.get(f"/api/quotations/{q['id']}/pdf").content)
    for word in (
        "Item 1",
        "ETB 065-040-250 GG",
        "Capacity (m3/hr)",
        "CF8M",
        "Scope of supply",
        "20 Hp 2 pole IE2 motor",
        "3,12,500",
    ):
        assert word in text, word
    # Empty datasheet rows do not print.
    assert not re.search(r"Shaft\s*$", text.split("Scope of supply")[0])


def test_revision_copies_the_layout_and_a_negotiation_keeps_items_fixed(
    client: TestClient, customer: Customer, db: Session
) -> None:
    shaft = stocked(db, sku="S", name="Shaft", qty=5)
    q = _create(
        client,
        customer,
        format="spares",
        print_columns=["moc"],
        lines=[
            {
                "product_id": shaft.id,
                "description": "Shaft",
                "quantity": 1,
                "rate_paise": 1000,
                "moc": "SS 410",
                "part_no": "210",
                "delivery": "Ex stock",
            }
        ],
    )
    r1 = client.post(f"/api/quotations/{q['id']}/revise", json={"kind": "revision"}).json()
    assert (r1["format"], r1["print_columns"]) == ("spares", ["moc"])
    assert (r1["lines"][0]["moc"], r1["lines"][0]["delivery"]) == ("SS 410", "Ex stock")

    n1 = client.post(f"/api/quotations/{r1['id']}/revise", json={"kind": "negotiation"}).json()
    lines = _lines(n1)
    lines[0]["rate_paise"] = 900
    assert client.patch(f"/api/quotations/{n1['id']}", json={"lines": lines}).status_code == 200
    # Which columns print is presentation: a negotiation may change it.
    ok = client.patch(f"/api/quotations/{n1['id']}", json={"print_columns": ["moc", "delivery"]})
    assert ok.status_code == 200 and ok.json()["print_columns"] == ["moc", "delivery"]
    lines[0]["moc"] = "CF8M"
    assert client.patch(f"/api/quotations/{n1['id']}", json={"lines": lines}).status_code == 422
    # The negotiated spares offer prints with the earlier rate beside the new one.
    text = _text(client.get(f"/api/quotations/{n1['id']}/pdf").content)
    assert "Old Rate" in text

    changes = client.get(f"/api/quotations/{r1['id']}/compare?against={q['id']}").json()
    assert changes["changes"] == []
