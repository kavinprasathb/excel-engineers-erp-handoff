"""Quotations: numbering, editing, revisions, status and the PDF."""

import threading
from collections.abc import Iterator
from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.constants import QuotationStatus, QuotationType, UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import AppSettings, Customer, Quotation, QuotationCounter, User
from app.schemas.quotation import QuotationCreate
from app.security import hash_password
from app.services import quotations as service
from tests.factories import make_product


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="quotes-admin@excelengineers.in",
        full_name="Admin",
        password_hash=hash_password("correct-horse-battery"),
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
    c = Customer(
        name="Steel Authority of India Ltd.",
        billing_address_line1="Salem Steel Plant",
        billing_city="Salem",
    )
    db.add(c)
    db.flush()
    return c


_COUPLING: dict[str, int] = {}


@pytest.fixture(autouse=True)
def coupling(db: Session) -> None:
    """The item the default quote offers, as a catalogue product.

    Accepting a quote makes an order and checks stock, which needs every item
    to be a product; free text is refused. Tests that exercise free text
    pass their own lines.
    """
    p = make_product(db, sku="RNS-125", name="RNS 125/100 Coupling", on_hand=0)
    _COUPLING["id"] = p.id


def _body(customer: Customer, **over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "type": "spares",
        "customer_id": customer.id,
        "quote_date": "2026-04-20",
        "subject": "Offer for RNS Coupling",
        "reference": "Telecon",
        "lines": [
            {
                "product_id": _COUPLING["id"],
                "description": "RNS 125/100 Coupling",
                "quantity": 1,
                "rate_paise": 1476000,
            },
        ],
    }
    base.update(over)
    return base


# --- numbering -------------------------------------------------------------


def test_numbers_follow_the_client_format(client: TestClient, customer: Customer) -> None:
    a = client.post("/api/quotations", json=_body(customer)).json()
    b = client.post("/api/quotations", json=_body(customer, type="pumps")).json()
    c = client.post("/api/quotations", json=_body(customer)).json()
    assert a["number"] == "ESQSP-26-1"
    assert b["number"] == "ESQP-26-1"  # each type has its own sequence
    assert c["number"] == "ESQSP-26-2"


def test_sequence_restarts_each_year(client: TestClient, customer: Customer) -> None:
    client.post("/api/quotations", json=_body(customer))
    nxt = client.post("/api/quotations", json=_body(customer, quote_date="2027-01-05")).json()
    assert nxt["number"] == "ESQSP-27-1"


def test_concurrent_creates_never_share_a_number(engine: Engine) -> None:
    """Eight threads, eight distinct numbers. The counter row lock is what makes this pass.

    Uses its own committed rows rather than the `db` fixture: that fixture's
    commit is a savepoint inside a transaction other connections cannot see.
    """
    with Session(engine) as setup:
        cust = Customer(name="Concurrency Test Customer")
        setup.add(cust)
        setup.commit()
        customer_id = cust.id

    numbers: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            with Session(engine) as s:
                q = service.create_quotation(
                    s,
                    QuotationCreate(
                        type=QuotationType.VALVES,
                        customer_id=customer_id,
                        quote_date=date(2026, 6, 1),
                    ),
                    actor_id=None,
                )
                with lock:
                    numbers.append(q.number)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        assert errors == []
        assert len(set(numbers)) == 8
    finally:
        with Session(engine) as s:
            for q in s.execute(
                select(Quotation).where(Quotation.customer_id == customer_id)
            ).scalars():
                s.delete(q)
            s.flush()
            for c in s.execute(select(QuotationCounter)).scalars():
                s.delete(c)
            cust_row = s.get(Customer, customer_id)
            if cust_row is not None:
                s.delete(cust_row)
            s.commit()


# --- content ---------------------------------------------------------------


