"""Customer/supplier codes, mandatory fields, branches, and the documents that name them."""

from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import Customer, Supplier, User
from tests.factories import make_product


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="branches-admin@excelengineers.in",
        full_name="Admin",
        password_hash="x",
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


CUSTOMER = {
    "name": "Chemplast Sanmar Limited",
    "gstin": "33AAACC1234A1Z5",
    "billing_address_line1": "Head Office, Guindy",
    "billing_city": "Chennai",
    "billing_state": "Tamil Nadu",
    "billing_pincode": "600032",
}
SUPPLIER = {
    "name": "KSB Limited",
    "gstin": "27AAACK1234A1Z5",
    "address_line1": "Pimpri",
    "city": "Pune",
    "state": "Maharashtra",
    "pincode": "411018",
}
BRANCH = {
    "name": "Mettur Plant",
    "gstin": "33AAACC1234A2Z4",
    "address_line1": "Chloro Chemical Division",
    "city": "Mettur Dam",
    "state": "Tamil Nadu",
    "pincode": "636403",
}


def _pdf_text(content: bytes) -> str:
    return " ".join(" ".join(p.extract_text().split()) for p in PdfReader(BytesIO(content)).pages)


# --- codes ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "body", "prefix"),
    [
        ("customers", CUSTOMER, "CUST-"),
        ("suppliers", SUPPLIER, "SUP-"),
    ],
)
def test_codes_are_sequential_read_only_and_never_reused(
    client: TestClient, kind: str, body: dict[str, str], prefix: str
) -> None:
    a = client.post(f"/api/{kind}", json=body).json()
    b = client.post(f"/api/{kind}", json={**body, "name": "Second Co"}).json()
    na, nb = int(a["code"].removeprefix(prefix)), int(b["code"].removeprefix(prefix))
    assert a["code"] == f"{prefix}{na:04d}" and nb == na + 1
    # Read-only: the API refuses a code rather than storing it.
    assert client.post(f"/api/{kind}", json={**body, "name": "X", "code": "Z"}).status_code == 422
    assert client.patch(f"/api/{kind}/{a['id']}", json={"code": "Z"}).status_code == 422
    # Deleted, the number is not issued again.
    assert client.delete(f"/api/{kind}/{b['id']}").status_code == 204
    c = client.post(f"/api/{kind}", json={**body, "name": "Third Co"}).json()
    assert int(c["code"].removeprefix(prefix)) == nb + 1


def test_records_added_outside_the_form_get_a_code_too(db: Session) -> None:
    c = Customer(name="Imported Co")
    s = Supplier(name="Imported Supplier")
    db.add_all([c, s])
    db.flush()
    assert c.code.startswith("CUST-") and s.code.startswith("SUP-")


# --- mandatory fields and formats ---------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "body", "field"),
    [
        ("customers", CUSTOMER, "gstin"),
        ("customers", CUSTOMER, "billing_city"),
        ("customers", CUSTOMER, "billing_state"),
        ("customers", CUSTOMER, "billing_pincode"),
        ("suppliers", SUPPLIER, "gstin"),
        ("suppliers", SUPPLIER, "city"),
        ("suppliers", SUPPLIER, "state"),
        ("suppliers", SUPPLIER, "pincode"),
    ],
)
def test_new_records_need_every_mandatory_field(
    client: TestClient, kind: str, body: dict[str, str], field: str
) -> None:
    r = client.post(f"/api/{kind}", json={k: v for k, v in body.items() if k != field})
    assert r.status_code == 422, r.text
    r = client.post(f"/api/{kind}", json={**body, field: "  "})
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("kind", ["customers", "suppliers"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gstin", "33AAACC1234"),
        ("gstin", "ABCDEFGHIJKLMNO"),
        ("pincode", "63601"),
        ("pincode", "63601a"),
    ],
)
def test_gst_and_pin_code_formats(client: TestClient, kind: str, field: str, value: str) -> None:
    body = CUSTOMER if kind == "customers" else SUPPLIER
    key = "billing_pincode" if kind == "customers" and field == "pincode" else field
    r = client.post(f"/api/{kind}", json={**body, key: value})
    assert r.status_code == 422, r.text


def test_mobile_and_email_are_optional_everywhere(client: TestClient) -> None:
    s = client.post("/api/suppliers", json={**SUPPLIER, "emails": [], "phones": [""]})
    assert s.status_code == 201, s.text
    b = client.post(f"/api/suppliers/{s.json()['id']}/branches", json={**BRANCH, "phones": [""]})
    assert b.status_code == 201, b.text


