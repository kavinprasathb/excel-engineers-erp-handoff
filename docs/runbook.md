# Runbook

Operational procedures for the Excel Engineers ERP. Written to be followed
under pressure, so each section is a sequence of commands with the reasoning
kept short.

## The one forbidden command

```
docker compose down -v      # ← NEVER. -v deletes the pg_data volume.
```

This project has already lost all its data twice to a expiring free database.
`-v` is the most likely way it happens a third time. To stop the stack, use
`docker compose down` (no flag) or `docker compose stop`.

## Server

Hostinger VPS `<VPS_HOST>` / `<VPS_IP>`. It also runs metricsgo,
analyst-agent, analytics-agent, mirra and n8n — **this app must not disturb
them**. Everything for this app lives under `/opt/excel-erp`.

### Access

SSH key auth (an `ed25519` public key is in `/root/.ssh/authorized_keys`):

```bash
ssh root@<VPS_IP>
```

Password auth is still enabled as a fallback. Note for anyone reading the old
access guide: the claim that this box rejects the standard `ssh` client applies
to **password** auth only — with a key, plain `ssh` works, and the paramiko
workaround is unnecessary.

### Port allocations on this box

| port | service |
|---|---|
| 3100 | metricsgo |
| 3200 | analyst-agent frontend |
| 8100 | analytics-agent |
| 8200 | analyst-agent backend |
| 8092 | mirra web |
| 5678 | n8n |
| **5442** | **excel-erp Postgres** |
| **3300** | **excel-erp API (reserved, not yet deployed)** |

Check before claiming a new one: `ss -tln`.

## Database

Its own container, volume and credentials — deliberately not shared with the
other projects on this box.

```bash
cd /opt/excel-erp
docker compose -f docker-compose.db.yml ps
docker compose -f docker-compose.db.yml logs --tail=50 db
```

Credentials: `/opt/excel-erp/.env`, mode 600, never in git.
Databases: `excel` (live) and `excel_test` (dropped and recreated by the test
suite — never point tests at `excel`).

Published on `127.0.0.1:5442` only. Never bind `0.0.0.0`: there is currently no
firewall on this box, so the loopback bind is the only thing between a
published port and the internet.

```bash
# psql on the server
docker compose -f docker-compose.db.yml exec db psql -U excel -d excel
```

## Local development

Postgres is not installed locally; dev connects to the VPS database through an
SSH tunnel.

```bash
# terminal 1 — keep this running. It reconnects on its own; the server drops
# idle SSH sessions, so a bare `ssh -L` will die during a long working session.
make tunnel

# terminal 2
make dev-api        # http://127.0.0.1:8000
# terminal 3
make dev-web        # http://localhost:5173  ← always browse here, not :8000
```

`backend/.env` points at `127.0.0.1:5442`, so the tunnel must be up before the
API starts. If the API reports `db: error` on `/api/health`, check the tunnel
first.

## Migrations

```bash
make migrate                       # alembic upgrade head
make revision m="what changed"     # autogenerate, then READ THE DIFF
```

Autogenerate reliably misses two things — add them by hand:
- `CREATE EXTENSION`, which must precede any index that uses it
- data seeds (e.g. the `app_settings` singleton row)

Every migration must have a working `downgrade()`; the test suite runs
`upgrade → downgrade → upgrade` and will fail if it does not.

## Deploy

Live at **https://<LIVE_DOMAIN>**.

```bash
# from your machine
git push vps main
ssh root@<VPS_IP> 'cd /opt/excel-erp && ./deploy.sh'
```

`deploy.sh` pulls, builds, runs the one-shot `migrate` service to completion,
starts the API on `127.0.0.1:3300`, rebuilds the SPA into `/var/www/excel-erp`
via an atomic directory swap, then polls `/api/health` and fails loudly if the
API never becomes healthy. A failed migration stops the deploy rather than
surfacing as runtime 500s.

nginx vhost: `/etc/nginx/sites-available/<LIVE_DOMAIN>`,
TLS by certbot with auto-renewal already scheduled.

### Applying nginx hardening (security headers, login rate limit)

