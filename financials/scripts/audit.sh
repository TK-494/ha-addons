#!/bin/sh
# Check the pinned Python dependencies against the CVE database.
#
# Deliberately NOT part of the Docker build: a new advisory published upstream
# would then break the add-on's build in Home Assistant, at the exact moment
# the user is trying to install or update it. A dependency alert should
# interrupt the maintainer, not the user's install.
#
# Run before releasing a new version:
#     ./scripts/audit.sh
set -eu

cd "$(dirname "$0")/.."

if ! command -v pip-audit >/dev/null 2>&1; then
    echo "pip-audit is niet geïnstalleerd. Installeer met: pip install pip-audit" >&2
    exit 1
fi

echo "Controle van backend/requirements.txt…"
pip-audit --requirement backend/requirements.txt --strict
echo "Geen bekende kwetsbaarheden."
