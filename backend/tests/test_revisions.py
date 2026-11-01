"""Revised quotations (R) and negotiations (N): the three workflows, and what reports show."""

# The fixtures are imported from test_orders and named as test parameters.
# ruff: noqa: F811

from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook  # type: ignore[import-untyped]
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


def _revise(client: TestClient, qid: int, kind: str | None = None) -> dict:
    body = {"kind": kind} if kind else None
    r = client.post(f"/api/quotations/{qid}/revise", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _lines(q: dict) -> list[dict]:
    keys = ("kind", "unit_label", "hsn_code", "product_id", "description", "quantity", "rate_paise")
    return [{**{k: ln[k] for k in keys}, "deviations": ln["deviations"]} for ln in q["lines"]]


def _set_rate(client: TestClient, q: dict, rate: int) -> dict:
    lines = _lines(q)
    lines[0]["rate_paise"] = rate
    r = client.patch(f"/api/quotations/{q['id']}", json={"lines": lines})
    assert r.status_code == 200, r.text
    return r.json()


def _set_qty(client: TestClient, q: dict, qty: int) -> dict:
    lines = _lines(q)
    lines[0]["quantity"] = qty
    r = client.patch(f"/api/quotations/{q['id']}", json={"lines": lines})
    assert r.status_code == 200, r.text
    return r.json()


def _history(client: TestClient, qid: int) -> list[dict]:
    return client.get(f"/api/quotations/{qid}/revisions").json()


# --- the three scenarios ------------------------------------------------------------


def test_scenario_a_product_changes_make_sequential_revisions(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    q = _quote(client, customer, [_line(a, 1)])
    base = q["number"]
    r1 = _set_qty(client, _revise(client, q["id"], "revision"), 2)
    r2 = _set_qty(client, _revise(client, r1["id"], "revision"), 3)
    r3 = _revise(client, r2["id"], "revision")
    assert [r1["number"], r2["number"], r3["number"]] == [
        f"{base}-R1",
        f"{base}-R2",
        f"{base}-R3",
    ]
    assert (r3["rev_no"], r3["neg_no"], r3["base_number"]) == (3, 0, base)
    assert r3["stage_label"] == "Revision R3"
    # Each linked to the one before; nothing overwritten.
    assert r2["supersedes_id"] == r1["id"] and r3["supersedes_id"] == r2["id"]
    hist = _history(client, r3["id"])
    assert [h["number"] for h in hist] == [base, f"{base}-R1", f"{base}-R2", f"{base}-R3"]
    assert [h["status"] for h in hist] == ["superseded"] * 3 + ["pending"]
    assert client.get(f"/api/quotations/{q['id']}").json()["lines"][0]["quantity"] == 1
    # Only the latest version moves on.
    assert (
        client.post(f"/api/quotations/{r2['id']}/status", json={"status": "accepted"}).status_code
        == 409
    )


def test_scenario_b_price_only_goes_straight_to_negotiation(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    q = _quote(client, customer, [_line(a, 1)])
    base = q["number"]
    n1 = _set_rate(client, _revise(client, q["id"]), 90000)  # default kind: negotiation
    n2 = _set_rate(client, _revise(client, n1["id"], "negotiation"), 85000)
    n3 = _revise(client, n2["id"], "negotiation")
    assert [n1["number"], n2["number"], n3["number"]] == [f"{base}N1", f"{base}N2", f"{base}N3"]
    assert (n3["rev_no"], n3["neg_no"]) == (0, 3)
    # Every price kept.
    rates = [h["id"] for h in _history(client, n3["id"])]
    got = [client.get(f"/api/quotations/{i}").json()["lines"][0]["rate_paise"] for i in rates]
    assert got == [100000, 90000, 85000, 85000]


def test_scenario_c_revisions_then_negotiation(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    q = _quote(client, customer, [_line(a, 1)])
    base = q["number"]
    r1 = _set_qty(client, _revise(client, q["id"], "revision"), 2)
    r2 = _set_qty(client, _revise(client, r1["id"], "revision"), 3)
    n1 = _set_rate(client, _revise(client, r2["id"], "negotiation"), 90000)
    n2 = _set_rate(client, _revise(client, n1["id"], "negotiation"), 80000)
    assert [n1["number"], n2["number"]] == [f"{base}-R2N1", f"{base}-R2N2"]
    assert n2["stage_label"] == "Revision R2 · Negotiation N2"
    assert n2["lines"][0]["quantity"] == 3  # the revision's content carried on

    # A product change after negotiating is a new revision, negotiations start again.
    r3 = _revise(client, n2["id"], "revision")
    n = _revise(client, r3["id"])
    assert (r3["number"], n["number"]) == (f"{base}-R3", f"{base}-R3N1")

    # Accepting the latest makes one order, numbered after the original quote.
    order = _accept(client, n["id"])
    assert order["number"] == f"ORD-{base}"
    numbers = [h["number"] for h in _history(client, n["id"])]
    assert len(numbers) == len(set(numbers)) == 7


def test_negotiation_changes_prices_only(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    q = _quote(client, customer, [_line(a, 1)])
    n1 = _revise(client, q["id"])
    lines = _lines(n1)
    lines[0]["quantity"] = 4
    r = client.patch(f"/api/quotations/{n1['id']}", json={"lines": lines})
    assert r.status_code == 422 and "revised quotation" in r.text
    lines = _lines(n1)
    lines[0]["deviations"] = [{"label": "Pump Model", "value": "X"}]
    assert client.patch(f"/api/quotations/{n1['id']}", json={"lines": lines}).status_code == 422
    # Price and commercial terms are fine.
    assert _set_rate(client, n1, 95000)["lines"][0]["rate_paise"] == 95000
    # A revised quotation may change anything.
    r1 = _revise(client, n1["id"], "revision")
    assert _set_qty(client, r1, 4)["lines"][0]["quantity"] == 4


def test_lists_split_by_stage(client: TestClient, customer: Customer, db: Session) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    plain = _quote(client, customer, [_line(a, 1)])
    revised = _revise(client, _quote(client, customer, [_line(a, 1)])["id"], "revision")
    negotiated = _revise(client, _quote(client, customer, [_line(a, 1)])["id"])

    def ids(stage: str) -> set[int]:
        rows = client.get("/api/quotations", params={"stage": stage}).json()["items"]
        return {r["id"] for r in rows}

    assert ids("quotation") == {plain["id"]}
    assert ids("revised") == {revised["id"]}
    assert ids("negotiation") == {negotiated["id"]}
    # The old flag still works, and every number is listed once.
    old = client.get("/api/quotations", params={"negotiated": True}).json()["items"]
    assert {r["id"] for r in old} == {negotiated["id"]}
    everything = client.get("/api/quotations").json()["items"]
    assert len(everything) == 3


def test_compare_any_two_versions(client: TestClient, customer: Customer, db: Session) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    q = _quote(client, customer, [_line(a, 1)])
    r1 = _set_qty(client, _revise(client, q["id"], "revision"), 2)
    n1 = _set_rate(client, _revise(client, r1["id"]), 90000)
    c = client.get(f"/api/quotations/{n1['id']}/compare", params={"against": q["id"]}).json()
    assert c["lines"][0]["old_quantity"] == 1 and c["lines"][0]["new_quantity"] == 2
    assert c["lines"][0]["old_rate_paise"] == 100000 and c["lines"][0]["new_rate_paise"] == 90000
    other = _quote(client, customer, [_line(a, 1)])
    r = client.get(f"/api/quotations/{n1['id']}/compare", params={"against": other["id"]})
    assert r.status_code == 422


# --- reports ------------------------------------------------------------------------


def test_quote_history_labels_every_version_and_counts_the_deal_once(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    q = _quote(client, customer, [_line(a, 1)])
    r1 = _set_rate(client, _revise(client, q["id"], "revision"), 95000)
    n1 = _set_rate(client, _revise(client, r1["id"]), 90000)
    rows = client.get("/api/quotations/history").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["original_number"] == q["number"] and row["number"] == n1["number"]
    assert [s["label"] for s in row["stages"]] == ["R1", "R1N1"]
    assert (row["quoted_paise"], row["revised_paise"], row["current_paise"]) == (
        100000,
        95000,
        90000,
    )
    assert row["stage_label"] == "Revision R1 · Negotiation N1"
    x = client.get("/api/quotations/history/export", params={"format": "xlsx"})
    assert x.status_code == 200
    ws = load_workbook(BytesIO(x.content)).active
    text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
    assert "R1 > R1N1" in text and q["number"] in text
    assert client.get("/api/quotations/history/export", params={"format": "pdf"}).status_code == 200


def test_deal_tracker_one_deal_with_its_references(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    q = _quote(client, customer, [_line(a, 1)])
    r1 = _set_rate(client, _revise(client, q["id"], "revision"), 95000)
    rows = client.get("/api/deal-tracker").json()
    assert len(rows) == 1 and rows[0]["stage"] == "Revised quotation"
    assert rows[0]["revision_ref"] == f"{q['number']}-R1" and rows[0]["negotiation_ref"] == ""

    n1 = _set_rate(client, _revise(client, r1["id"]), 90000)
    rows = client.get("/api/deal-tracker").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["stage"] == "In negotiation"
    assert row["quote_no"] == q["number"] and row["original_id"] == q["id"]
    assert row["negotiation_ref"] == n1["number"] and row["quotation_id"] == n1["id"]
    assert row["history"] == "Original → R1 → R1N1"
    assert (row["quoted_paise"], row["revised_paise"], row["final_paise"]) == (
        100000,
        95000,
        90000,
    )
    assert (row["revisions"], row["negotiations"]) == (1, 1)

    _accept(client, n1["id"])
    rows = client.get("/api/deal-tracker").json()
    assert len(rows) == 1 and rows[0]["result"] == "Accepted" and rows[0]["order_no"]
    for fmt in ("xlsx", "pdf"):
        assert client.get("/api/deal-tracker/export", params={"format": fmt}).status_code == 200


def test_analytics_counts_a_revised_and_negotiated_deal_once(
    client: TestClient, customer: Customer, db: Session
) -> None:
    a = stocked(db, sku="A", name="Coupling", qty=5)
    q = _quote(client, customer, [_line(a, 1)])
    r1 = _set_rate(client, _revise(client, q["id"], "revision"), 95000)
    n1 = _set_rate(client, _revise(client, r1["id"]), 90000)
    _accept(client, n1["id"])
    rep = client.get("/api/analytics").json()
    conv = rep["conversion"]
    assert (conv["quoted"], conv["accepted_count"], conv["pending_count"]) == (1, 1, 0)
    d = rep["discount"]
    assert d["won_quotes"] == 1 and len(d["rows"]) == 1
    row = d["rows"][0]
    assert row["original_number"] == q["number"]
    assert (row["revisions"], row["negotiations"]) == (1, 1)
    # Current value is the latest version's (with 18% GST), not a sum of versions.
    assert row["final_paise"] == 106200 and row["revised_paise"] == 112100
    assert row["first_paise"] == 118000
