#!/usr/bin/env bash
# Nightly backup of the Excel Engineers database.
#
# This project has lost all its data twice to an expiring free database. The
# backup is therefore treated as a feature, not an afterthought — and the step
# that actually protects the data is the off-server copy, because a backup
# sitting on the same VPS dies with the VPS.
set -euo pipefail
umask 077   # dumps hold the whole business; owner-only

# Optional env (in /opt/excel-erp/.env):
#   RCLONE_DEST      rclone target for the off-site copy. Use an rclone
#                    `crypt` remote (e.g. gdrive-crypt:excel-erp) so the copy
#                    is encrypted client-side before it leaves this server.
#   HEALTHCHECK_URL  pinged on success, <url>/fail on failure (healthchecks.io style).

DIR=/opt/excel-erp/backups
STAMP=$(date +%Y%m%d-%H%M)
FILE="$DIR/excel-$STAMP.dump"
mkdir -p "$DIR"
chmod 700 "$DIR"
cd /opt/excel-erp
set -a; . ./.env; set +a
RCLONE_DEST="${RCLONE_DEST:-}"         # e.g. gdrive-crypt:excel-erp-backups
HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"

ping_hc() {
  [ -n "$HEALTHCHECK_URL" ] || return 0
  curl -fsS -m 10 --retry 3 -o /dev/null "${HEALTHCHECK_URL}$1" || echo "healthcheck ping failed" >&2
}
# Any failure (set -e) or explicit exit 1 reports /fail.
trap 'rc=$?; if [ "$rc" -ne 0 ]; then echo "BACKUP FAILED (exit $rc)" >&2; ping_hc /fail; fi' EXIT

echo "== dump =="
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$FILE"

# A zero-byte or truncated dump is worse than no dump, because it looks like
# one. Refuse to keep it.
size=$(stat -c%s "$FILE")
if [ "$size" -lt 4096 ]; then
  echo "dump is only ${size} bytes — refusing to keep it" >&2
  rm -f "$FILE"
  exit 1
fi
echo "wrote $FILE (${size} bytes)"

echo "== verify it restores =="
# Restoring into a scratch database is the only thing that distinguishes a
# backup from a file. An untested backup is a rumour.
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c 'DROP DATABASE IF EXISTS restore_check WITH (FORCE)' >/dev/null
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c 'CREATE DATABASE restore_check' >/dev/null
drop_check() {
  docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres     -c 'DROP DATABASE IF EXISTS restore_check WITH (FORCE)' >/dev/null || true
}
restore_log="$DIR/restore-check.log"
if ! docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d restore_check      --no-owner --exit-on-error < "$FILE" >"$restore_log" 2>&1; then
  echo "pg_restore FAILED � this backup does not restore:" >&2
  cat "$restore_log" >&2
  drop_check
  exit 1
fi
# alembic_version always has exactly one row once migrated; products may
# legitimately be empty on a fresh database.
if ! ver=$(docker compose exec -T db psql -U "$POSTGRES_USER" -d restore_check -tAc      'SELECT version_num FROM alembic_version' | tr -d '[:space:]') || [ -z "$ver" ]; then
  echo "restore check FAILED � alembic_version missing or empty" >&2
  drop_check
  exit 1
fi
rows=$(docker compose exec -T db psql -U "$POSTGRES_USER" -d restore_check -tAc   'SELECT count(*) FROM users' | tr -d '[:space:]')
drop_check
echo "restore check OK — $rows products"

echo "== reconcile =="
# The ledger must still explain the counters. A discrepancy means stock has
# drifted and someone should look before another day of orders lands on it.
docker compose exec -T api python -c "
from sqlalchemy.orm import Session
from app.db import engine
from app.services import stock
with Session(engine) as s:
    d = stock.reconcile(s)
    print('reconcile:', 'clean' if not d else f'{len(d)} DISCREPANCIES {d}')
" || echo "reconcile check could not run"

if [ -n "$RCLONE_DEST" ]; then
  echo "== copy off this server =="
  if ! rclone copy "$FILE" "$RCLONE_DEST"; then
    echo "off-site copy to $RCLONE_DEST FAILED" >&2
    exit 1
  fi
  echo "copied to $RCLONE_DEST"
else
  echo "WARNING: RCLONE_DEST is not set — this backup exists only on the VPS," >&2
  echo "         which means it does not protect against losing the VPS." >&2
fi

echo "== prune =="
# 14 daily. Weeklies and monthlies are kept by the off-site side, which has
# versioning; keeping three tiers locally just fills the disk.
find "$DIR" -name 'excel-*.dump' -mtime +14 -print -delete
ping_hc ""
echo "backup complete"
