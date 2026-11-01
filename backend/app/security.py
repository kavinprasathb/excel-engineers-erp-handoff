"""Password hashing and session tokens.

Two deliberate choices, both of which v2 got wrong:

* **argon2id, not bcrypt.** bcrypt silently truncates at 72 bytes, so a
  passphrase and its first 72 bytes are the same password — a property nobody
  wants to discover from an incident report. argon2-cffi's defaults are
  memory-hard and are left alone on purpose; tuning them by feel is how you end
  up with a work factor of 1.
* **The token is a cookie payload, not an API key.** It carries the minimum
  needed to load the user and nothing worth stealing on its own: the role is
  present only so a future `require_role` can reject early, and it is still
  re-read from the database on every request.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerifyMismatchError

from .config import get_settings
from .errors import AppError


class NotAuthenticated(AppError):
    """No usable session cookie. The client should show the login screen."""

    code = "not_authenticated"
    status = 401


class InvalidCredentials(AppError):
    """The email or the password was wrong — deliberately not saying which."""

    code = "invalid_credentials"
    status = 401


class RateLimited(AppError):
    code = "rate_limited"
    status = 429


class Forbidden(AppError):
    """Authenticated, but the role does not permit this. Unused in slice 1."""

    code = "forbidden"
    status = 403


# Minimum password length. Length beats composition rules; see docs/security.md.
MIN_PASSWORD_LENGTH = 12

_hasher = PasswordHasher()

# A real argon2 hash of a value nobody can log in with. Verifying against this
# when an email does not exist costs the same as a genuine check, so response
# timing does not tell an attacker which addresses are registered.
_DUMMY_HASH = _hasher.hash("not-a-real-password-timing-decoy")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """False rather than raising: a bad password is an expected outcome, not an error."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, Argon2Error):
        return False


def dummy_verify() -> None:
    """Burn the same CPU a real verification would, for a user that does not exist."""
    verify_password("not-a-real-password-timing-decoy-attempt", _DUMMY_HASH)


class TokenError(Exception):
    """The cookie was absent, malformed, tampered with or expired."""


def create_session_token(*, user_id: int, role: str, session_epoch: int = 0) -> str:
    """Mint a session JWT. A fresh `jti` each time, so rotation is observable.

    `epoch` is what makes revocation possible: the user row holds the epoch
    a session must have been minted under, so bumping it invalidates every
    outstanding token at once.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.session_hours)).timestamp()),
        "jti": uuid.uuid4().hex,
        "epoch": session_epoch,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_session_token(token: str) -> dict[str, Any]:
    """Decode and validate. Raises TokenError for every failure mode alike.

    Callers must not distinguish "expired" from "forged" in the response: both
    mean "log in again", and telling them apart only helps someone probing.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    return payload


__all__ = [
    "MIN_PASSWORD_LENGTH",
    "Forbidden",
    "InvalidCredentials",
    "NotAuthenticated",
    "RateLimited",
    "TokenError",
    "create_session_token",
    "decode_session_token",
    "dummy_verify",
    "hash_password",
    "verify_password",
]
