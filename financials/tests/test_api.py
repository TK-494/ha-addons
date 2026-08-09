"""API tests: the import lifecycle, account separation and the security
guards. Runs entirely on synthetic fixtures in a temporary /data."""

from __future__ import annotations

import pytest

from conftest import FIXTURES, import_fixture, upload


# ─── upload, preview, commit ────────────────────────────────────────────────

def test_preview_does_not_write_to_the_ledger(client):
    upload(client, "rabobank_current.csv")
    assert client.get("/api/transactions/", params={"page_size": 1}).json()["total"] == 0


def test_preview_shows_parsed_sample_rows(client):
    preview = upload(client, "rabobank_current.csv").json()
    assert preview["format_key"] == "rabobank_current"
    assert preview["rows_parsed"] == 6
    assert preview["sample"][0]["amount"] == -12.34
    assert preview["date_from"] == "2024-01-02"


def test_commit_writes_and_creates_accounts(client):
    _, result = import_fixture(client, "rabobank_current.csv")
    assert result["rows_imported"] == 6
    accounts = client.get("/api/accounts/").json()
    assert {a["iban"] for a in accounts} == {"NL00TEST0000000001", "NL00TEST0000000002"}


def test_reupload_is_idempotent(client):
    import_fixture(client, "rabobank_current.csv")
    preview, result = import_fixture(client, "rabobank_current.csv")
    assert preview["rows_new"] == 0
    assert preview["duplicate_of"] is not None
    assert result["rows_imported"] == 0
    assert client.get("/api/transactions/", params={"page_size": 1}).json()["total"] == 6


def test_explicit_format_overrides_detection(client):
    response = upload(client, "rabobank_creditcard.csv", format_key="asn")
    assert response.status_code == 422
    assert "Je rekening" in response.json()["detail"]


def test_rejects_non_csv_extension(client):
    response = client.post(
        "/api/imports/upload",
        files={"file": ("statement.xlsx", b"not a csv", "application/vnd.ms-excel")},
        data={"format_key": "auto"},
    )
    assert response.status_code == 400


def test_rejects_empty_file(client):
    response = client.post(
        "/api/imports/upload",
        files={"file": ("empty.csv", b"", "text/csv")},
        data={"format_key": "auto"},
    )
    assert response.status_code == 400


# ─── stored files: persist, replay, delete ──────────────────────────────────

def test_uploaded_file_persists_under_a_generated_name(client):
    import_fixture(client, "rabobank_current.csv")
    stored = list((client.data_dir / "uploads").iterdir())
    assert len(stored) == 1
    # The client-supplied name never reaches the filesystem.
    assert "rabobank_current" not in stored[0].name


def test_hostile_filename_cannot_escape_the_upload_directory(client):
    upload(client, "rabobank_current.csv", filename="../../evil.csv")
    assert not (client.data_dir.parent / "evil.csv").exists()
    assert len(list((client.data_dir / "uploads").iterdir())) == 1


def test_download_returns_the_original_file(client):
    preview, _ = import_fixture(client, "asn.csv")
    response = client.get(f"/api/imports/{preview['batch_id']}/download")
    assert response.status_code == 200
    assert "Je rekening" in response.text


def test_delete_file_only_keeps_transactions(client):
    preview, _ = import_fixture(client, "rabobank_current.csv")
    response = client.request("DELETE", f"/api/imports/{preview['batch_id']}")
    assert response.json()["deleted_transactions"] == 0
    assert client.get("/api/transactions/", params={"page_size": 1}).json()["total"] == 6
    assert list((client.data_dir / "uploads").iterdir()) == []


def test_delete_file_with_transactions_is_a_full_undo(client):
    preview, _ = import_fixture(client, "rabobank_current.csv")
    impact = client.get(f"/api/imports/{preview['batch_id']}/impact").json()
    assert impact["transactions"] == 6

    response = client.request(
        "DELETE", f"/api/imports/{preview['batch_id']}",
        params={"delete_transactions": True},
    )
    assert response.json()["deleted_transactions"] == 6
    assert client.get("/api/transactions/", params={"page_size": 1}).json()["total"] == 0


def test_reimport_after_deleting_transactions_restores_them(client):
    """The point of keeping the file: replay without going back to the bank."""
    preview, _ = import_fixture(client, "rabobank_current.csv")
    batch_id = preview["batch_id"]
    client.request("DELETE", f"/api/imports/{batch_id}", params={"delete_transactions": True})

    import_fixture(client, "rabobank_current.csv")
    assert client.get("/api/transactions/", params={"page_size": 1}).json()["total"] == 6


# ─── account separation (PLAN §11) ──────────────────────────────────────────

