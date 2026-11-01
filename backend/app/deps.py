"""Request-scoped dependencies: who is calling, and how much they may have.

`require_role` is deliberately written and tested while nothing uses it.
Slice 1 has exactly one admin, so applying it now would be theatre — but an
authorization layer invented later, under pressure, is the one that gets the
default wrong. Having it here means adding staff accounts is an annotation on a
route, not a design decision.
"""

from collections.abc import Callable

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from .constants import UserRole
from .db import get_db
from .models import User
from .security import Forbidden, NotAuthenticated, TokenError, decode_session_token

SESSION_COOKIE = "session"

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200


def client_ip(request: Request) -> str:
    """The caller's address as nginx saw it.

    nginx sets X-Real-IP to $remote_addr, which the client cannot influence.
    X-Forwarded-For is only a fallback, and then its *last* entry: nginx
    appends the real peer, while everything before it is whatever the client
    chose to send — trusting the first entry let anyone reset the login limit.
    """
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip[:64]
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last[:64]
    return request.client.host[:64] if request.client else "unknown"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the session cookie to a live user row.

    The role travels in the token but is never trusted from it: the user is
    re-read every request, so deactivating an account takes effect immediately
    rather than in up to eight hours.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise NotAuthenticated("Please sign in.")

    try:
        payload = decode_session_token(token)
    except TokenError as exc:
        raise NotAuthenticated("Your session has expired. Please sign in again.") from exc

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise NotAuthenticated("Your session is not valid. Please sign in again.") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotAuthenticated("Your account is no longer active.")

    # Sessions minted under an older epoch are dead. Rotating the cookie on
    # change-password is not enough on its own: the old token stays
    # cryptographically valid until it expires, so a stolen session would
    # otherwise survive the very action taken to end it.
    if int(payload.get("epoch", 0)) != user.session_epoch:
        raise NotAuthenticated("Your password was changed. Please sign in again.")

    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Build a dependency that admits only the listed roles.

    `owner_only` below is the one the app uses.
    """

    allowed = frozenset(roles)

    def _guard(user: User = Depends(get_current_user)) -> User:
        # Coerced rather than compared raw: the column is a VARCHAR, and
        # StrEnum members hash by name, so `"admin" in {UserRole.ADMIN}` is False.
        try:
            role = UserRole(str(user.role))
        except ValueError:
            raise Forbidden("You do not have permission to do that.") from None
        if role not in allowed:
            raise Forbidden("You do not have permission to do that.")
        return user

    return _guard


class Pagination:
    """A validated `?page=&page_size=` pair.

    The cap is enforced here rather than in each router so no list endpoint can
    be talked into materialising the whole table by a hand-written query string.
    """

    __slots__ = ("page", "page_size")

    def __init__(self, page: int, page_size: int) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def get_pagination(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> Pagination:
    return Pagination(page=page, page_size=page_size)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "SESSION_COOKIE",
    "Pagination",
    "client_ip",
    "get_current_user",
    "get_pagination",
    "owner_only",
    "require_role",
]


# Owner-only routes: deleting, analytics, settings, staff, the activity log.
owner_only = require_role(UserRole.ADMIN)
