ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20

# ─── Stage 1: build the React bundle ────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /build
COPY frontend/package.json ./
# `npm install` rather than `npm ci`: this repo ships no package-lock.json.
# Generate one (`npm install` locally, commit the lock file) and switch this to
# `npm ci` to get reproducible frontend builds.
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ─── Stage 2: runtime ───────────────────────────────────────────────────────
FROM ${BUILD_FROM}

# su-exec drops privileges at startup; curl is for the healthcheck.
RUN apk add --no-cache su-exec curl

WORKDIR /app

COPY backend/requirements.txt ./
# Versions are pinned in requirements.txt; `scripts/audit.sh` checks them for
# advisories out of band, deliberately not during this build.
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY --from=frontend /build/dist ./static

# Unprivileged account for the application process. The entrypoint starts as
# root only long enough to make /data writable, then steps down to this user.
# No fixed UID: 1000 is often already taken on a base image, and a clashing
# adduser would fail the whole build for no benefit — nothing here depends on
# the number matching anything outside the container.
RUN addgroup -S financials \
    && adduser -S -G financials -h /app financials \
    && chown -R financials:financials /app

ENV DATABASE_URL=sqlite:////data/financials.db \
    DATA_DIR=/data \
    STATIC_DIR=/app/static \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["/run.sh"]
