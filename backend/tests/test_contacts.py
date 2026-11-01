"""Many emails/phones on customers and suppliers, and importing them from Excel or PDF."""

import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import Customer, Supplier, User
from app.security import hash_password
from app.services.contact_import import parse_pdf_text


@pytest.fixture
def staff(db: Session) -> User:
    user = User(
        email="contacts-staff@excelengineers.in",
        full_name="Staff",
        password_hash=hash_password("correct-horse-battery"),
        role=UserRole.STAFF,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def client(db: Session, staff: User) -> Iterator[TestClient]:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    fastapi_app.dependency_overrides[get_current_user] = lambda: staff
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()


KINDS = ["customers", "suppliers"]

# GST number, city, state and pin code are mandatory on a new record.
MANDATORY = {
    "customers": {
        "gstin": "33AAIFE2328P1Z9",
        "billing_city": "Salem",
        "billing_state": "Tamil Nadu",
        "billing_pincode": "636016",
    },
    "suppliers": {
        "gstin": "33AAIFE2328P1Z9",
        "city": "Salem",
        "state": "Tamil Nadu",
        "pincode": "636016",
    },
}


# --------------------------------------------------------------------------- lists


@pytest.mark.parametrize("kind", KINDS)
def test_create_with_lists_syncs_first_entry(client: TestClient, kind: str) -> None:
    r = client.post(
        f"/api/{kind}",
        json={
            **MANDATORY[kind],
            "name": "Multi Co",
            "emails": [" a@example.com ", "", "B@example.com", "a@EXAMPLE.com"],
            "phones": ["+91 98400 12345", "044-2345 6789", "  ", "+91 98400 12345"],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["emails"] == ["a@example.com", "B@example.com"]
    assert body["phones"] == ["+91 98400 12345", "044-2345 6789"]
    assert body["email"] == "a@example.com"
    assert body["phone"] == "+91 98400 12345"


@pytest.mark.parametrize("kind", KINDS)
def test_legacy_single_values_still_accepted(client: TestClient, kind: str) -> None:
    r = client.post(
        f"/api/{kind}",
        json={
            **MANDATORY[kind],
            "name": "Legacy Co",
            "email": "x@example.com",
            "phone": "9840012345",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["emails"] == ["x@example.com"]
    assert r.json()["phones"] == ["9840012345"]
    cid = r.json()["id"]

    r = client.patch(f"/api/{kind}/{cid}", json={"emails": ["x@example.com", "y@example.com"]})
    assert r.json()["emails"] == ["x@example.com", "y@example.com"]

    # A legacy PATCH of the single value replaces the first entry only.
    r = client.patch(f"/api/{kind}/{cid}", json={"email": "z@example.com"})
    assert r.json()["emails"] == ["z@example.com", "y@example.com"]
    assert r.json()["email"] == "z@example.com"

    r = client.patch(f"/api/{kind}/{cid}", json={"emails": []})
    assert r.json()["emails"] == [] and r.json()["email"] == ""


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize(
    "payload",
    [
        {"emails": ["not-an-email"]},
        {"phones": ["12ab"]},
        {"phones": ["123"]},
        {"phones": ["1" * 21]},
        {"emails": [f"u{i}@example.com" for i in range(11)]},
        {"phones": [f"98400{i:05d}" for i in range(11)]},
    ],
)
def test_invalid_contacts_are_422(client: TestClient, kind: str, payload: dict) -> None:
    r = client.post(f"/api/{kind}", json={"name": "Bad Co", **payload})
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("kind", KINDS)
def test_search_matches_any_email_or_phone(client: TestClient, kind: str) -> None:
    client.post(
        f"/api/{kind}",
        json={
            **MANDATORY[kind],
            "name": "Searchable Co",
            "emails": ["first@one.in", "second@hidden-domain.in"],
            "phones": ["9840011111", "04423456789"],
        },
    )
    for q in ("hidden-domain", "04423456789"):
        names = [row["name"] for row in client.get(f"/api/{kind}", params={"q": q}).json()["items"]]
        assert "Searchable Co" in names


def test_rows_created_without_lists_read_back_empty(db: Session) -> None:
    """Rows written by code that predates the lists get the server default."""
    customer = Customer(name="Old Style")
    supplier = Supplier(name="Old Style Supplier")
    db.add_all([customer, supplier])
    db.flush()
    db.refresh(customer)
    db.refresh(supplier)
    assert customer.emails == [] and supplier.phones == []


# --------------------------------------------------------------------------- import


def _xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Customer master export"])
    ws.append([])
    ws.append(["Company Name", "Contact Person", "Email(s)", "Mobile No", "GST No", "City", "Pin"])
    ws.append(
        [
            "Acme Pumps",
            "Ravi",
            "a@acme.in; b@acme.in",
            "9840012345 / 044-23456789",
            "33AAACA1234A1Z5",
            "Chennai",
            600001,
        ]
    )
    ws.append([None] * 7)
    ws.append(["Beta Valves", "", "bad-email", "", "", "Coimbatore", "64101"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800.0
    for line in lines:
        if line:
            c.drawString(50, y, line)
        y -= 28 if not line else 16
    c.save()
    return buf.getvalue()


def test_xlsx_preview_customers(client: TestClient, db: Session) -> None:
    db.add(Customer(name="Acme Pumps"))
    db.flush()
    r = client.post(
        "/api/customers/import/preview",
        files={"file": ("list.xlsx", _xlsx(), "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    records = r.json()["records"]
    assert len(records) == 2
    acme = records[0]
    assert acme["data"]["name"] == "Acme Pumps"
    assert acme["data"]["emails"] == ["a@acme.in", "b@acme.in"]
    assert acme["data"]["phones"] == ["9840012345", "044-23456789"]
    assert acme["data"]["gstin"] == "33AAACA1234A1Z5"
    assert acme["data"]["billing_city"] == "Chennai"
    assert acme["data"]["billing_pincode"] == "600001"
    assert acme["duplicate_of"]["name"] == "Acme Pumps"
    beta = records[1]
    assert any("email" in w for w in beta["warnings"])
    assert any("Pincode" in w for w in beta["warnings"])
    # Preview writes nothing.
    assert db.query(Customer).filter(Customer.name == "Beta Valves").count() == 0


def test_xlsx_preview_suppliers_uses_supplier_shape(client: TestClient) -> None:
    r = client.post(
        "/api/suppliers/import/preview",
        files={"file": ("list.xlsx", _xlsx(), "application/octet-stream")},
    )
    assert r.status_code == 200, r.text
    data = r.json()["records"][0]["data"]
    assert data["city"] == "Chennai" and data["pincode"] == "600001"
    assert "billing_city" not in data


def test_pdf_preview(client: TestClient) -> None:
    pdf = _pdf(
        [
            "Name: Gamma Engineering",
            "Contact Person: Mr. Kumar",
            "Address: 12 Industrial Estate, Guindy",
            "City: Chennai",
            "Email: sales@gamma.in, kumar@gamma.in",
            "Phone: +91 98401 23456 / 044 2234 5678",
            "GSTIN: 33ABCDE1234F1Z5",
            "Pincode: 600032",
            "",
            "Name: Delta Motors",
            "Mobile: 9876543210",
        ]
    )
    r = client.post(
        "/api/customers/import/preview", files={"file": ("list.pdf", pdf, "application/pdf")}
    )
    assert r.status_code == 200, r.text
    records = [rec["data"] for rec in r.json()["records"]]
    assert [rec["name"] for rec in records] == ["Gamma Engineering", "Delta Motors"]
    g = records[0]
    assert g["contact_person"] == "Mr. Kumar"
    assert g["emails"] == ["sales@gamma.in", "kumar@gamma.in"]
    assert "+91 98401 23456" in g["phones"]
    assert g["gstin"] == "33ABCDE1234F1Z5"
    assert g["billing_pincode"] == "600032"
    assert g["billing_city"] == "Chennai"
    assert records[1]["phones"] == ["9876543210"]


def test_pdf_text_splits_on_repeated_name_labels() -> None:
    records = parse_pdf_text("Name: A Co\nEmail: a@a.in\nName: B Co\nEmail: b@b.in")
    assert [r["name"] for r in records] == ["A Co", "B Co"]


@pytest.mark.parametrize("kind", KINDS)
def test_preview_rejects_other_files(client: TestClient, kind: str) -> None:
    r = client.post(
        f"/api/{kind}/import/preview", files={"file": ("list.csv", b"name\nA", "text/csv")}
    )
    assert r.status_code == 422
    r = client.post(
        f"/api/{kind}/import/preview", files={"file": ("x.xlsx", b"not a zip", "text/plain")}
    )
    assert r.status_code == 422


@pytest.mark.parametrize("kind", KINDS)
def test_commit_creates_all_or_nothing(client: TestClient, kind: str) -> None:
    r = client.post(
        f"/api/{kind}/import/commit",
        json={
            "records": [
                {"name": "Imp One", "emails": ["one@imp.in"], "phones": ["9840000001"]},
                {"name": "Imp Two"},
            ]
        },
    )
    assert r.status_code == 201, r.text
    assert r.json() == {"created": 2}
    names = [
        row["name"] for row in client.get(f"/api/{kind}", params={"q": "Imp "}).json()["items"]
    ]
    assert {"Imp One", "Imp Two"} <= set(names)

    r = client.post(
        f"/api/{kind}/import/commit",
        json={"records": [{"name": "Imp Three"}, {"name": "imp one"}]},
    )
    assert r.status_code == 422
    names = [
        row["name"] for row in client.get(f"/api/{kind}", params={"q": "Imp "}).json()["items"]
    ]
    assert "Imp Three" not in names
