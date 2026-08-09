"""Shared test fixtures.

Each test gets a fresh app against a throwaway `/data`, so nothing leaks
between tests and no real bank data is ever involved.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client():
    tmp = tempfile.mkdtemp(prefix="financials-test-")
    static = Path(tmp) / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    # A file that must stay unreachable through the SPA fallback.
    (Path(tmp) / "secret.db").write_text("SENSITIVE", encoding="utf-8")

    os.environ["DATA_DIR"] = tmp
    os.environ["STATIC_DIR"] = str(static)
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/test.db"

    # The app reads its configuration at import time, so it has to be reloaded
    # for each temporary directory.
    for name in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        del sys.modules[name]

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        test_client.data_dir = Path(tmp)  # type: ignore[attr-defined]
        yield test_client


def upload(client, fixture: str, format_key: str = "auto", filename: str | None = None):
    with (FIXTURES / fixture).open("rb") as fh:
        return client.post(
            "/api/imports/upload",
            files={"file": (filename or fixture, fh, "text/csv")},
            data={"format_key": format_key},
        )


def import_fixture(client, fixture: str, format_key: str = "auto"):
    preview = upload(client, fixture, format_key).json()
    committed = client.post(
        f"/api/imports/{preview['batch_id']}/commit",
        params={"format_key": preview["format_key"]},
    )
    assert committed.status_code == 200, committed.text
    return preview, committed.json()