def test_legacy_record_keeps_working_and_is_flagged(client: TestClient, db: Session) -> None:
    """Saved before the fields were mandatory (and with a malformed GST number)."""
    old = Customer(name="Old Customer", gstin="33-OLD-GST", billing_city="Salem")
    db.add(old)
    db.flush()
    got = client.get(f"/api/customers/{old.id}").json()
    assert got["missing_fields"] == ["State", "Pin Code"]
    listed = client.get("/api/customers", params={"q": "Old Customer"}).json()["items"]
    assert listed[0]["missing_fields"] == ["State", "Pin Code"]

    # Unrelated edits still save: blanks that were blank stay allowed, and the
    # stored GST number is not re-judged while it is not changed.
    r = client.patch(
        f"/api/customers/{old.id}",
        json={"phones": ["9840012345"], "gstin": "33-OLD-GST", "billing_state": ""},
    )
    assert r.status_code == 200, r.text
    assert r.json()["missing_fields"] == ["State", "Pin Code"]
    # ... but a value that is there may not be blanked, and a new one must be valid.
    assert client.patch(f"/api/customers/{old.id}", json={"billing_city": ""}).status_code == 422
    assert client.patch(f"/api/customers/{old.id}", json={"gstin": "nope"}).status_code == 422
    r = client.patch(
        f"/api/customers/{old.id}",
        json={
            "gstin": "33AAACC1234A1Z5",
            "billing_state": "Tamil Nadu",
            "billing_pincode": "636016",
        },
    )
    assert r.status_code == 200 and r.json()["missing_fields"] == []


# --- branches -----------------------------------------------------------------------


@pytest.mark.parametrize(("kind", "body"), [("customers", CUSTOMER), ("suppliers", SUPPLIER)])
def test_branch_codes_follow_the_parent_and_are_never_reused(
    client: TestClient, kind: str, body: dict[str, str]
) -> None:
    parent = client.post(f"/api/{kind}", json=body).json()
    pid = parent["id"]
    one = client.post(f"/api/{kind}/{pid}/branches", json=BRANCH)
    assert one.status_code == 201, one.text
    two = client.post(f"/api/{kind}/{pid}/branches", json={**BRANCH, "name": "Karaikal"}).json()
    codes = [b["code"] for b in two["branches"]]
    assert codes == [f"{parent['code']}-BR01", f"{parent['code']}-BR02"]

    first = two["branches"][0]
    assert client.delete(f"/api/{kind}/{pid}/branches/{first['id']}").status_code == 204
    three = client.post(f"/api/{kind}/{pid}/branches", json={**BRANCH, "name": "Cuddalore"}).json()
    assert [b["code"] for b in three["branches"] if b["is_active"]] == [
        f"{parent['code']}-BR02",
        f"{parent['code']}-BR03",
    ]


@pytest.mark.parametrize(("kind", "body"), [("customers", CUSTOMER), ("suppliers", SUPPLIER)])
def test_branch_needs_name_gst_city_state_pin(
    client: TestClient, kind: str, body: dict[str, str]
) -> None:
    pid = client.post(f"/api/{kind}", json=body).json()["id"]
    for field in ("name", "gstin", "city", "state", "pincode"):
        r = client.post(
            f"/api/{kind}/{pid}/branches", json={k: v for k, v in BRANCH.items() if k != field}
        )
        assert r.status_code == 422, field
    assert (
        client.post(f"/api/{kind}/{pid}/branches", json={**BRANCH, "pincode": "12345"}).status_code
        == 422
    )
    b = client.post(f"/api/{kind}/{pid}/branches", json=BRANCH).json()["branches"][0]
    r = client.patch(f"/api/{kind}/{pid}/branches/{b['id']}", json={"city": "Salem"})
    assert r.status_code == 200 and r.json()["branches"][0]["city"] == "Salem"
    assert (
        client.patch(f"/api/{kind}/{pid}/branches/{b['id']}", json={"gstin": ""}).status_code == 422
    )


def test_supplier_branches_have_no_contact_person(client: TestClient) -> None:
    pid = client.post("/api/suppliers", json=SUPPLIER).json()["id"]
    r = client.post(f"/api/suppliers/{pid}/branches", json={**BRANCH, "contact_person": "X"})
    assert r.status_code == 422


# --- quotation ----------------------------------------------------------------------