def test_internal_transfer_between_own_accounts_is_paired(client):
    import_fixture(client, "rabobank_current.csv")
    internal = client.get("/api/transactions/", params={"internal": True}).json()
    groups = {i["transfer_group"] for i in internal["items"] if i["transfer_group"]}
    assert len(groups) == 1
    legs = [i for i in internal["items"] if i["transfer_group"]]
    assert len(legs) == 2
    assert sum(leg["amount"] for leg in legs) == 0


def test_both_legs_of_a_transfer_are_kept(client):
    """Neither side is deleted — the account balances must keep reconciling."""
    import_fixture(client, "rabobank_current.csv")
    assert client.get("/api/transactions/", params={"page_size": 1}).json()["total"] == 6


def test_transfer_to_an_unimported_account_is_flagged_not_counted(client):
    """ASN's opening row comes from a Rabobank account. Imported on its own,
    the other leg does not exist yet — that must be visible, not silently
    treated as income."""
    import_fixture(client, "asn.csv")
    items = client.get("/api/transactions/", params={"internal": True}).json()["items"]
    assert items == []  # NL00TEST...0001 is not a known account yet

    import_fixture(client, "rabobank_current.csv")
    pending = [
        i for i in client.get("/api/transactions/", params={"internal": True}).json()["items"]
        if i["transfer_pending"]
    ]
    assert len(pending) == 1
    assert pending[0]["amount"] == 200.0


def test_credit_card_settlement_is_netted_but_purchases_are_not(client):
    import_fixture(client, "rabobank_current.csv")
    import_fixture(client, "rabobank_creditcard.csv")

    internal = client.get("/api/transactions/", params={"internal": True}).json()["items"]
    settlement = [i for i in internal if abs(i["amount"]) == 100.0]
    assert len(settlement) == 2, "the €100 collection and the card credit must pair"

    # The genuine refund must NOT be swallowed as a settlement.
    refunds = client.get("/api/transactions/", params={"search": "RETOUR"}).json()["items"]
    assert refunds and all(not r["is_internal"] for r in refunds)


def test_manual_link_and_unlink(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 100}).json()["items"]
    group = next(i["transfer_group"] for i in items if i["transfer_group"])

    assert client.request("DELETE", f"/api/transactions/transfer-group/{group}").json()["unlinked"] == 2
    still_internal = client.get("/api/transactions/", params={"internal": True}).json()["total"]
    assert still_internal == 0


# ─── categorisation ─────────────────────────────────────────────────────────

def test_seeded_rules_categorise_on_import(client):
    import_fixture(client, "rabobank_current.csv")
    categories = {c["name"]: c["transaction_count"] for c in client.get("/api/categories/").json()}
    assert categories.get("Inkomen", 0) >= 1


def test_manual_category_survives_a_rule_reapply(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 100}).json()["items"]
    target = next(i for i in items if not i["is_internal"])
    category_id = client.get("/api/categories/").json()[0]["id"]

    client.patch(f"/api/transactions/{target['id']}/category", json={"category_id": category_id})
    client.post("/api/rules/reapply")

    after = client.get("/api/transactions/", params={"search": target["description"][:20]}).json()
    assert any(i["category_id"] == category_id for i in after["items"])


def test_rule_preview_reports_impact_before_creating(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 100}).json()["items"]
    target = next(i for i in items if i["counter_name"])

    preview = client.get(
        f"/api/transactions/{target['id']}/rule-preview",
        params={"field": "counter_name", "value": target["counter_name"][:10]},
    ).json()
    assert preview["matches"] >= 1


# ─── security guards ────────────────────────────────────────────────────────

@pytest.mark.parametrize("probe", [
    "../secret.db",
    "..%2Fsecret.db",
    "static/../../secret.db",
])
def test_spa_fallback_cannot_serve_files_outside_static(client, probe):
    response = client.get(f"/{probe}")
    assert response.status_code == 200
    assert "SENSITIVE" not in response.text
    assert "spa" in response.text


def test_security_headers_present(client):
    headers = client.get("/api/health").headers
    assert "nosniff" == headers["x-content-type-options"]
    assert "default-src 'self'" in headers["content-security-policy"]
    # Ingress iframes the panel: X-Frame-Options must stay absent.
    assert "x-frame-options" not in headers


def test_export_escapes_formula_injection(client):
    import_fixture(client, "rabobank_current.csv")
    response = client.get("/api/transactions/export")
    assert response.status_code == 200
    for line in response.text.splitlines()[1:]:
        for cell in line.split(";"):
            assert not cell.startswith(("=", "+", "@")), cell


def test_page_size_is_bounded(client):
    assert client.get("/api/transactions/", params={"page_size": 100_000}).status_code == 422


def test_no_openapi_schema_exposed(client):
    """The catch-all serves the SPA shell for unknown paths, so the status is
    200 either way — what matters is that no schema comes back."""
    body = client.get("/openapi.json").text
    assert '"paths"' not in body and "swagger" not in body.lower()
