#!/bin/sh
# Entrypoint for both the HA add-on and standalone Docker.
echo "[finance-dashboard] starting on port 8000..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips="*"
