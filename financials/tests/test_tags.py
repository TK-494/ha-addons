"""Label tests.

The whole point of labels is that they add a dimension *without* disturbing the
accounting, so most of these assert that some total did **not** change.
"""

from __future__ import annotations

from conftest import import_fixture


def make_tag(client, name="Vakantie 2019", color="#0ea5e9"):
    return client.post("/api/tags/", json={"name": name, "color": color}).json()["id"]


def all_transactions(client):
    return client.get("/api/transactions/", params={"page_size": 100}).json()["items"]


# ─── the core promise: labels never move the money ──────────────────────────

def test_labelling_does_not_change_any_total(client):
    import_fixture(client, "rabobank_current.csv")
    before = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()

    tag_id = make_tag(client)
    ids = [t["id"] for t in all_transactions(client)]
    client.post("/api/tags/bulk", json={"transaction_ids": ids, "tag_id": tag_id, "action": "add"})

    after = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()
    assert after["income"] == before["income"]
    assert after["expenses"] == before["expenses"]
    assert after["net"] == before["net"]


def test_a_transaction_keeps_exactly_one_category_alongside_its_labels(client):
    """The fuel-on-holiday case: one category, several labels, full amount in
    both views — no double counting because only the category is summed."""
    import_fixture(client, "rabobank_current.csv")
    target = next(t for t in all_transactions(client) if t["amount"] < 0 and not t["is_internal"])
    category_id = client.get("/api/categories/").json()[0]["id"]
    client.patch(f"/api/transactions/{target['id']}/category", json={"category_id": category_id})

    holiday = make_tag(client, "Vakantie 2019")
    project = make_tag(client, "Project X")
    client.put(f"/api/tags/transaction/{target['id']}", json={"tag_ids": [holiday, project]})

    row = next(t for t in all_transactions(client) if t["id"] == target["id"])
    assert row["category_id"] == category_id
    assert {t["name"] for t in row["tags"]} == {"Vakantie 2019", "Project X"}


def test_category_totals_still_sum_to_the_spend_after_labelling(client):
    import_fixture(client, "rabobank_current.csv")
    tag_id = make_tag(client)
    ids = [t["id"] for t in all_transactions(client)]
    client.post("/api/tags/bulk", json={"transaction_ids": ids, "tag_id": tag_id, "action": "add"})

    rows = client.get("/api/dashboard/by-category", params={"year": 2024, "month": 1}).json()
    summary = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()
    assert round(sum(r["amount"] for r in rows), 2) == round(abs(summary["expenses"]), 2)


# ─── assignment ─────────────────────────────────────────────────────────────

def test_bulk_add_is_idempotent(client):
    import_fixture(client, "rabobank_current.csv")
    tag_id = make_tag(client)
    ids = [t["id"] for t in all_transactions(client)]

    first = client.post("/api/tags/bulk", json={"transaction_ids": ids, "tag_id": tag_id, "action": "add"}).json()
    second = client.post("/api/tags/bulk", json={"transaction_ids": ids, "tag_id": tag_id, "action": "add"}).json()
    assert first["changed"] == len(ids)
    assert second["changed"] == 0


def test_bulk_remove(client):
    import_fixture(client, "rabobank_current.csv")
    tag_id = make_tag(client)
    ids = [t["id"] for t in all_transactions(client)]
    client.post("/api/tags/bulk", json={"transaction_ids": ids, "tag_id": tag_id, "action": "add"})

    removed = client.post("/api/tags/bulk", json={"transaction_ids": ids, "tag_id": tag_id, "action": "remove"}).json()
    assert removed["changed"] == len(ids)
    assert client.get("/api/tags/").json()[0]["transactions"] == 0


def test_setting_tags_replaces_the_whole_set(client):
    import_fixture(client, "rabobank_current.csv")
    target = all_transactions(client)[0]
    a, b = make_tag(client, "A"), make_tag(client, "B")

    client.put(f"/api/tags/transaction/{target['id']}", json={"tag_ids": [a, b]})
    client.put(f"/api/tags/transaction/{target['id']}", json={"tag_ids": [b]})

    row = next(t for t in all_transactions(client) if t["id"] == target["id"])
    assert [t["name"] for t in row["tags"]] == ["B"]


def test_unknown_tag_is_rejected(client):
    import_fixture(client, "rabobank_current.csv")
    target = all_transactions(client)[0]
    assert client.put(f"/api/tags/transaction/{target['id']}", json={"tag_ids": [999999]}).status_code == 422


def test_duplicate_tag_name_is_rejected_case_insensitively(client):
    make_tag(client, "Vakantie")
    assert client.post("/api/tags/", json={"name": "vakantie"}).status_code == 409


# ─── filtering and reporting ────────────────────────────────────────────────

def test_filter_transactions_by_label(client):
    import_fixture(client, "rabobank_current.csv")
    tag_id = make_tag(client)
    target = all_transactions(client)[0]
    client.put(f"/api/tags/transaction/{target['id']}", json={"tag_ids": [tag_id]})

    filtered = client.get("/api/transactions/", params={"tag_id": tag_id}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == target["id"]


def test_breakdown_splits_a_label_across_categories(client):
    """“What did this holiday cost, and on what?” — the reason labels exist."""
    import_fixture(client, "rabobank_current.csv")
    tag_id = make_tag(client)
    spend = [t for t in all_transactions(client) if t["amount"] < 0 and not t["is_internal"]]
    client.post("/api/tags/bulk", json={
        "transaction_ids": [t["id"] for t in spend], "tag_id": tag_id, "action": "add",
    })

    result = client.get(f"/api/tags/{tag_id}/breakdown").json()
    assert result["tag"]["name"] == "Vakantie 2019"
    assert result["spent"] == round(sum(abs(t["amount"]) for t in spend), 2)
    assert sum(c["transactions"] for c in result["categories"]) == len(spend)


def test_deleting_a_label_keeps_the_transactions(client):
    import_fixture(client, "rabobank_current.csv")
    tag_id = make_tag(client)
    ids = [t["id"] for t in all_transactions(client)]
    client.post("/api/tags/bulk", json={"transaction_ids": ids, "tag_id": tag_id, "action": "add"})

    result = client.request("DELETE", f"/api/tags/{tag_id}").json()
    assert result["untagged_transactions"] == len(ids)
    assert client.get("/api/transactions/", params={"page_size": 1}).json()["total"] == len(ids)


def test_deleting_a_transaction_removes_its_label_link(client):
    """The association row must not outlive its transaction."""
    import_fixture(client, "rabobank_current.csv")
    tag_id = make_tag(client)
    ids = [t["id"] for t in all_transactions(client)]
    client.post("/api/tags/bulk", json={"transaction_ids": ids, "tag_id": tag_id, "action": "add"})

    batch = client.get("/api/imports/").json()[0]
    client.request("DELETE", f"/api/imports/{batch['id']}", params={"delete_transactions": True})

    assert client.get("/api/tags/").json()[0]["transactions"] == 0


def test_labels_appear_in_the_export(client):
    import_fixture(client, "rabobank_current.csv")
    tag_id = make_tag(client, "Vakantie 2019")
    target = all_transactions(client)[0]
    client.put(f"/api/tags/transaction/{target['id']}", json={"tag_ids": [tag_id]})

    export = client.get("/api/transactions/export").text
    assert "Labels" in export.splitlines()[0]
    assert "Vakantie 2019" in export
