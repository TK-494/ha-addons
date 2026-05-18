ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.19

FROM ${BUILD_FROM}

WORKDIR /app

# arp-scan + iproute2 power the LAN auto-discovery sweep. arp-scan needs
# NET_RAW; iproute2 gives us `ip neigh show` as a no-privilege fallback.
RUN apk add --no-cache arp-scan iproute2

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/

# Persistent inventory location lives in /data (HA-managed persistent volume)
RUN mkdir -p /data
ENV INVENTORY_PATH=/data/infrastructure.yaml

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
