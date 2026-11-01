#!/usr/bin/env bash
# Deploy Excel Engineers ERP. Run on the VPS from /opt/excel-erp.
#
# Wrapped in main() so that a `git pull` replacing this file mid-run cannot
# make bash execute half-old, half-new content — that bit the MetricsGo deploy
# once and the worker silently never started.
set -euo pipefail

main() {
  cd /opt/excel-erp

  echo "== pull =="
  git -C src pull --ff-only

  echo "== sync deploy files =="
  cp src/docker-compose.prod.yml ./docker-compose.yml

  echo "== build =="
  docker compose --profile tools build api migrate

  echo "== migrate (must succeed before the API serves) =="
  docker compose --profile tools run --rm migrate

  echo "== start api =="
  docker compose up -d db api

  echo "== build the SPA and publish it for nginx =="
  docker build -t excel-erp-web:latest ./src/frontend
  rm -rf /var/www/excel-erp.new
  mkdir -p /var/www/excel-erp.new
  # The web image has no runtime; copy /app/dist out of a stopped container.
  cid=$(docker create excel-erp-web:latest)
  docker cp "$cid:/app/dist/." /var/www/excel-erp.new/
  docker rm "$cid" >/dev/null
  # Swap atomically so a request mid-deploy never sees a half-copied bundle.
  rm -rf /var/www/excel-erp.old
  [ -d /var/www/excel-erp ] && mv /var/www/excel-erp /var/www/excel-erp.old
  mv /var/www/excel-erp.new /var/www/excel-erp
  chown -R www-data:www-data /var/www/excel-erp

  echo "== health =="
  for i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:3300/api/health >/dev/null; then
      curl -s http://127.0.0.1:3300/api/health; echo
      echo "DEPLOY OK"
      return 0
    fi
    sleep 2
  done
  echo "DEPLOY FAILED: API did not become healthy" >&2
  docker compose logs --tail=50 api >&2
  return 1
}

main "$@"
