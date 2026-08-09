#!/bin/sh
# Entrypoint for both the HA add-on and plain Docker.
#
# Starts as root only to make /data writable, then drops to the unprivileged
# `financials` user. If dropping privileges is not possible on this host the
# app still starts as root and says so — a hardened container that refuses to
# boot is worse than a running one that reports its own state honestly.
set -eu

APP_USER=financials
DATA_DIR=${DATA_DIR:-/data}

echo "[financials] start; data=${DATA_DIR}"

mkdir -p "${DATA_DIR}/uploads"

if [ "$(id -u)" = "0" ] && command -v su-exec >/dev/null 2>&1 \
   && id "${APP_USER}" >/dev/null 2>&1; then
    if chown -R "${APP_USER}:${APP_USER}" "${DATA_DIR}" 2>/dev/null; then
        echo "[financials] draaien als ${APP_USER} (niet-root)"
        exec su-exec "${APP_USER}" \
            uvicorn app.main:app \
                --host 0.0.0.0 --port 8000 \
                --proxy-headers --forwarded-allow-ips="*" \
                --no-server-header
    fi
    echo "[financials] WAARSCHUWING: /data kon niet worden overgedragen; verder als root" >&2
fi

# Fail fast on an unwritable volume: SQLAlchemy's "unable to open database
# file" further down the line is far harder to diagnose than this.
if ! ( touch "${DATA_DIR}/.probe" && rm "${DATA_DIR}/.probe" ); then
    echo "[financials] FATAAL: ${DATA_DIR} is niet beschrijfbaar door $(id)" >&2
    exit 1
fi

exec uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips="*" \
    --no-server-header
