ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.19
FROM ${BUILD_FROM}

# Stdlib only: no requirements.txt, nothing to audit.
WORKDIR /app
COPY app/ ./
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
