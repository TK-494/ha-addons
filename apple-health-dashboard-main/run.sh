#!/bin/bash
set -e

# Lees RELOAD_TOKEN uit HA options.json (geschreven door de Supervisor)
RELOAD_TOKEN=$(python3 -c "
import json, sys
try:
    d = json.load(open('/data/options.json'))
    print(d.get('reload_token', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

# Paden: /data is het persistente volume dat HA voor dit add-on monteert
export HEALTH_DIR=/data
export HEALTH_DATA_DIR=/data/parsed
export HEALTH_EXPORT_ZIP=/data/export.zip
export RELOAD_TOKEN="${RELOAD_TOKEN}"

cd /app
exec uvicorn app.main:app --host 0.0.0.0 --port 8095
