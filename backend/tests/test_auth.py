"""Auth endpoints, the cookie's flags, and the role guard that nothing uses yet.

These assert the controls named in docs/security.md. A control nobody tests is
a control that quietly stops working, which is exactly how v2's session ended
up readable from JavaScript.
"""

from collections.abc import Iterator

# starlette's TestClient prefers httpx2 and only falls back to httpx, so the
# response type must come from the same package the client actually uses.
import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.constants import UserRole
from app.db import get_db
from app.deps import require_role
from app.main import app as fastapi_app
from app.models import User
from app.routers import auth as auth_router
from app.security import (
    Forbidden,
    TokenError,
    create_session_token,
    decode_session_token,
    hash_password,
    verify_password,
)

PASSWORD = "correct-horse-battery"


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """A client bound to the test transaction.

    Built without entering the context manager on purpose: that would run the
    lifespan, and bootstrap() would commit an admin outside this rollback.
    """
    fastapi_app.dependency_overrides[get_db] = lambda: db
    auth_router.reset_rate_limits()
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.clear()
        auth_router.reset_rate_limits()


@pytest.fixture
def admin(db: Session) -> User:
    user = User(
        email="Admin@ExcelEngineers.in",
        full_name="Admin",
        password_hash=hash_password(PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _login(
    client: TestClient,
    email: str = "admin@excelengineers.in",
    password: str = PASSWORD,
) -> httpx.Response:
    return client.post("/api/auth/login", json={"email": email, "password": password})


# --------------------------------------------------------------------------- hashing


def test_password_hash_is_argon2id_and_verifies() -> None:
    digest = hash_password(PASSWORD)
    assert digest.startswith("$argon2id$"), "docs/security.md requires argon2id, not bcrypt"
    assert verify_password(PASSWORD, digest)
    assert not verify_password(PASSWORD + "x", digest)


def test_long_passwords_are_not_truncated() -> None:
    """The specific bcrypt failure this project rejected: 72-byte truncation."""
    base = "a" * 80
    digest = hash_password(base + "TAIL")
    assert not verify_password(base + "DIFF", digest)


def test_session_token_round_trips_with_a_fresh_jti() -> None:
    first = decode_session_token(create_session_token(user_id=7, role="admin"))
    second = decode_session_token(create_session_token(user_id=7, role="admin"))
    assert first["sub"] == "7"
    assert first["role"] == "admin"
    assert "exp" in first
    assert first["jti"] != second["jti"]


def test_a_tampered_token_is_rejected() -> None:
    token = create_session_token(user_id=1, role="admin")
    forged = token[:-2] + ("bb" if token.endswith("aa") else "aa")
    with pytest.raises(TokenError):
        decode_session_token(forged)


# --------------------------------------------------------------------------- login


def test_login_succeeds_and_is_case_insensitive_on_email(
    client: TestClient, admin: User, db: Session
) -> None:
    response = _login(client, email="ADMIN@excelengineers.in")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "user": {
            "id": admin.id,
            "email": "Admin@ExcelEngineers.in",
            "full_name": "Admin",
            "role": "admin",
        }
    }
    db.refresh(admin)
    assert admin.last_login_at is not None


def test_login_sets_the_cookie_flags_the_security_doc_requires(
    client: TestClient, admin: User
) -> None:
    header = _login(client).headers["set-cookie"].lower()
    assert "session=" in header
    assert "httponly" in header, "an XSS-readable session is what v2 shipped"
    assert "samesite=lax" in header
    assert "path=/" in header
    # Dev has CORS origins configured, so is_production is False and Secure
    # would make the cookie unusable over plain http on localhost.
    assert "secure" not in header


def test_login_cookie_is_secure_in_production(
    client: TestClient, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    production = Settings(
        environment="production",
        cors_origins="",
        jwt_secret="test-secret-for-the-production-branch",
    )
    monkeypatch.setattr(auth_router, "get_settings", lambda: production)
    assert "secure" in _login(client).headers["set-cookie"].lower()


def test_login_with_a_wrong_password_is_401_invalid_credentials(
    client: TestClient, admin: User
) -> None:
    response = _login(client, password="not-the-password")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert "set-cookie" not in response.headers


def test_login_for_an_unknown_email_says_exactly_the_same_thing(client: TestClient) -> None:
    """Same code, same message: the response must not enumerate our users."""
    response = _login(client, email="nobody@example.com")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_is_refused_for_a_deactivated_user(
    client: TestClient, admin: User, db: Session
) -> None:
    admin.is_active = False
    db.flush()
    assert _login(client).status_code == 401


def test_login_body_must_be_a_valid_email(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"]["fields"][0]["field"] == "email"


def test_login_is_rate_limited_per_ip(client: TestClient, admin: User) -> None:
    # Different addresses, so it is the per-IP window being spent, not the per-email one.
    for i in range(auth_router.LOGIN_MAX_ATTEMPTS):
        assert _login(client, email=f"nobody{i}@example.com").status_code == 401
    blocked = _login(client)  # the correct password, but the window is spent
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"


def test_rate_limit_counts_per_ip_not_globally(client: TestClient, admin: User) -> None:
    for i in range(auth_router.LOGIN_MAX_ATTEMPTS):
        client.post(
            "/api/auth/login",
            json={"email": f"nobody{i}@example.com", "password": "wrong"},
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
    other = client.post(
        "/api/auth/login",
        json={"email": "admin@excelengineers.in", "password": PASSWORD},
        headers={"X-Forwarded-For": "10.0.0.2"},
    )
    assert other.status_code == 200


def test_a_spoofed_forwarded_for_does_not_reset_the_limit(client: TestClient, admin: User) -> None:
    """nginx appends the real peer; the client controls everything before it."""
    for i in range(auth_router.LOGIN_MAX_ATTEMPTS):
        client.post(
            "/api/auth/login",
            json={"email": f"nobody{i}@example.com", "password": "wrong"},
            headers={"X-Forwarded-For": f"1.2.3.{i}, 10.0.0.9"},
        )
    blocked = client.post(
        "/api/auth/login",
        json={"email": "admin@excelengineers.in", "password": PASSWORD},
        headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.9"},
    )
    assert blocked.status_code == 429


def test_x_real_ip_is_preferred_over_forwarded_for(client: TestClient, admin: User) -> None:
    for i in range(auth_router.LOGIN_MAX_ATTEMPTS):
        client.post(
            "/api/auth/login",
            json={"email": f"nobody{i}@example.com", "password": "wrong"},
            headers={"X-Real-IP": "10.0.0.7", "X-Forwarded-For": f"10.1.1.{i}"},
        )
    blocked = client.post(
        "/api/auth/login",
        json={"email": "admin@excelengineers.in", "password": PASSWORD},
        headers={"X-Real-IP": "10.0.0.7"},
    )
    assert blocked.status_code == 429


def test_failures_are_limited_per_email_across_ips(client: TestClient, admin: User) -> None:
    for i in range(auth_router.EMAIL_MAX_FAILURES):
        r = client.post(
            "/api/auth/login",
            json={"email": "ADMIN@excelengineers.in", "password": "wrong"},
            headers={"X-Real-IP": f"10.2.0.{i}"},
        )
        assert r.status_code == 401
    blocked = client.post(
        "/api/auth/login",
        json={"email": "admin@excelengineers.in", "password": PASSWORD},
        headers={"X-Real-IP": "10.2.9.9"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"


def test_rate_limit_buckets_stay_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_router, "MAX_BUCKETS", 3)
    auth_router.reset_rate_limits()
    try:
        for i in range(10):
            auth_router._record_failure(f"user{i}@example.com")
        assert len(auth_router._email_failures) <= 3
    finally:
        auth_router.reset_rate_limits()


# --------------------------------------------------------------------------- me / logout


def test_me_returns_the_signed_in_user(client: TestClient, admin: User) -> None:
    _login(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "Admin@ExcelEngineers.in"


def test_me_without_a_cookie_is_401_not_authenticated(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_with_a_forged_cookie_is_401(client: TestClient, admin: User) -> None:
    client.cookies.set("session", "not.a.jwt")
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_is_401_once_the_account_is_deactivated(
    client: TestClient, admin: User, db: Session
) -> None:
    """The cookie is still valid; the account is not. The database is the authority."""
    _login(client)
    admin.is_active = False
    db.flush()
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_the_cookie_and_works_without_one(client: TestClient) -> None:
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert "session=" in response.headers["set-cookie"]
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_logout_revokes_the_session_server_side(client: TestClient, admin: User) -> None:
    """A copy of the cookie kept from before logout must stop working."""
    _login(client)
    copied = TestClient(client.app, base_url=str(client.base_url))
    copied.cookies.set("session", client.cookies["session"])
    assert copied.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert copied.get("/api/auth/me").status_code == 401


# --------------------------------------------------------------------------- change password


def test_change_password_rotates_the_hash_and_the_session(
    client: TestClient, admin: User, db: Session
) -> None:
    before = _login(client).cookies["session"]
    old_hash = admin.password_hash

    response = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a-brand-new-passphrase"},
    )
    assert response.status_code == 204
    after = response.cookies["session"]
    assert after != before, "changing a password must invalidate the old session"
    assert decode_session_token(after)["jti"] != decode_session_token(before)["jti"]

    db.refresh(admin)
    assert admin.password_hash != old_hash
    assert verify_password("a-brand-new-passphrase", admin.password_hash)
    assert not verify_password(PASSWORD, admin.password_hash)


def test_change_password_rejects_a_wrong_current_password(client: TestClient, admin: User) -> None:
    _login(client)
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": "nope", "new_password": "a-brand-new-passphrase"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_change_password_enforces_the_twelve_character_minimum(
    client: TestClient, admin: User
) -> None:
    _login(client)
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "elevenchar"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_change_password_requires_a_session(client: TestClient, admin: User) -> None:
    response = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a-brand-new-passphrase"},
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------- require_role


def test_require_role_admits_a_matching_role_and_denies_a_mismatch(admin: User) -> None:
    """Unused in slice 1, tested anyway — the point is that it already works.

    The guard is exercised as a plain function rather than through a route,
    because mounting it on a route is exactly what slice 1 does not do.
    """
    assert require_role(UserRole.ADMIN)(admin) is admin
    assert require_role(UserRole.ADMIN, UserRole.STAFF)(admin) is admin

    with pytest.raises(Forbidden) as caught:
        require_role(UserRole.STAFF)(admin)
    assert caught.value.status == 403
    assert caught.value.code == "forbidden"


# --------------------------------------------------------------------------- headers / CSRF


def test_responses_carry_the_security_headers(client: TestClient) -> None:
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "same-origin"
    # Dev is not production, and HSTS on localhost pins a developer's browser.
    assert "strict-transport-security" not in headers


def test_a_mutating_request_from_a_foreign_origin_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@excelengineers.in", "password": PASSWORD},
        headers={"Origin": "https://evil.example.com"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_a_mutating_request_naming_no_origin_is_rejected(
    client: TestClient, admin: User
) -> None:
    """A browser's fetch always sends Origin; a request with neither header is refused."""
    del client.headers["origin"]
    response = _login(client)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_referer_stands_in_for_a_missing_origin(client: TestClient, admin: User) -> None:
    del client.headers["origin"]
    same = {"Referer": "http://testserver/login"}
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "admin@excelengineers.in", "password": PASSWORD},
            headers=same,
        ).status_code
        == 200
    )
    foreign = client.post(
        "/api/auth/logout", headers={"Referer": "https://evil.example.com/page"}
    )
    assert foreign.status_code == 403


def test_reads_need_no_origin(client: TestClient) -> None:
    del client.headers["origin"]
    assert client.get("/api/health").status_code == 200


def test_a_mutating_request_from_the_dev_spa_origin_is_allowed(
    client: TestClient, admin: User
) -> None:
    """The Vite dev origin must behave exactly as production's same origin does."""
    dev_origins = get_settings().cors_origin_list
    if not dev_origins:
        pytest.skip("no dev CORS origin configured; this environment is production-shaped")
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@excelengineers.in", "password": PASSWORD},
        headers={"Origin": dev_origins[0]},
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------
# Session revocation on password change
# --------------------------------------------------------------------------


def test_changing_the_password_kills_sessions_issued_earlier(
    client: TestClient, admin: User, db: Session
) -> None:
    """Rotating the cookie is not enough on its own.

    The old JWT stays cryptographically valid until it expires, so without a
    server-side stamp a stolen session would survive the very action taken to
    end it. Two clients here: one changes the password, the other must die.
    """
    stolen = TestClient(client.app, base_url=str(client.base_url))
    stolen.post(
        "/api/auth/login",
        json={"email": admin.email, "password": PASSWORD},
    )
    assert stolen.get("/api/auth/me").status_code == 200

    client.post(
        "/api/auth/login",
        json={"email": admin.email, "password": PASSWORD},
    )
    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a-much-longer-password"},
    )
    assert changed.status_code == 204

    # The session that did the changing keeps working…
    assert client.get("/api/auth/me").status_code == 200
    # …and every other session is now refused.
    assert stolen.get("/api/auth/me").status_code == 401


def test_enum_columns_come_back_as_real_enum_members(db: Session, admin: User) -> None:
    """A VARCHAR column annotated Mapped[SomeStrEnum] otherwise hands back a
    plain str, and `ImportJobStatus.is_terminal` would raise AttributeError on
    a loaded row — at runtime, in the import poller, past every type check.
    """
    from app.constants import ImportJobStatus, UserRole
    from app.models import ImportJob

    db.expire_all()
    reloaded = db.get(User, admin.id)
    assert reloaded is not None
    assert isinstance(reloaded.role, UserRole)

    job = ImportJob(filename="x.xlsx")
    db.add(job)
    db.flush()
    db.expire(job)
    assert isinstance(job.status, ImportJobStatus)
    assert job.status.is_terminal is False
