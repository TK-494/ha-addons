#!/bin/sh
# Entrypoint for both the HA add-on and standalone Docker.
#
# Binds to 127.0.0.1, NOT 0.0.0.0. Reason: this add-on runs with
# host_network: true so the container shares the host's network stack — if
# we listened on 0.0.0.0 the entire LAN could reach port 8000 and bypass HA's
# Ingress authentication. HA's Ingress proxy reaches the add-on through the
# host's loopback, so 127.0.0.1 is sufficient and lets nothing else in.
# Override with BIND_HOST=0.0.0.0 for standalone docker-compose runs.
BIND_HOST="${BIND_HOST:-127.0.0.1}"
BIND_PORT="${BIND_PORT:-8000}"
echo "[homelab-inventory] starting on ${BIND_HOST}:${BIND_PORT}..."
exec uvicorn app.main:app \
    --host "${BIND_HOST}" \
    --port "${BIND_PORT}" \
    --proxy-headers \
    --forwarded-allow-ips="127.0.0.1"