def _quote(client: TestClient, customer_id: int, branch_id: int | None, db: Session) -> dict:
    p = make_product(db, name="Coupling")
    r = client.post(
        "/api/quotations",
        json={
            "type": "spares",
            "customer_id": customer_id,
            "customer_branch_id": branch_id,
            "quote_date": "2026-10-01",
            "lines": [{"product_id": p.id, "description": "Coupling", "rate_paise": 100000}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_quotation_prints_the_branch_gst_and_address(client: TestClient, db: Session) -> None:
    c = client.post("/api/customers", json=CUSTOMER).json()
    c = client.post(f"/api/customers/{c['id']}/branches", json=BRANCH).json()
    branch = c["branches"][0]

    q = _quote(client, c["id"], branch["id"], db)
    assert q["customer_branch"] == {
        "id": branch["id"],
        "code": branch["code"],
        "name": "Mettur Plant",
    }
    text = _pdf_text(client.get(f"/api/quotations/{q['id']}/pdf").content)
    assert "Mettur Plant" in text and BRANCH["gstin"] in text and "Mettur Dam" in text
    assert CUSTOMER["gstin"] not in text and "Guindy" not in text

    # Back to the head office: its GST number and address print instead.
    r = client.patch(f"/api/quotations/{q['id']}", json={"customer_branch_id": None})
    assert r.status_code == 200 and r.json()["customer_branch"] is None
    text = _pdf_text(client.get(f"/api/quotations/{q['id']}/pdf").content)
    assert CUSTOMER["gstin"] in text and "Guindy" in text and BRANCH["gstin"] not in text


def test_quotation_branch_must_belong_to_its_customer(client: TestClient, db: Session) -> None:
    a = client.post("/api/customers", json=CUSTOMER).json()
    b = client.post("/api/customers", json={**CUSTOMER, "name": "Other Co"}).json()
    b = client.post(f"/api/customers/{b['id']}/branches", json=BRANCH).json()
    other_branch = b["branches"][0]["id"]
    p = make_product(db, name="Coupling")
    r = client.post(
        "/api/quotations",
        json={
            "type": "spares",
            "customer_id": a["id"],
            "customer_branch_id": other_branch,
            "quote_date": "2026-10-01",
            "lines": [{"product_id": p.id, "description": "Coupling", "rate_paise": 100000}],
        },
    )
    assert r.status_code == 422

    # Switching customer drops the old customer's branch.
    q = _quote(client, b["id"], other_branch, db)
    r = client.patch(f"/api/quotations/{q['id']}", json={"customer_id": a["id"]})
    assert r.status_code == 200 and r.json()["customer_branch"] is None


def test_negotiation_keeps_the_branch(client: TestClient, db: Session) -> None:
    c = client.post("/api/customers", json=CUSTOMER).json()
    c = client.post(f"/api/customers/{c['id']}/branches", json=BRANCH).json()
    q = _quote(client, c["id"], c["branches"][0]["id"], db)
    n1 = client.post(f"/api/quotations/{q['id']}/revise").json()
    assert n1["customer_branch"]["id"] == c["branches"][0]["id"]


# --- purchase order -----------------------------------------------------------------


def test_purchase_order_prints_the_supplier_branch(client: TestClient, db: Session) -> None:
    customer = client.post("/api/customers", json=CUSTOMER).json()
    s = client.post("/api/suppliers", json=SUPPLIER).json()
    s = client.post(f"/api/suppliers/{s['id']}/branches", json=BRANCH).json()
    branch = s["branches"][0]
    p = make_product(db, name="Impeller")
    q = _quote(client, customer["id"], None, db)
    # Re-point the quote at a short product so the order drafts a purchase order.
    line = {"product_id": p.id, "description": "Impeller", "quantity": 2, "rate_paise": 100000}
    client.patch(f"/api/quotations/{q['id']}", json={"lines": [line]})
    client.post(f"/api/quotations/{q['id']}/status", json={"status": "accepted"})
    order = client.get(f"/api/quotations/{q['id']}/order").json()
    po = client.get(f"/api/orders/{order['id']}/purchase-orders").json()[0]

    wrong = client.post(
        f"/api/purchase-orders/{po['id']}/supplier",
        json={"supplier_id": s["id"], "branch_id": 999999},
    )
    assert wrong.status_code == 422
    r = client.post(
        f"/api/purchase-orders/{po['id']}/supplier",
        json={"supplier_id": s["id"], "branch_id": branch["id"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["supplier_branch"]["code"] == branch["code"]
    text = _pdf_text(client.get(f"/api/purchase-orders/{po['id']}/pdf").content)
    assert BRANCH["gstin"] in text and "Mettur Dam" in text and SUPPLIER["gstin"] not in text

    # No branch: the head office again.
    r = client.post(f"/api/purchase-orders/{po['id']}/supplier", json={"supplier_id": s["id"]})
    assert r.json()["supplier_branch"] is None
    text = _pdf_text(client.get(f"/api/purchase-orders/{po['id']}/pdf").content)
    assert SUPPLIER["gstin"] in text and BRANCH["gstin"] not in text
