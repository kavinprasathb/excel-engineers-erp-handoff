"""The settings singleton, and the bootstrap that guards how the app starts."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user
from app.main import app as fastapi_app
from app.models import AppSettings, User
from app.routers import auth as auth_router
from app.schemas.common import Page
from app.security import hash_password, verify_password
from app.seed import InsecureBootstrap, bootstrap, check_production_secrets


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="settings-admin@excelengineers.in",
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
    """Signed in by dependency override — the auth path has its own test file."""
    fastapi_app.dependency_overrides[get_db] = lambda: db
    fastapi_app.dependency_overrides[get_current_user] = lambda: admin
    auth_router.reset_rate_limits()
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
def anonymous_client(db: Session) -> Iterator[TestClient]:
    fastapi_app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()


# --------------------------------------------------------------------------- GET


def test_the_singleton_row_is_seeded_by_the_migration(db: Session) -> None:
    """No get-or-create anywhere in the app depends on this being true."""
    assert db.get(AppSettings, 1) is not None


CONTRACT_FIELDS = {
    "company_name",
    "low_stock_threshold",
    "default_gst_rate_bp",
    "company_address_line1",
    "company_address_line2",
    "company_city",
    "company_state",
    "company_pincode",
    "company_gstin",
    "company_phone",
    "company_mobile",
    "company_email",
    "signatory_name",
    "signatory_designation",
    "quotation_terms_defaults",
    "quotation_spec_defaults",
}


def test_get_settings_returns_the_contract_shape(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert set(response.json()) == CONTRACT_FIELDS


def test_the_letterhead_is_seeded_not_blank(client: TestClient) -> None:
    """Every printed document draws its head and foot from these. Blank here is blank on paper."""
    body = client.get("/api/settings").json()
    assert body["company_gstin"]
    assert body["company_email"]
    assert body["signatory_name"]


def test_patch_updates_the_letterhead(client: TestClient, db: Session) -> None:
    response = client.patch(
        "/api/settings",
        json={
            "company_gstin": "33AAIFE2328P1Z0",
            "signatory_name": "K. Prasath",
            "signatory_designation": "Partner",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["company_gstin"] == "33AAIFE2328P1Z0"
    assert body["signatory_designation"] == "Partner"

    row = db.get(AppSettings, 1)
    assert row is not None
    assert row.signatory_name == "K. Prasath"


def test_a_blank_letterhead_line_is_a_real_value(client: TestClient) -> None:
    """ "" means "do not print this line" — unlike the company name, it is allowed."""
    body = client.patch("/api/settings", json={"company_address_line2": ""}).json()
    assert body["company_address_line2"] == ""


@pytest.mark.parametrize(
    "payload",
    [
        {"company_gstin": "3" * 21},
        {"company_pincode": "1" * 11},
    ],
    ids=["gstin-too-long", "pincode-too-long"],
)
def test_patch_rejects_letterhead_values_the_columns_cannot_hold(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.patch("/api/settings", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_theme_is_not_a_server_setting(client: TestClient) -> None:
    """Per-viewer, in localStorage. Here it would make one person's taste everyone's."""
    assert "theme" not in client.get("/api/settings").json()


def test_settings_requires_a_session(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/api/settings")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


# --------------------------------------------------------------------------- PATCH


def test_patch_updates_only_the_fields_sent(client: TestClient, db: Session) -> None:
    before = client.get("/api/settings").json()

    response = client.patch("/api/settings", json={"low_stock_threshold": 12})
    assert response.status_code == 200
    body = response.json()
    assert body["low_stock_threshold"] == 12
    assert body["company_name"] == before["company_name"]
    assert body["default_gst_rate_bp"] == before["default_gst_rate_bp"]

    assert db.get(AppSettings, 1).low_stock_threshold == 12  # type: ignore[union-attr]


def test_patch_accepts_an_empty_body_as_a_no_op(client: TestClient) -> None:
    before = client.get("/api/settings").json()
    assert client.patch("/api/settings", json={}).json() == before


def test_patch_accepts_zero_as_a_real_value(client: TestClient) -> None:
    """0 is a legitimate threshold; only an omitted field means "leave it alone"."""
    assert (
        client.patch("/api/settings", json={"low_stock_threshold": 0}).json()["low_stock_threshold"]
        == 0
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"low_stock_threshold": -1},
        {"default_gst_rate_bp": -1},
        {"default_gst_rate_bp": 10001},
        {"company_name": ""},
        {"low_stock_threshold": "five"},
    ],
    ids=["negative-threshold", "negative-gst", "gst-over-100pc", "blank-name", "not-a-number"],
)
def test_patch_rejects_values_the_check_constraints_would_reject(
    client: TestClient, payload: dict[str, object]
) -> None:
    """A 422 with a usable message, not a 500 from the database. The CHECK still backs it."""
    response = client.patch("/api/settings", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_patch_rejects_unknown_fields(client: TestClient) -> None:
    """Mass assignment defence: the schema is the allowlist."""
    response = client.patch("/api/settings", json={"id": 2, "company_name": "Hijacked"})
    assert response.status_code == 422


def test_patch_requires_a_session(anonymous_client: TestClient) -> None:
    response = anonymous_client.patch("/api/settings", json={"low_stock_threshold": 3})
    assert response.status_code == 401


# --------------------------------------------------------------------------- Page


def test_page_derives_its_page_count(client: TestClient) -> None:
    """Every list endpoint builds its envelope here. Wrong once, wrong everywhere."""
    page: Page[int] = Page.build([1, 2, 3], total=137, page=1, page_size=25)
    assert page.model_dump() == {
        "items": [1, 2, 3],
        "total": 137,
        "page": 1,
        "page_size": 25,
        "pages": 6,
    }
    assert Page.build([], total=0, page=1, page_size=25).pages == 0


# --------------------------------------------------------------------------- bootstrap


def test_bootstrap_creates_the_admin_and_is_idempotent(db: Session) -> None:
    settings = Settings(
        admin_email="Boot@ExcelEngineers.in",
        admin_password="a-real-local-password",
        admin_full_name="Boot",
        environment="development", cors_origins="http://localhost:5173",
    )
    first = bootstrap(db, settings)
    assert UserRole(first.role) is UserRole.ADMIN
    assert verify_password("a-real-local-password", first.password_hash)

    # Case-insensitive, because the lookup uses the same func.lower() expression
    # the unique index is built on.
    lowered = Settings(**{**settings.model_dump(), "admin_email": "boot@excelengineers.in"})
    assert bootstrap(db, settings).id == first.id
    assert bootstrap(db, lowered).id == first.id


def test_bootstrap_does_not_reset_an_existing_password(db: Session) -> None:
    """A stale ADMIN_PASSWORD in the env must not roll the credential back on deploy."""
    settings = Settings(
        admin_email="stable@excelengineers.in",
        admin_password="the-original-password",
        environment="development", cors_origins="http://localhost:5173",
    )
    bootstrap(db, settings)
    rotated = Settings(**{**settings.model_dump(), "admin_password": "something-else-entirely"})
    user = bootstrap(db, rotated)
    assert verify_password("the-original-password", user.password_hash)


def test_bootstrap_refuses_a_placeholder_password_in_production(db: Session) -> None:
    production = Settings(
        environment="production", cors_origins="", admin_password="change-me-admin"
    )
    with pytest.raises(InsecureBootstrap, match="ADMIN_PASSWORD"):
        bootstrap(db, production)


def test_bootstrap_refuses_a_placeholder_jwt_secret_in_production() -> None:
    production = Settings(
        environment="production", cors_origins="",
        admin_password="a-real-production-password",
        jwt_secret="change-me-in-production",
    )
    with pytest.raises(InsecureBootstrap, match="JWT_SECRET"):
        check_production_secrets(production)


def test_placeholders_are_allowed_outside_production() -> None:
    """Locally the placeholders are the point; a forced secret is invented badly."""
    check_production_secrets(
        Settings(
            environment="development", cors_origins="http://localhost:5173",
            admin_password="change-me-admin",
            jwt_secret="change-me-in-production",
        )
    )


def test_quotation_terms_defaults_are_seeded_and_editable(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert set(body["quotation_terms_defaults"]) == {"pumps", "valves", "spares"}
    assert body["quotation_terms_defaults"]["spares"][0]["label"] == "Price Basis"

    patched = client.patch(
        "/api/settings",
        json={
            "quotation_terms_defaults": {
                "pumps": [{"label": "Only", "text": "one"}],
                "valves": [],
                "spares": [{"label": "A", "text": "b"}, {"label": "C", "text": "d"}],
            }
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["quotation_terms_defaults"]["valves"] == []
    assert [t["label"] for t in patched.json()["quotation_terms_defaults"]["spares"]] == ["A", "C"]
    assert (
        client.patch("/api/settings", json={"quotation_terms_defaults": {"boats": []}}).status_code
        == 422
    )
