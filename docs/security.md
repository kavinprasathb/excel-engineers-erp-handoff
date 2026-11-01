# Security posture

The baseline every part of this app is held to. These are requirements, not
aspirations: each one names how it is enforced, because a rule nobody checks
decays. Where a control is enforced by CI or by the database, that is stated —
prefer those over discipline.

## Threat model

A single-tenant internal business app. Realistic threats, in order:

1. **Credential compromise** — a password leaked, reused, or phished. Already
   happened once during development (a root password pasted into a chat).
2. **Secrets in the repository** — v2 committed `.env` and a database file.
3. **Data loss** — not an attacker; expiry and operator error. Data has been
   lost twice on this project. Treated as a security concern because the
   outcome is identical.
4. **XSS leading to session theft** — the app renders customer- and
   supplier-supplied text (names, notes, addresses).
5. **Exposed infrastructure** — a database port open to the internet.

Explicitly *not* in the model: multi-tenant isolation, nation-state actors,
side-channel attacks.

## Authentication

| Control | Detail | Enforced by |
|---|---|---|
| Password hashing | **argon2id** via `argon2-cffi`. Not bcrypt — its 72-byte truncation silently ignores the tail of a long password. | `app/security.py`, unit test |
| Session transport | **httpOnly + Secure + SameSite=Lax cookie**. Never `localStorage` — v2 stored a JWT there, readable by any XSS. | `app/routers/auth.py`, test asserts the flags |
| Session lifetime | A flat 8 hours. Long enough for a working day, short enough that a stolen cookie expires. **No sliding refresh** — it was considered and dropped: it extends exactly the sessions an attacker is actively using. | config |
| Session revocation | Changing a password stamps `users.password_changed_at`; every token issued earlier is refused. Rotating the cookie alone is not enough — the old JWT stays cryptographically valid until it expires, so a stolen session would survive the action taken to end it. | `app/deps.py`, test |
| Login rate limit | 10 attempts/minute/IP, in-process counter. No Redis needed at this scale. | middleware + test |
| Password policy | Minimum 12 characters, checked server-side. No composition rules — length beats theatre. | Pydantic validator |
| Admin bootstrap | Created from env vars, idempotent. **Startup refuses to boot** if the password is still a known placeholder and the database is not local. | `app/seed.py`, test |
| Roles | `require_role()` exists and is tested but unused in slice 1. Adding staff accounts later means annotating routes, not inventing an authorization layer. | `app/deps.py` |

## Secrets

- No secret ever reaches git. `.gitignore` was correct in the **first** commit,
  and a CI job fails the build if `git ls-files` matches `.env`, `*.db`,
  `*.sqlite3` or `.venv/`. v2 committed all three; this makes it impossible
  rather than remembered.
- Production values live only in `/opt/excel-erp/.env` on the VPS, mode `600`.
- `.env.example` carries placeholder values and is the only env file in git.
- `JWT_SECRET` is 32 random bytes (`openssl rand -hex 32`), distinct per
  environment. The app refuses to start with the placeholder value against a
  non-local database.
- **Any secret that appears in a chat, ticket or document is considered burned
  and is rotated.** No exceptions, no "it was only for a minute".

## Transport and headers

- HTTPS only, terminated by the existing nginx + certbot on the VPS. HTTP
  redirects to HTTPS.
- HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: same-origin`, and a Content-Security-Policy with no
  `unsafe-inline` for scripts.
- SPA and API are served from **one origin**, so the session cookie is
  same-site and CORS is empty in production. Dev matches via the Vite proxy —
  no environment-specific auth behaviour to get wrong.

## Application

- **SQL injection**: all queries go through SQLAlchemy with bound parameters.
  Raw SQL is permitted only via `text()` with bound parameters, never
  f-strings. CI greps for f-string SQL.
- **XSS**: React escapes by default; `dangerouslySetInnerHTML` is banned and
  CI greps for it.
- **Upload safety**: imports accept `.xlsx`/`.xlsm` only, capped at 10 MB,
  parsed with `openpyxl` in `read_only` mode. Uploaded bytes are never written
  to disk and never executed.
- **Mass assignment**: request bodies are explicit Pydantic schemas; a model is
  never populated from raw client JSON.
- **Error responses** carry a stable code and a human message, never a stack
  trace or SQL text. Tracebacks go to the server log only.
- **CSRF**: `SameSite=Lax` plus an `Origin` check on every mutating request.

## Data integrity as a security property

Stock counts are money. The controls that keep them honest are listed in the
architecture notes, but belong here too:

- Three database CHECK constraints make negative and over-reserved stock
  impossible even from a `psql` prompt.
- Every counter change goes through one service, enforced by a session guard
  that raises on any bypass, plus a CI check that greps the AST.
- The append-only `stock_movements` ledger records who, what, when and why —
  and `reconcile()` proves the counters still match it. Run nightly.

## Backups

A backup is a security control: the most likely total-loss event on this
project is not an attacker.

- Nightly `pg_dump -Fc`, retained 14 daily / 8 weekly / 6 monthly.
- **Copied off the server** (rclone). A backup on the same VPS is not a backup.
- `scripts/restore.sh` drills the restore into a scratch database with a
  row-count check. An untested backup is a rumour.
- `docker compose down -v` deletes the data volume. It is named in the runbook
  as forbidden.

## Dependencies

- Lockfiles committed (`uv.lock`, `package-lock.json`); CI installs frozen.
- `pip-audit` and `npm audit --omit=dev` run in CI; a high or critical
  advisory fails the build.
- Dependabot enabled for both ecosystems.

## Infrastructure

The VPS also runs MetricsGo, hermes and analytics, so app isolation matters:

- This app gets its **own Postgres container**, its own volume and its own
  credentials. It does not share a database server with the other projects.
- Postgres publishes **no ports** — it is reachable only on the app's private
  Docker network. The API binds `127.0.0.1` and is reached only through nginx.
- Containers run as a non-root user.

Not yet done, and worth doing (touches the other projects on the box, so it
needs care): disable root password login in favour of keys, fail2ban, UFW, and
unattended security upgrades.

## Review

This document is checked when a slice ships. If a control here is not actually
enforced by the code, the entry is wrong and gets fixed or removed — an
aspirational security document is worse than none, because it is believed.
