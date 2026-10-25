"""The shell must never be cached, the bundles always.

This is the bug behind "I updated the add-on and nothing changed": served
without Cache-Control, a browser invents its own freshness from the file's
age, so a long-installed version kept its old `index.html` — and therefore
its old bundle — for days after an update. The add-on version said 0.23.0
while the screen was still 0.21.0.
"""

from __future__ import annotations


def test_the_spa_shell_must_always_be_revalidated(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"


def test_an_unknown_route_falls_back_to_a_revalidated_shell(client):
    """Deep links land here too, and they must not pin an old shell either."""
    response = client.get("/transacties")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_fingerprinted_assets_may_be_cached_forever(client, tmp_path):
    (client.data_dir / "static" / "assets").mkdir(parents=True, exist_ok=True)
    (client.data_dir / "static" / "assets" / "index-abc123.js").write_text(
        "console.log(1)", encoding="utf-8"
    )
    response = client.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_an_unfingerprinted_file_is_revalidated(client):
    """A favicon keeps its name across releases, so it must not be pinned."""
    (client.data_dir / "static" / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    response = client.get("/favicon.svg")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_health_names_the_bundle_the_shell_points_at(client):
    """A page can only notice it is stale if it can ask what current is."""
    static = client.data_dir / "static"
    (static / "assets").mkdir(parents=True, exist_ok=True)
    (static / "index.html").write_text(
        '<!doctype html><html><head>'
        '<script type="module" crossorigin src="./assets/index-NEW123.js"></script>'
        '</head><body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    data = client.get("/api/health").json()
    assert data["bundle"] == "assets/index-NEW123.js"
    assert data["status"] == "ok"


def test_health_survives_a_shell_it_cannot_parse(client):
    """An unexpected index.html must not take the health check down with it."""
    (client.data_dir / "static" / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["bundle"] is None
