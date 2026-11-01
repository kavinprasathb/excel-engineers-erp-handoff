#!/usr/bin/env bash
# Keep a tunnel open from localhost:5442 to the excel-erp Postgres on the VPS.
#
# The database deliberately publishes only on the server's loopback interface,
# so local development reaches it through SSH. The server drops idle sessions
# ("Connection reset by peer"), which is why this reconnects rather than being
# a bare `ssh -L` you restart by hand.
#
# Usage:  ./scripts/db-tunnel.sh     (leave running in its own terminal)
set -u

HOST="${VPS_HOST:-root@<VPS_IP>}"
PORT="${DB_TUNNEL_PORT:-5442}"

echo "tunnel: localhost:${PORT} -> ${HOST} 127.0.0.1:${PORT}  (ctrl-c to stop)"

while true; do
  ssh -N \
      -o BatchMode=yes \
      -o ExitOnForwardFailure=yes \
      -o ServerAliveInterval=20 \
      -o ServerAliveCountMax=3 \
      -o StrictHostKeyChecking=accept-new \
      -L "127.0.0.1:${PORT}:127.0.0.1:${PORT}" \
      "$HOST"
  code=$?
  # 0 means someone closed it deliberately; anything else is a drop worth retrying.
  if [ $code -eq 0 ]; then
    echo "tunnel closed cleanly"
    break
  fi
  echo "tunnel dropped (exit ${code}); reconnecting in 3s…"
  sleep 3
done
