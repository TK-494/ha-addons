"""Runtime configuration. Everything lives under /data so Home Assistant
backups cover the database and the uploaded files together."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Financials"
APP_VERSION = "0.3.1"

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
UPLOAD_DIR = DATA_DIR / "uploads"
STATIC_DIR = Path(os.getenv("STATIC_DIR", "/app/static"))

# A bank CSV of 10k rows is roughly 2.5 MB; 25 MB is generous headroom while
# still refusing anything that would be read into memory unpleasantly.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
UPLOAD_CHUNK_BYTES = 1024 * 1024
MAX_ROWS_PER_FILE = 200_000

ALLOWED_EXTENSIONS = {".csv", ".txt"}

# Upper bounds on anything a client can ask for, so a crafted query cannot ask
# the server to materialise the whole table.
MAX_PAGE_SIZE = 500
MAX_BULK_IDS = 5_000


def ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
