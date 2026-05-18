#!/bin/sh
# Entrypoint for both the HA add-on and standalone Docker.
#
# We MUST bind to 0.0.0.0 because Supervisor's ingress proxy runs in a
# separate container; when this add-on uses host_network: true, binding to
# 127.0.0.1 makes it unreachable from Supervisor (gives a 502 Gateway error
# in HA). The defense against LAN exposure now lives in-app: the
# IngressOnlyMiddleware in main.py rejects any request that doesn't carry
# Supervisor's ingress headers (X-Hass-User-Id / X-Ingress-Path).
BIND_HOST="${BIND_HOST:-0.0.0.0}"
BIND_PORT="${BIND_PORT:-8000}"
echo "[homelab-inventory] starting on ${BIND_HOST}:${BIND_PORT}..."
exec uvicorn app.main:app \
    --host "${BIND_HOST}" \
    --port "${BIND_PORT}" \
    --proxy-headers \
    --forwarded-allow-ips="*"
