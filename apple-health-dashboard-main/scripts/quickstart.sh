#!/usr/bin/env bash
#
# quickstart.sh — eenvoudige installatieflow voor het gezondheidsdashboard.
#
# Doel: vanaf een verse clone met één commando de app opzetten en starten.
# Veilig: maakt nooit een bestaande .env kapot en toont nooit .env-inhoud.
#
# Optionele overrides (env-vars vóór het commando):
#   APP_HOST=127.0.0.1   APP_PORT=18095   HEALTH_DATA_DIR=./data/parsed
#
# Voorbeeld:
#   ./scripts/quickstart.sh
#   APP_PORT=18095 ./scripts/quickstart.sh

set -euo pipefail

die() { echo "FOUT: $*" >&2; exit 1; }

# --- locatie: altijd vanuit de projectroot werken ----------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# --- helpers ------------------------------------------------------------------
# Vervang of voeg een KEY=VALUE toe in .env (waarde wordt niet geprint).
set_env() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  awk -v k="$key" -v v="$value" '
    $0 ~ "^"k"=" { print k"="v; done=1; next }
    { print }
    END { if (!done) print k"="v }
  ' .env > "$tmp" && mv "$tmp" .env
}

# Lees één waarde uit .env zonder het bestand te tonen.
get_env() {
  local line
  line="$(grep -E "^$1=" .env 2>/dev/null | head -1 || true)"
  printf '%s' "${line#*=}"
}

# Waarschuw als een token nog op de placeholder staat (waarde niet getoond).
warn_placeholder() {
  local key="$1"
  if [ "$(get_env "$key")" = "change-me" ]; then
    echo "WAARSCHUWING: $key staat nog op 'change-me'. Pas dit aan in .env"
    echo "             voordat je de app breder beschikbaar maakt."
  fi
}

# --- vereisten controleren ----------------------------------------------------
command -v docker >/dev/null 2>&1 \
  || die "Docker niet gevonden. Installeer Docker (Mac: Docker Desktop; Linux-server: Docker Engine + Compose-plugin)."

docker compose version >/dev/null 2>&1 \
  || die "'docker compose' werkt niet. Installeer de Docker Compose v2 plugin."

[ -f .env.example ] || die ".env.example ontbreekt in $REPO_ROOT — staat de repo compleet?"

# --- optionele overrides met veilige defaults --------------------------------
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8095}"
HEALTH_DATA_DIR="${HEALTH_DATA_DIR:-./data/parsed}"

# --- .env aanmaken (bestaande nooit overschrijven) ---------------------------
if [ -f .env ]; then
  echo "Bestaande .env gevonden — die laat ik ongemoeid."
else
  cp .env.example .env
  echo ".env aangemaakt vanaf .env.example met veilige defaults."
  set_env APP_HOST          "$APP_HOST"
  set_env APP_PORT          "$APP_PORT"
  set_env HEALTH_DATA_DIR   "$HEALTH_DATA_DIR"
  set_env RELOAD_TOKEN      "change-me"
fi

warn_placeholder RELOAD_TOKEN

# --- compose valideren en starten --------------------------------------------
echo "Compose-config controleren..."
docker compose config >/dev/null || die "docker compose config faalde — controleer .env en docker-compose.yml."

echo "Bouwen en starten..."
docker compose up -d --build

# --- afronding: nuttige info (geen .env-inhoud) ------------------------------
url_host="$(get_env APP_HOST)"; url_host="${url_host:-127.0.0.1}"
url_port="$(get_env APP_PORT)"; url_port="${url_port:-8095}"

echo ""
echo "Klaar. Het dashboard draait nu."
echo "  Lokale URL:       http://${url_host}:${url_port}/"
echo "  Upload-pagina:    http://${url_host}:${url_port}/upload"
echo "  Healthcheck:      curl http://${url_host}:${url_port}/api/import/status"
echo "  Config aanpassen: bewerk het .env-bestand in de projectmap"
echo "                    (o.a. RELOAD_TOKEN, APP_PORT, HEALTH_DATA_DIR)."
echo "  Inhoud van .env wordt bewust niet getoond."
