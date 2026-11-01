"""First-run bootstrap: make sure someone can log in.

Idempotent, because it runs on every startup. It does **not** reset an existing
admin's password — an operator who leaves a stale `ADMIN_PASSWORD` in the env
would otherwise silently roll the credential back to a known value on each
deploy.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .constants import UserRole
from .models import User
from .security import MIN_PASSWORD_LENGTH, hash_password

log = logging.getLogger(__name__)

# Values shipped in .env.example and in this repo's defaults. Convenient
# locally; a live incident if one ever reaches the VPS.
PLACEHOLDER_PASSWORDS = frozenset(
    {
        "change-me-admin",
        "change-me-in-production",
        "changeme",
        "admin",
        "password",
    }
)
PLACEHOLDER_SECRETS = frozenset({"change-me-in-production", "changeme", "secret"})
MIN_JWT_SECRET_LENGTH = 32


class InsecureBootstrap(RuntimeError):
    """Refusing to start beats starting with a password the whole internet knows."""


def check_production_secrets(settings: Settings) -> None:
    """Fail loudly, at startup, rather than quietly serving a guessable admin.

    Only enforced in production: locally the placeholders are the point, and a
    developer who has to invent a secret before the app boots invents a bad one.
    """
    if not settings.is_production:
        return
    problems = []
    if settings.admin_password in PLACEHOLDER_PASSWORDS:
        problems.append("ADMIN_PASSWORD is still a placeholder")
    if settings.jwt_secret in PLACEHOLDER_SECRETS:
        problems.append("JWT_SECRET is still a placeholder")
    if len(settings.admin_password) < MIN_PASSWORD_LENGTH:
        problems.append(f"ADMIN_PASSWORD is shorter than {MIN_PASSWORD_LENGTH} characters")
    if len(settings.jwt_secret) < MIN_JWT_SECRET_LENGTH:
        # Logged, not fatal: the live secret cannot be inspected from here, and
        # refusing to boot over it would take the whole business offline.
        log.error(
            "JWT_SECRET is shorter than %s characters; generate one with "
            "`openssl rand -hex 32` and restart.",
            MIN_JWT_SECRET_LENGTH,
        )
    if problems:
        log.error("Refusing to start in production: %s", "; ".join(problems))
        raise InsecureBootstrap(
            "Refusing to start in production: " + "; ".join(problems) + ". "
            "Set real values in /opt/excel-erp/.env."
        )


def bootstrap(db: Session, settings: Settings | None = None) -> User:
    """Create the first admin if there is not one already. Returns the admin row."""
    settings = settings or get_settings()
    check_production_secrets(settings)

    email = settings.admin_email.strip()
    # Same func.lower() expression as login, so this hits uq_users_email_lower
    # and cannot create a second admin differing only in case.
    existing = db.execute(
        select(User).where(func.lower(User.email) == email.lower())
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    user = User(
        email=email,
        full_name=settings.admin_full_name,
        password_hash=hash_password(settings.admin_password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log.info("Bootstrapped first admin %s", email)
    return user


__all__ = ["InsecureBootstrap", "bootstrap", "check_production_secrets"]
