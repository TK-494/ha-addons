#!/bin/sh
# Entrypoint for both the HA add-on and standalone Docker.
echo "[finance-dashboard] starting on port 8000..."

# Make sure the persistent volume is reachable and writable before launching
# uvicorn — otherwise the SQLAlchemy table creation in main.py blows up with
# the opaque "unable to open database file" and the container exits.
mkdir -p /data
echo "[finance-dashboard] /data listing:"
ls -la /data || true
if ! ( touch /data/.probe && rm /data/.probe ); then
    echo "[finance-dashboard] FATAL: /data is not writable by $(id)" >&2
    exit 1
fi
echo "[finance-dashboard] /data is writable"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips="*"