def test_create_copies_default_terms_for_the_type(client: TestClient, customer: Customer) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    labels = [t["label"] for t in q["terms"]]
    assert labels[:2] == ["Price Basis", "GST"]
    assert any("No Warranty" in t["text"] for t in q["terms"])
    assert all(t["included"] for t in q["terms"])
    assert q["total_paise"] == 1476000
    assert q["is_latest"] is True


def test_defaults_come_from_settings_when_edited(
    client: TestClient, customer: Customer, db: Session
) -> None:
    settings = db.get(AppSettings, 1)
    assert settings is not None
    settings.quotation_terms_defaults = {"spares": [{"label": "Only", "text": "one line"}]}
    db.flush()
    q = client.post("/api/quotations", json=_body(customer)).json()
    assert [t["label"] for t in q["terms"]] == ["Only"]


def test_product_line_keeps_its_own_rate_no_floor(
    client: TestClient, customer: Customer, db: Session
) -> None:
    product = make_product(db, name="Gasket")
    product.sell_price = 50000
    db.flush()
    body = _body(
        customer,
        lines=[
            {
                "product_id": product.id,
                "description": "Gasket",
                "quantity": 3,
                "rate_paise": 10000,
            }
        ],
    )
    r = client.post("/api/quotations", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["lines"][0]["value_paise"] == 30000


def test_unknown_product_is_a_404(client: TestClient, customer: Customer) -> None:
    body = _body(
        customer,
        lines=[{"product_id": 999999, "description": "x", "quantity": 1, "rate_paise": 1}],
    )
    assert client.post("/api/quotations", json=body).status_code == 404


def test_patch_replaces_lines_and_terms(client: TestClient, customer: Customer) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    r = client.patch(
        f"/api/quotations/{q['id']}",
        json={
            "subject": "Offer for spares",
            "lines": [
                {"description": "A", "quantity": 2, "rate_paise": 100},
                {"description": "B", "quantity": 1, "rate_paise": 300},
            ],
            "terms": [{"label": "Delivery", "text": "3 weeks", "included": False}],
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["subject"] == "Offer for spares"
    assert [ln["description"] for ln in out["lines"]] == ["A", "B"]
    assert out["total_paise"] == 500
    assert out["terms"] == [
        {**out["terms"][0], "label": "Delivery", "text": "3 weeks", "included": False}
    ]


# --- revisions and status --------------------------------------------------


def test_revise_supersedes_and_copies(client: TestClient, customer: Customer) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    r = client.post(f"/api/quotations/{q['id']}/revise")
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["number"] == "ESQSP-26-1N1"
    assert new["revision"] == 1
    assert new["supersedes_id"] == q["id"]
    assert new["status"] == "pending"
    assert [ln["description"] for ln in new["lines"]] == ["RNS 125/100 Coupling"]
    assert [ln["rate_paise"] for ln in new["lines"]] == [1476000]
    assert new["total_paise"] == q["total_paise"]
    assert [(t["label"], t["text"], t["included"]) for t in new["terms"]] == [
        (t["label"], t["text"], t["included"]) for t in q["terms"]
    ]

    old = client.get(f"/api/quotations/{q['id']}").json()
    assert old["status"] == "superseded"
    assert old["is_latest"] is False

    again = client.post(f"/api/quotations/{new['id']}/revise").json()
    assert again["number"] == "ESQSP-26-1N2"


def test_superseded_cannot_be_edited_but_can_start_a_negotiation(
    client: TestClient, customer: Customer
) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    r1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    r = client.patch(f"/api/quotations/{q['id']}", json={"subject": "x"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "quotation_locked"
    # Negotiating again *from the initial quote* is allowed: the content comes
    # from R0, the number continues from the highest revision, and R1 is
    # superseded because only one version can be live.
    client.patch(f"/api/quotations/{r1['id']}", json={"subject": "changed in R1"})
    r2 = client.post(f"/api/quotations/{q['id']}/revise")
    assert r2.status_code == 201, r2.text
    assert r2.json()["number"] == "ESQSP-26-1N2"
    assert r2.json()["subject"] == "Offer for RNS Coupling"
    assert r2.json()["supersedes_id"] == q["id"]
    assert client.get(f"/api/quotations/{r1['id']}").json()["status"] == "superseded"


def test_accepted_number_is_final(client: TestClient, customer: Customer) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    r1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    client.post(f"/api/quotations/{r1['id']}/status", json={"status": "accepted"})
    for qid in (q["id"], r1["id"]):
        r = client.post(f"/api/quotations/{qid}/revise")
        assert r.status_code == 409
        assert "final" in r.json()["error"]["message"]


def test_changes_lists_what_a_negotiation_altered(client: TestClient, customer: Customer) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    assert client.get(f"/api/quotations/{q['id']}/changes").json() == []
    # Quantity and items change: a revised quotation (a negotiation is price only).
    r1 = client.post(f"/api/quotations/{q['id']}/revise", json={"kind": "revision"}).json()
    client.patch(
        f"/api/quotations/{r1['id']}",
        json={
            "lines": [
                {"description": "RNS 125/100 Coupling", "quantity": 2, "rate_paise": 1350000},
                {"description": "Gasket set", "quantity": 1, "rate_paise": 50000},
            ],
            "terms": [{"label": "Delivery", "text": "3 weeks", "included": True}],
        },
    )
    changes = client.get(f"/api/quotations/{r1['id']}/changes").json()
    by = {(c["section"], c["item"], c["field"]): (c["before"], c["after"]) for c in changes}
    assert by[("Items", "RNS 125/100 Coupling", "Quantity")] == ("1", "2")
    assert by[("Items", "RNS 125/100 Coupling", "Rate")] == ("1476000", "1350000")
    assert by[("Items", "Gasket set", "Line")] == ("—", "Gasket set")
    assert by[("Terms", "Delivery", "Text")] == ("2 weeks", "3 weeks")
    assert by[("Terms", "Price Basis", "Term")] == ("present", "—")
    assert ("Header", "", "Subject") not in by


def test_dashboard_buckets_by_stage(client: TestClient, customer: Customer) -> None:
    a = client.post("/api/quotations", json=_body(customer)).json()  # awaiting
    b = client.post("/api/quotations", json=_body(customer)).json()
    b1 = client.post(f"/api/quotations/{b['id']}/revise").json()  # negotiating, stage 1
    c = client.post("/api/quotations", json=_body(customer)).json()
    c1 = client.post(f"/api/quotations/{c['id']}/revise").json()
    c2 = client.post(f"/api/quotations/{c1['id']}/revise").json()
    client.post(f"/api/quotations/{c2['id']}/status", json={"status": "accepted"})  # stage 2
    d = client.post("/api/quotations", json=_body(customer)).json()
    client.post(
        f"/api/quotations/{d['id']}/status", json={"status": "declined", "reason": "Too costly"}
    )

    dash = client.get("/api/quotations/dashboard").json()
    counts = {k: v["count"] for k, v in dash["buckets"].items()}
    assert counts == {"awaiting": 1, "negotiating": 1, "accepted": 1, "declined": 1}
    assert dash["buckets"]["accepted"]["total_paise"] == 1476000
    assert dash["awaiting"][0]["id"] == a["id"]
    assert dash["negotiating"][0]["id"] == b1["id"] and dash["negotiating"][0]["stage"] == 1
    assert dash["accepted"][0]["stage"] == 2
    assert dash["declined"][0]["decline_reason"] == "Too costly"


def test_decline_requires_a_reason_and_keeps_it(client: TestClient, customer: Customer) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    r = client.post(f"/api/quotations/{q['id']}/status", json={"status": "declined"})
    assert r.status_code == 422
    assert "reason" in r.json()["error"]["message"]
    r = client.post(
        f"/api/quotations/{q['id']}/status", json={"status": "declined", "reason": "   "}
    )
    assert r.status_code == 422
    r = client.post(
        f"/api/quotations/{q['id']}/status",
        json={"status": "declined", "reason": "Went with a local supplier at 12,000."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "declined"
    assert r.json()["decline_reason"] == "Went with a local supplier at 12,000."
    # The revision is a fresh offer: no reason carried over.
    new = client.post(f"/api/quotations/{q['id']}/revise").json()
    assert new["decline_reason"] == ""


def test_status_transitions(client: TestClient, customer: Customer) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    r = client.post(f"/api/quotations/{q['id']}/status", json={"status": "accepted"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"
    # Decided quotes are locked...
    assert client.patch(f"/api/quotations/{q['id']}", json={"subject": "x"}).status_code == 409
    assert (
        client.post(f"/api/quotations/{q['id']}/status", json={"status": "declined"}).status_code
        == 409
    )
    # ...and an accepted one is final: no further negotiation.
    assert client.post(f"/api/quotations/{q['id']}/revise").status_code == 409
    # A declined one, on the other hand, is exactly what gets re-quoted.
    d = client.post("/api/quotations", json=_body(customer)).json()
    client.post(f"/api/quotations/{d['id']}/status", json={"status": "declined", "reason": "Price"})
    new = client.post(f"/api/quotations/{d['id']}/revise").json()
    assert new["status"] == "pending"
    # Nobody sets superseded by hand.
    assert (
        client.post(
            f"/api/quotations/{new['id']}/status", json={"status": "superseded"}
        ).status_code
        == 409
    )


# --- list --------------------------------------------------------------------


def test_list_filters_and_searches(client: TestClient, customer: Customer) -> None:
    a = client.post("/api/quotations", json=_body(customer)).json()
    client.post("/api/quotations", json=_body(customer, type="pumps", subject="Offer for pump"))
    client.post(
        f"/api/quotations/{a['id']}/status", json={"status": "declined", "reason": "Too costly"}
    )

    assert client.get("/api/quotations").json()["total"] == 2
    assert client.get("/api/quotations", params={"type": "pumps"}).json()["total"] == 1
    assert client.get("/api/quotations", params={"status": "declined"}).json()["total"] == 1
    assert client.get("/api/quotations", params={"q": "ESQP-26"}).json()["total"] == 1
    assert client.get("/api/quotations", params={"q": "steel authority"}).json()["total"] == 2
    row = client.get("/api/quotations", params={"q": "coupling"}).json()["items"][0]
    assert row["customer"]["name"] == customer.name
    assert row["total_paise"] == 1476000
    assert client.get("/api/quotations", params={"status": "junk"}).status_code == 422


# --- pdf ---------------------------------------------------------------------


def test_pdf_renders_the_letter(client: TestClient, customer: Customer) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    r = client.get(f"/api/quotations/{q['id']}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "ESQSP-26-1.pdf" in r.headers["content-disposition"]
    pages = PdfReader(__import__("io").BytesIO(r.content)).pages
    text = " ".join(" ".join(pg.extract_text() for pg in pages).split())
    for needle in (
        "Quotation",
        "ESQSP-26-1",
        "20 Apr 2026",
        "M/s. Steel Authority of India Ltd.",
        "Offer for RNS Coupling",
        "Telecon",
        "our offer for RNS Coupling.",
        "RNS 125/100 Coupling",
        "14,760.00",
        "No Warranty / Guarantee for spares",
        "SGST @ 9%",
        "Amount in words",
        "M. Rajamuthaiyah",
    ):
        assert needle in text, needle


def test_pdf_omits_unticked_terms_and_totals_many_lines(
    client: TestClient, customer: Customer
) -> None:
    q = client.post(
        "/api/quotations",
        json=_body(
            customer,
            lines=[
                {"description": "A <b>bold</b>", "quantity": 2, "rate_paise": 100000},
                {"description": "B", "quantity": 1, "rate_paise": 250000},
            ],
            terms=[
                {"label": "Delivery", "text": "3 weeks", "included": True},
                {"label": "Secret", "text": "do not print", "included": False},
            ],
        ),
    ).json()
    # Every page: a pump offer's item cards can push the terms onto page 2.
    reader = PdfReader(
        __import__("io").BytesIO(client.get(f"/api/quotations/{q['id']}/pdf").content)
    )
    text = " ".join(p.extract_text() for p in reader.pages)
    assert "Total" in text and "4,500.00" in text
    assert "3 weeks" in text
    assert "Secret" not in text
    assert "A <b>bold</b>" in text  # user text is escaped, not interpreted


def test_status_enum_is_what_the_frontend_expects() -> None:
    assert [s.value for s in QuotationStatus] == ["pending", "accepted", "declined", "superseded"]


def test_list_shows_one_row_per_number_and_history_is_separate(
    client: TestClient, customer: Customer
) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    r1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    r2 = client.post(f"/api/quotations/{r1['id']}/revise").json()
    client.post("/api/quotations", json=_body(customer, type="pumps"))

    listed = client.get("/api/quotations").json()
    assert listed["total"] == 2
    assert {row["number"] for row in listed["items"]} == {"ESQSP-26-1N2", "ESQP-26-1"}
    assert client.get("/api/quotations", params={"all_revisions": "true"}).json()["total"] == 4

    history = client.get(f"/api/quotations/{q['id']}/revisions").json()
    assert [h["number"] for h in history] == ["ESQSP-26-1", "ESQSP-26-1N1", "ESQSP-26-1N2"]
    assert [h["status"] for h in history] == ["superseded", "superseded", "pending"]
    assert history[-1]["id"] == r2["id"]


# --- technical deviation, per item ----------------------------------------------


def _technical(customer: Customer) -> dict[str, object]:
    return _body(
        customer,
        type="pumps",
        subject="Offer for supply of KSB make MCPK pump with motor",
        reference="PR no 10208801",
        lines=[
            {"kind": "note", "description": "KSB Make"},
            {"description": "M CPK 125-80-200", "rate_paise": 21600000, "unit_label": "Each"},
            {"description": "P JHL 123-07-678", "rate_paise": 21000000, "unit_label": "Each"},
            {"kind": "note", "description": "Fitted with Mechanical Seal (Bare Pump)"},
        ],
    )


def test_each_item_starts_with_the_default_deviation_rows_and_notes_have_none(
    client: TestClient, customer: Customer
) -> None:
    r = client.post("/api/quotations", json=_technical(customer))
    assert r.status_code == 201, r.text
    q = r.json()
    # The pump offer is the default layout; "specs" (the old quote-level block) is gone.
    assert q["format"] == "pump" and "specs" not in q
    assert [ln["kind"] for ln in q["lines"]] == ["note", "product", "product", "note"]
    for ln in q["lines"]:
        if ln["kind"] == "note":
            assert ln["deviations"] == []
        else:
            assert [d["label"] for d in ln["deviations"]][:2] == ["Pump Model", "Liquid Handled"]
            assert all(d["value"] == "" for d in ln["deviations"])
    # A note never carries a price, whatever was sent.
    assert q["lines"][0]["rate_paise"] == 0 and q["lines"][0]["quantity"] == 1
    assert q["total_paise"] == 42600000


def test_format_is_no_longer_accepted(client: TestClient, customer: Customer) -> None:
    assert client.post("/api/quotations", json=_body(customer, format="2")).status_code == 422
    assert client.post("/api/quotations", json=_body(customer, specs=[])).status_code == 422


def test_deviations_belong_to_their_line_and_are_copied_on_revise(
    client: TestClient, customer: Customer
) -> None:
    q = client.post("/api/quotations", json=_technical(customer)).json()
    lines = q["lines"]
    lines[1]["deviations"] = [
        {"label": "Pump Model", "value": "MCPK 125-80-200"},
        {"label": "Casing", "value": "CD4MCU"},
        {"label": "  ", "value": "dropped: no label"},
    ]
    lines[2]["deviations"] = []
    body = [
        {
            k: ln[k]
            for k in (
                "kind",
                "unit_label",
                "hsn_code",
                "product_id",
                "description",
                "quantity",
                "rate_paise",
                "deviations",
            )
        }
        for ln in lines
    ]
    r = client.patch(f"/api/quotations/{q['id']}", json={"lines": body})
    assert r.status_code == 200, r.text
    got = r.json()["lines"]
    assert got[1]["deviations"] == [
        {"label": "Pump Model", "value": "MCPK 125-80-200"},
        {"label": "Casing", "value": "CD4MCU"},
    ]
    assert got[2]["deviations"] == []
    # Technical deviation changes are a revised quotation, not a negotiation.
    new = client.post(f"/api/quotations/{q['id']}/revise", json={"kind": "revision"}).json()
    assert [ln["deviations"] for ln in new["lines"]] == [ln["deviations"] for ln in got]

    body[1]["deviations"] = [{"label": "Pump Model", "value": "MCPK 150"}]
    client.patch(f"/api/quotations/{new['id']}", json={"lines": body})
    changes = client.get(f"/api/quotations/{new['id']}/changes").json()
    dev = [c for c in changes if c["section"] == "Technical deviation"]
    assert {(c["field"], c["before"], c["after"]) for c in dev} == {
        ("Pump Model", "MCPK 125-80-200", "MCPK 150"),
        ("Casing", "CD4MCU", "—"),
    }


def test_pdf_prints_only_filled_deviation_rows_under_their_item(
    client: TestClient, customer: Customer
) -> None:
    q = client.post("/api/quotations", json=_technical(customer)).json()
    body = [
        {
            k: ln[k]
            for k in (
                "kind",
                "unit_label",
                "hsn_code",
                "product_id",
                "description",
                "quantity",
                "rate_paise",
                "deviations",
            )
        }
        for ln in q["lines"]
    ]
    body[1]["deviations"] = [
        {"label": "Pump Model", "value": "MCPK 125-80-200"},
        {"label": "Liquid Handled", "value": ""},
    ]
    client.patch(f"/api/quotations/{q['id']}", json={"lines": body})
    r = client.get(f"/api/quotations/{q['id']}/pdf")
    assert r.status_code == 200
    reader = PdfReader(__import__("io").BytesIO(r.content))
    text = "\n".join(p.extract_text() for p in reader.pages)
    for needle in (
        "we are submitting our offer for",
        "Technical Deviation",
        "Pump Model",
        "MCPK 125-80-200",
        "KSB Make",
        "2,16,000.00",
        "2,10,000.00",
        "Each",
        "Fitted with Mechanical Seal (Bare Pump)",
        "GSTIN: 33AAIFE2328P1Z9",  # letterhead footer
        "excelengrs@gmail.com",
    ):
        assert needle in text, needle
    # Blank rows and the untouched second item print nothing extra.
    assert "Liquid Handled" not in text
    assert text.count("Technical Deviation") == 1
    # ... and it sits between its own item and the next one.
    assert (
        text.index("M CPK 125-80-200")
        < text.index("MCPK 125-80-200")
        < text.index("P JHL 123-07-678")
    )


def test_pdf_without_any_filled_deviation_has_no_panel(
    client: TestClient, customer: Customer
) -> None:
    q = client.post("/api/quotations", json=_technical(customer)).json()
    r = client.get(f"/api/quotations/{q['id']}/pdf")
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(r.content)).pages)
    assert "Technical Deviation" not in text and "Pump Model" not in text


def test_indian_rupees_grouping() -> None:
    from app.services.quotation_pdf import indian_rupees

    assert indian_rupees(21600000) == "2,16,000"
    assert indian_rupees(1476000) == "14,760"
    assert indian_rupees(99900) == "999"
    assert indian_rupees(12345678900) == "12,34,56,789"


def test_list_can_show_only_negotiated_numbers(client: TestClient, customer: Customer) -> None:
    a = client.post("/api/quotations", json=_body(customer)).json()
    client.post("/api/quotations", json=_body(customer))
    r1 = client.post(f"/api/quotations/{a['id']}/revise").json()
    only = client.get("/api/quotations", params={"negotiated": "true"}).json()
    assert [r["id"] for r in only["items"]] == [r1["id"]]
    assert client.get("/api/quotations", params={"negotiated": "false"}).json()["total"] == 1


def test_line_changes_give_old_and_new_rate_per_item(
    client: TestClient, customer: Customer
) -> None:
    q = client.post("/api/quotations", json=_body(customer)).json()
    assert client.get(f"/api/quotations/{q['id']}/line-changes").json() == []
    # Quantity changes and a new item: a revised quotation.
    n1 = client.post(f"/api/quotations/{q['id']}/revise", json={"kind": "revision"}).json()
    assert n1["number"].endswith("-R1")
    client.patch(
        f"/api/quotations/{n1['id']}",
        json={
            "lines": [
                {"description": "RNS 125/100 Coupling", "quantity": 3, "rate_paise": 1350000},
                {"description": "Gasket", "quantity": 1, "rate_paise": 5000},
            ]
        },
    )
    rows = client.get(f"/api/quotations/{n1['id']}/line-changes").json()
    assert rows[0] == {
        "description": "RNS 125/100 Coupling",
        "old_quantity": 1,
        "new_quantity": 3,
        "old_rate_paise": 1476000,
        "new_rate_paise": 1350000,
        "change": "kept",
    }
    assert rows[1]["change"] == "added" and rows[1]["old_rate_paise"] is None


def test_history_is_one_row_per_item_with_ten_stages(
    client: TestClient, customer: Customer, db: Session
) -> None:
    cp = make_product(db, sku="CPL", name="Coupling").id
    sb = make_product(db, sku="SPB", name="Spblock").id
    body = _body(
        customer,
        lines=[
            {"product_id": cp, "description": "Coupling", "quantity": 1, "rate_paise": 605000},
            {"product_id": sb, "description": "Spblock", "quantity": 1, "rate_paise": 2400000},
        ],
    )
    q = client.post("/api/quotations", json=body).json()
    # Quantities change: a revised quotation.
    n1 = client.post(f"/api/quotations/{q['id']}/revise", json={"kind": "revision"}).json()
    client.patch(
        f"/api/quotations/{n1['id']}",
        json={
            "lines": [
                {"product_id": cp, "description": "Coupling", "quantity": 3, "rate_paise": 60500},
                {"product_id": sb, "description": "Spblock", "quantity": 3, "rate_paise": 24000},
            ]
        },
    )
    client.post(f"/api/quotations/{n1['id']}/status", json={"status": "accepted"})
    other = client.post("/api/quotations", json=_body(customer, subject="Other")).json()

    rows = client.get("/api/quotations/history").json()
    mine = [r for r in rows if r["quotation_id"] == n1["id"]]
    assert [r["description"] for r in mine] == ["Coupling", "Spblock"]
    assert mine[0]["quoted_paise"] == 605000
    assert len(mine[0]["negotiations_paise"]) == 10
    assert mine[0]["negotiations_paise"][:2] == [60500, None]
    assert mine[0]["quantity"] == 3
    assert mine[0]["status"] == "accepted" and mine[0]["stage"] == 1
    assert any(r["quotation_id"] == other["id"] for r in rows)

    assert {
        r["quotation_id"]
        for r in client.get("/api/quotations/history", params={"status": "accepted"}).json()
    } == {n1["id"]}
    assert [
        r["description"]
        for r in client.get("/api/quotations/history", params={"q": "spblock"}).json()
    ] == ["Coupling", "Spblock"]


def test_history_exports_as_excel_and_pdf(client: TestClient, customer: Customer) -> None:
    import io

    from openpyxl import load_workbook

    q = client.post("/api/quotations", json=_body(customer)).json()
    n1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    client.patch(
        f"/api/quotations/{n1['id']}",
        json={
            "lines": [
                {
                    "product_id": _COUPLING["id"],
                    "description": "RNS 125/100 Coupling",
                    "quantity": 1,
                    "rate_paise": 1340000,
                }
            ]
        },
    )
    x = client.get("/api/quotations/history/export", params={"format": "xlsx"})
    assert x.status_code == 200
    assert "quote-history.xlsx" in x.headers["content-disposition"]
    ws = load_workbook(io.BytesIO(x.content)).active
    # The branding sits above the column headers.
    top = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "Company")
    header = [c.value for c in ws[top]]
    assert header[:5] == ["Company", "Quote no.", "Description", "Qty", "Quoted price"]
    row = [c.value for c in ws[top + 1]]
    assert row[0] == customer.name and row[1] == "ESQSP-26-1"
    assert row[4] == 14760 and row[5] == 13400  # numbers, so the sheet can sum them

    p = client.get("/api/quotations/history/export", params={"format": "pdf", "q": "coupling"})
    assert p.status_code == 200 and p.headers["content-type"] == "application/pdf"
    text = PdfReader(io.BytesIO(p.content)).pages[0].extract_text()
    assert "Quote History" in text and "14,760" in text and "13,400" in text


def test_history_filters_by_the_date_first_quoted(client: TestClient, customer: Customer) -> None:
    apr = client.post("/api/quotations", json=_body(customer, quote_date="2026-04-20")).json()
    aug = client.post("/api/quotations", json=_body(customer, quote_date="2026-08-05")).json()
    # A negotiation dated later does not move the quote out of its period.
    n1 = client.post(f"/api/quotations/{apr['id']}/revise").json()
    client.patch(f"/api/quotations/{n1['id']}", json={"quote_date": "2026-09-01"})

    def ids(**p: str) -> set[int]:
        return {r["quotation_id"] for r in client.get("/api/quotations/history", params=p).json()}

    assert ids(**{"from": "2026-04-01", "to": "2026-04-30"}) == {n1["id"]}
    assert ids(**{"from": "2026-07-01"}) == {aug["id"]}
    assert ids(to="2026-12-31") == {n1["id"], aug["id"]}
    x = client.get(
        "/api/quotations/history/export",
        params={"format": "xlsx", "from": "2026-04-01", "to": "2026-04-30"},
    )
    assert "quote-history-2026-04-01-to-2026-04-30.xlsx" in x.headers["content-disposition"]


def test_modern_format_pdf_shows_gst_total_and_old_rates_on_negotiation(
    client: TestClient, customer: Customer
) -> None:
    import pypdf

    q = client.post("/api/quotations", json=_body(customer)).json()
    n1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    line = {**_body(customer)["lines"][0], "rate_paise": 1400000}  # type: ignore[index]
    assert client.patch(f"/api/quotations/{n1['id']}", json={"lines": [line]}).status_code == 200
    r = client.get(f"/api/quotations/{n1['id']}/pdf")
    assert r.status_code == 200
    pages = pypdf.PdfReader(BytesIO(r.content)).pages
    text = " ".join(" ".join(p.extract_text().split()) for p in pages)
    assert "Quotation" in text and "Negotiation N1" in text
    assert "Old Rate" in text and "SGST @ 9%" in text and "CGST @ 9%" in text
    assert "Saved vs last offer Rs. 760.00" in text
    assert "Amount in words" in text
