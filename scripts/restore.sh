#!/usr/bin/env bash
# Restore a dump into a scratch database and report what is in it.
#
# Deliberately does NOT overwrite the live database: the common case is
# "check what this backup contains", and a script that silently replaces
# production is one keystroke from a disaster. Promoting a restore is the last
# two commands, printed at the end for a human to run deliberately.
set -euo pipefail

DUMP="${1:?usage: restore.sh /opt/excel-erp/backups/excel-YYYYMMDD-HHMM.dump}"
SCRATCH="${2:-excel_restore}"

cd /opt/excel-erp
set -a; . ./.env; set +a

docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS $SCRATCH WITH (FORCE)" >/dev/null
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c "CREATE DATABASE $SCRATCH" >/dev/null
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$SCRATCH" --no-owner < "$DUMP"

echo "== contents of $SCRATCH =="
for t in products suppliers categories inventory stock_movements users; do
  n=$(docker compose exec -T db psql -U "$POSTGRES_USER" -d "$SCRATCH" -tAc "SELECT count(*) FROM $t" | tr -d '[:space:]')
  printf "  %-16s %s\n" "$t" "$n"
done

cat <<MSG

Restored into '$SCRATCH'. The live database is untouched.
To promote this over production, stop the API first and run deliberately:

  docker compose stop api
  docker compose exec -T db psql -U $POSTGRES_USER -d postgres -c "DROP DATABASE $POSTGRES_DB WITH (FORCE)"
  docker compose exec -T db psql -U $POSTGRES_USER -d postgres -c "ALTER DATABASE $SCRATCH RENAME TO $POSTGRES_DB"
  docker compose up -d api
MSG