The installed vhost has certbot's SSL lines and :443 block in it, which the
repo copy (`deploy/nginx-excel-erp.conf`) does not. **Never copy the repo file
over it — merge.** Touch only this app's files; nginx is shared with metricsgo,
n8n and analytics.

```bash
V=/etc/nginx/sites-available/<LIVE_DOMAIN>
cp -a $V /root/erp-vhost.bak.$(date +%F-%H%M)                 # 1. backup
install -m 644 /opt/excel-erp/src/deploy/nginx-excel-erp-security-headers.conf   /etc/nginx/snippets/excel-erp-security-headers.conf          # 2. snippet
nano $V                                                        # 3. merge, below
nginx -t && systemctl reload nginx                             # 4. test, reload
curl -sI https://<LIVE_DOMAIN>/ | grep -iE 'strict|content-security|x-frame'
```

Merge edits (in every `server` block for this host, i.e. both :80 and :443):

1. At the very top of the file, outside any `server {}`:
   `limit_req_zone $binary_remote_addr zone=excelerp_login:10m rate=10r/m;`
   (only once in the file).
2. In the server block: `server_tokens off;` and
   `include /etc/nginx/snippets/excel-erp-security-headers.conf;`
3. `X-Forwarded-For $proxy_add_x_forwarded_for` → `X-Forwarded-For $remote_addr`.
4. Add the `location = /api/auth/login { ... }` block from the repo file.
5. Add the same `include` line inside `location /assets/` and `location /`
   (their own `add_header` otherwise drops the server-level headers).

If the :80 block is only certbot's `return 301` redirect, leave it alone and
apply 2–5 to the :443 block that serves the app.

**Rollback:** `cp /root/erp-vhost.bak.<stamp> $V && nginx -t && systemctl reload nginx`.
If `nginx -t` fails, do not reload — restore the backup first; the running
nginx keeps serving the old config until a successful reload.
Smoke test after: sign in, open a quotation PDF, check the browser console for
CSP violations.

**Rollback:** `git -C src checkout <sha> && ./deploy.sh`. If the bad deploy
included a schema change, run `alembic downgrade` first — the app will not
start against a schema ahead of its code.

## Backups

`/opt/excel-erp/backup.sh` runs nightly at 02:00 via cron, logging to
`backups/backup.log`. Each run dumps, **refuses a dump under 4 KB** (a
truncated dump is worse than none because it looks like one), **restores it
into a scratch database and counts the rows**, and runs `reconcile()` so a
drift between the stock ledger and the counters is caught within a day.

```bash
cd /opt/excel-erp && ./backup.sh              # run one now
./restore.sh backups/excel-YYYYMMDD-HHMM.dump # inspect a backup safely
```

`restore.sh` never overwrites production; it restores into a scratch database
and prints the commands to promote it, for a human to run deliberately.

**⚠️ The off-site copy is not configured.** Until `RCLONE_DEST` is set in
`/opt/excel-erp/.env`, every backup lives only on this VPS — which means it
protects against a bad migration or a mistaken delete, but not against losing
the server. Setting it up needs an interactive `rclone config` to authorise a
Google Drive (or B2/R2) remote:

```bash
rclone config                      # create a remote named e.g. gdrive
rclone config                      # then a `crypt` remote gdrive-crypt wrapping gdrive:excel-erp
echo 'RCLONE_DEST=gdrive-crypt:' >> /opt/excel-erp/.env
echo 'HEALTHCHECK_URL=https://hc-ping.com/<uuid>' >> /opt/excel-erp/.env  # optional
```

## Known issues on the shared box

Pre-existing, not caused by this app, left alone deliberately so as not to
disturb the other services. Worth fixing when someone can babysit them:

1. **`waitress-serve` listens on `0.0.0.0:8080`** — publicly reachable,
   bypassing nginx, so no TLS and no rate limiting. Fix: rebind to `127.0.0.1`
   and proxy through nginx. Requires restarting that service.
2. **No firewall** — UFW inactive, iptables policy ACCEPT. This is what makes
   (1) reachable from the internet. Fix: default-deny inbound, allow 22/80/443.
   Enumerate every listener first; five other services share this box.
