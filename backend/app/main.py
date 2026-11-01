"""FastAPI application factory.

Everything cross-cutting is assembled here and nowhere else: error shape,
security headers, CSRF origin check, the stock guard, and the first-admin
bootstrap. A route handler should never have to remember any of it.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import SessionLocal
from .errors import AppError
from .routers import (
    activity,
    analytics,
    auth,
    categories,
    customers,
    deal_tracker,
    health,
    imports,
    inventory,
    notifications,
    orders,
    products,
    quotations,
    suppliers,
    users,
)
from .routers import settings as settings_router
from .seed import bootstrap
from .services.stock import install_stock_guard
from .viewer import track

log = logging.getLogger(__name__)

MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})


def _error_body(
    code: str, message: str, details: dict[str, object] | None = None
) -> dict[str, object]:
    """The single error envelope. Never a bare string, never a traceback."""
    return {"error": {"code": code, "message": message, "details": details or {}}}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Installed on the session *factory*, so the guard covers every request the
    # app serves. conftest installs it per-session for tests; without this line
    # the production app would be the one place it was not active.
    install_stock_guard(SessionLocal)
    with SessionLocal() as db:
        bootstrap(db)
    yield


def _allowed_origins() -> set[str]:
    """Hosts a mutating request may claim to come from.

    In production the SPA and the API share one origin, so an Origin header
    that is present must be our own host. In dev the Vite origin is added from
    CORS_ORIGINS, which keeps auth behaviour identical in both environments.
    """
    return {urlsplit(o).netloc for o in get_settings().cors_origin_list if urlsplit(o).netloc}


def create_app() -> FastAPI:
    settings = get_settings()
    # No interactive docs in production: a map of every route is only useful to
    # someone who should not be exploring them.
    docs = not settings.is_production
    app = FastAPI(
        title="Excel Engineers ERP",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=_error_body(exc.code, exc.message, dict(exc.details)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic's own list is genuinely useful to the form that sent it, so
        # it is kept under `details.fields` — but the top-level shape stays the
        # same envelope every other failure uses.
        fields = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ())[1:]),
                "message": err.get("msg", ""),
            }
            for err in exc.errors()
        ]
        first = fields[0]["message"] if fields else "The request could not be understood."
        return JSONResponse(
            status_code=422,
            content=_error_body("validation_error", first, {"fields": fields}),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # The traceback belongs in the log, where an operator can read it, and
        # nowhere near the browser.
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "Something went wrong. Please try again."),
        )

    @app.middleware("http")
    async def _csrf_origin_check(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """SameSite=Lax is the primary defence; this is the belt to its braces.

        Every mutating /api request must name where it came from: Origin if
        the browser sent one, else Referer. Browsers send Origin on every
        fetch POST, so the SPA always passes; a request carrying neither is
        refused rather than trusted.
        """
        if request.method in MUTATING_METHODS and request.url.path.startswith("/api"):
            source = request.headers.get("origin") or request.headers.get("referer")
            netloc = urlsplit(source).netloc if source else ""
            if not netloc or (
                netloc != request.headers.get("host") and netloc not in _allowed_origins()
            ):
                return JSONResponse(
                    status_code=403,
                    content=_error_body("forbidden", "Cross-origin request rejected."),
                )
        return await call_next(request)

    @app.middleware("http")
    async def _security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if get_settings().is_production:
            # Only in production: sending HSTS from a dev server pins localhost
            # to HTTPS in the developer's browser for a year.
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    # Every signed-in router goes through `track`: it hides purchase cost from
    # staff and writes the activity log. Health and sign-in stay outside it.
    signed_in = [Depends(track)]
    for r in (
        settings_router.router,
        suppliers.router,
        customers.router,
        categories.router,
        products.router,
        quotations.router,
        orders.router,
        analytics.router,
        notifications.router,
        inventory.router,
        imports.router,
        users.router,
        activity.router,
        deal_tracker.router,
    ):
        app.include_router(r, prefix="/api", dependencies=signed_in)
    return app


app = create_app()
