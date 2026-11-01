"""Who is asking: purchase-cost visibility and the activity log.

`track` is added to every signed-in router in `main.py`. It is an *async*
dependency on purpose: FastAPI runs async dependencies in the request's own
context, so the context variable it sets is still set when the response is
serialised, and the schemas can hide purchase cost from staff. The default
is "hidden", so a route that forgets `track` fails closed.

After a successful change (POST/PATCH/PUT/DELETE) it writes one activity row
in the request's own session. A request that fails writes nothing.
"""

import json
from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .constants import UserRole
from .db import get_db
from .deps import client_ip, get_current_user
from .models import ActivityLog, User
from .services.activity import describe, label_for
from .visibility import set_can_see_cost

MUTATING = {"POST", "PATCH", "PUT", "DELETE"}


def is_owner(user: User) -> bool:
    return str(user.role) == UserRole.ADMIN.value


async def track(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AsyncIterator[None]:
    set_can_see_cost(is_owner(user))
    if request.method not in MUTATING:
        yield
        return

    route = request.scope.get("route")
    template = getattr(route, "path", request.url.path).removeprefix("/api")
    params = dict(request.path_params)
    body: dict[str, object] = {}
    # Only small JSON bodies are read for the wording ("Marked ... declined").
    # A file upload's stream belongs to the route and must not be touched.
    is_json = request.headers.get("content-type", "").startswith("application/json")
    try:
        raw = await request.body() if is_json else b""
        parsed = json.loads(raw) if raw else {}
        body = parsed if isinstance(parsed, dict) else {}
    except (ValueError, UnicodeDecodeError):
        body = {}
    # Named before the change, so a delete still says what was deleted.
    label = label_for(db, template, params)
    user_id, user_name = user.id, user.full_name or user.email

    yield

    action, area, entity_id, link = describe(request.method, template, params, body, label)
    try:
        db.add(
            ActivityLog(
                user_id=user_id,
                user_name=user_name,
                action=action[:200],
                area=area,
                entity_id=entity_id,
                link=link[:200],
                method=request.method,
                path=request.url.path[:300],
                ip=client_ip(request),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
