ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.19

# ─── Stage 1: build React frontend ──────────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ─── Stage 2: HA add-on runtime ─────────────────────────────────────────────
FROM ${BUILD_FROM}

RUN apk add --no-cache build-base

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/

# Bring in the static frontend bundle
COPY --from=frontend-build /build/dist ./static

# Persistent SQLite location lives in /data (HA-managed persistent volume)
RUN mkdir -p /data
ENV DATABASE_URL=sqlite:////data/finance.db

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
