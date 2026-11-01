# Excel Engineers ERP (v3)

Order management for Excel Engineers, Salem — a KSB pump dealer. Quotations, orders,
purchase orders, inventory, contacts, workforce and analytics in one place.

This is the **v3 rebuild**: own Postgres, deployed to the Hostinger VPS. Earlier builds
(`Desktop\Excel Engineer`, `Desktop\Excel 2.0`) are reference only.

## Stack

FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · Postgres 16
React 19 · Vite · TypeScript · Tailwind v4 · TanStack Query

## Local setup

Requires Python 3.12 (via `uv`), Node 22, and a **native Postgres 16** — there is no
Docker on the dev machine; the Docker files here run only on the VPS.

```bash
# once: create the databases
createdb -U postgres excel
createdb -U postgres excel_test

cp backend/.env.example backend/.env   # then edit
make install
make migrate
make dev-api      # terminal 1  -> http://127.0.0.1:8000
make dev-web      # terminal 2  -> http://localhost:5173
```

The web dev server proxies `/api` to the API, so the session cookie is same-origin in
dev exactly as it is in production. Always browse via `localhost:5173`, not the API port.

## Layout

```
backend/app/models      SQLAlchemy tables
backend/app/services    domain logic — stock.py is the ONLY writer of stock counters
backend/app/routers     HTTP surface
frontend/src/features   one folder per module (api hooks + page + components)
frontend/src/api        generated OpenAPI types — never hand-edited
```

## Conventions that matter

- **Money is integer paise** (`BigInteger`), formatted only in the browser.
- **GST is basis points** (`1800` = 18%) — integer percent cannot express the 0.25% slab.
- **All stock changes go through `app/services/stock.py`.** A session guard raises if
  anything else touches the counters, and CI greps for bypasses.
- `quantity_available` is a Postgres generated column. Never compute it in Python or TS.
- Constants live in `app/constants.py` and reach the frontend as generated types.

See `docs/runbook.md` for deploy, restore and backup procedures.
