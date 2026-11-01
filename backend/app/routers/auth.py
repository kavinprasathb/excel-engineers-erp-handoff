"""Sign in, sign out, and change your password.

The session is a signed cookie the browser cannot read. v2 kept a JWT in
localStorage, which meant any XSS anywhere on the page — including in a
supplier's name — was a full account takeover.
"""

import time
from collections import deque
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import SESSION_COOKIE, client_ip, get_current_user
from ..models import User
from ..schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, UserOut
from ..security import (
    InvalidCredentials,
    RateLimited,
    TokenError,
    create_session_token,
    decode_session_token,
    dummy_verify,
    hash_password,
    verify_password,
)
from ..services import activity

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_MAX_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 60
# Per address as well as per IP: rotating IPs gets past the per-IP window,
# but not this one.
EMAIL_MAX_FAILURES = 5
EMAIL_WINDOW_SECONDS = 15 * 60
# A bound on memory, not a limit anyone should reach: past it, expired buckets
# are swept and, failing that, the oldest are dropped.
MAX_BUCKETS = 10_000

# In-process sliding windows. One API process at this scale, so a shared store
# would be infrastructure bought to solve a problem we do not have; if a
# second process ever appears, this becomes per-process and needs Redis.
_attempts: dict[str, deque[float]] = {}
_email_failures: dict[str, deque[float]] = {}

RATE_LIMITED_MESSAGE = "Too many sign-in attempts. Please wait a minute and try again."


def _bucket(store: dict[str, deque[float]], key: str, window: float, now: float) -> deque[float]:
    """The live window for `key`, pruned, with the store kept bounded."""
    bucket = store.get(key)
    if bucket is None:
        if len(store) >= MAX_BUCKETS:
            for k in [k for k, b in store.items() if not b or now - b[-1] > window]:
                del store[k]
            while len(store) >= MAX_BUCKETS:
                del store[next(iter(store))]
        bucket = store[key] = deque()
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    return bucket


def _check_rate_limit(request: Request, email: str = "") -> None:
    now = time.monotonic()
    bucket = _bucket(_attempts, client_ip(request), LOGIN_WINDOW_SECONDS, now)
    if len(bucket) >= LOGIN_MAX_ATTEMPTS:
        raise RateLimited(RATE_LIMITED_MESSAGE)
    if email and len(_bucket(_email_failures, email, EMAIL_WINDOW_SECONDS, now)) >= (
        EMAIL_MAX_FAILURES
    ):
        raise RateLimited(RATE_LIMITED_MESSAGE)
    bucket.append(now)


def _record_failure(email: str) -> None:
    now = time.monotonic()
    _bucket(_email_failures, email, EMAIL_WINDOW_SECONDS, now).append(now)


def reset_rate_limits() -> None:
    """Only for tests; a running server has no reason to forget an attacker."""
    _attempts.clear()
    _email_failures.clear()


def _set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        # str(): the column is a plain VARCHAR, so this is already a string on a
        # loaded row but a UserRole on one just constructed in memory.
        create_session_token(
            user_id=user.id, role=str(user.role), session_epoch=user.session_epoch
        ),
        max_age=settings.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    email = body.email.lower()
    _check_rate_limit(request, email)

    # func.lower() rather than ilike or a Python-side comparison: this is the
    # expression the uq_users_email_lower index is built on, so it is both the
    # uniqueness rule and an index seek.
    user = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none()

    # Always spend the cost of one argon2 verification, even for an unknown
    # address, so the response time does not enumerate our users.
    if user is None or not user.is_active:
        dummy_verify()
        _record_failure(email)
        raise InvalidCredentials("Incorrect email or password.")
    if not verify_password(body.password, user.password_hash):
        _record_failure(email)
        raise InvalidCredentials("Incorrect email or password.")

    user.last_login_at = datetime.now(UTC)
    activity.record(db, user=user, action="Signed in", area="Sign-in", ip=client_ip(request))
    db.commit()
    db.refresh(user)

    _set_session_cookie(response, user)
    return LoginResponse(user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """Unauthenticated on purpose: logging out with a dead cookie must still work.

    A live cookie is also revoked server-side by bumping the session epoch, so
    a copy of it (stolen, or left on a shared PC) stops working too. The epoch
    is per user, not per session, so this signs the user out on every device;
    at this scale that is the simple, safe trade.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        try:
            payload = decode_session_token(token)
            user = db.get(User, int(payload["sub"]))
            if user is not None and int(payload.get("epoch", 0)) == user.session_epoch:
                user.session_epoch += 1
                db.commit()
        except (TokenError, KeyError, TypeError, ValueError):
            pass  # already dead: nothing to revoke
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Rotate the session as well as the hash.

    Changing a password is what someone does when they think it leaked, so the
    old cookie has to stop working — otherwise the attacker keeps the session
    the victim was trying to close.
    """
    if not verify_password(body.current_password, user.password_hash):
        raise InvalidCredentials("Your current password is not correct.")

    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    # Kills every outstanding session, including any an attacker holds. The
    # fresh cookie set below carries the new epoch, so the person who made the
    # change stays signed in and everyone else is turned out.
    user.session_epoch += 1
    db.commit()
    db.refresh(user)

    _set_session_cookie(response, user)
