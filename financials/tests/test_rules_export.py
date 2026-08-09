"""Rule provenance, export, import and conflict detection."""

from __future__ import annotations

from conftest import import_fixture


def category_id(client, name):
    return next(c["id"] for c in client.get("/api/categories/").json() if c["name"] == name)


# ─── provenance ─────────────────────────────────────────────────────────────

def test_seeded_rules_record_their_batch(client):
    rules = client.get("/api/rules/").json()
    assert rules
    assert all(r["origin"] == "seed" for r in rules)
    assert {r["seed_batch"] for r in rules} == {1, 2}


def test_a_hand_written_rule_is_marked_manual(client):
    import_fixture(client, "rabobank_current.csv")
    client.post("/api/rules/", json={
        "category_id": category_id(client, "Wonen"), "value": "handmatig-test", "priority": 1,
    })
    rule = next(r for r in client.get("/api/rules/").json() if r["value"] == "handmatig-test")
    assert rule["origin"] == "manual"
    assert rule["seed_batch"] is None


def test_a_rule_made_from_a_transaction_records_that(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 50}).json()["items"]
    target = next(i for i in items if i["counter_name"])

    client.post(f"/api/transactions/{target['id']}/rule", json={
        "category_id": category_id(client, "Wonen"),
        "field": "counter_name",
        "value": target["counter_name"][:10],
        "apply_to_existing": False,
    })
    rule = next(r for r in client.get("/api/rules/").json() if r["origin"] == "transaction")
    assert rule["value"] == target["counter_name"][:10]


# ─── the trailing space ─────────────────────────────────────────────────────

def test_rule_values_are_stored_verbatim(client):
    """A trailing space is part of the pattern: "ns " must not silently become
    "ns", which would match jetbrains, transip and half the ledger."""
    import_fixture(client, "rabobank_current.csv")
    client.post("/api/rules/", json={
        "category_id": category_id(client, "Wonen"), "value": "xyz ", "priority": 1,
    })
    assert any(r["value"] == "xyz " for r in client.get("/api/rules/").json())


def test_seed_keeps_its_spaced_keywords(client):
    values = {r["value"] for r in client.get("/api/rules/").json()}
    assert "ns " in values
    assert "ns" not in values


# ─── export ─────────────────────────────────────────────────────────────────

def test_export_carries_categories_by_name_and_provenance(client):
    export = client.get("/api/rules/export").json()
    assert export["format"] == "financials-rules"
    assert export["categories"]
    rule = export["rules"][0]
    assert set(rule) >= {"category", "field", "operator", "value", "priority", "origin", "seed_batch"}
    assert isinstance(rule["category"], str)


def test_export_reports_how_many_transactions_each_rule_owns(client):
    import_fixture(client, "rabobank_current.csv")
    export = client.get("/api/rules/export").json()
    assert any((r["matches"] or 0) > 0 for r in export["rules"])


# ─── import ─────────────────────────────────────────────────────────────────

def test_reimporting_our_own_export_changes_nothing(client):
    """The round trip has to be a no-op, or the file is not a safe backup."""
    export = client.get("/api/rules/export").json()
    payload = {"rules": [
        {"category": r["category"], "value": r["value"], "field": r["field"],
         "operator": r["operator"], "priority": r["priority"]}
        for r in export["rules"]
    ]}
    result = client.post("/api/rules/import", json=payload).json()
    assert result["added"] == 0
    assert result["skipped"] == len(payload["rules"])


def test_import_dry_run_writes_nothing(client):
    before = len(client.get("/api/rules/").json())
    result = client.post("/api/rules/import", params={"dry_run": True}, json={
        "rules": [{"category": "Nieuwe Categorie", "value": "iets-nieuws", "priority": 100}],
    }).json()
    assert result["dry_run"] is True
    assert result["added"] == 1
    assert len(client.get("/api/rules/").json()) == before


def test_import_creates_missing_categories_when_allowed(client):
    result = client.post("/api/rules/import", json={
        "rules": [{"category": "Verbouwing", "value": "bouwmarkt-x", "priority": 100}],
    }).json()
    assert result["created_categories"] == ["Verbouwing"]
    assert any(c["name"] == "Verbouwing" for c in client.get("/api/categories/").json())


def test_import_can_refuse_to_invent_categories(client):
    result = client.post("/api/rules/import", json={
        "rules": [{"category": "Bestaat Niet", "value": "iets", "priority": 100}],
        "create_missing_categories": False,
    }).json()
    assert result["added"] == 0
    assert result["skipped"] == 1


def test_imported_rules_are_marked_as_imported(client):
    client.post("/api/rules/import", json={
        "rules": [{"category": "Wonen", "value": "geimporteerd-x", "priority": 100}],
    })
    rule = next(r for r in client.get("/api/rules/").json() if r["value"] == "geimporteerd-x")
    assert rule["origin"] == "import"


# ─── conflicts ──────────────────────────────────────────────────────────────

def test_shipped_rules_have_no_duplicate_patterns(client):
    assert client.get("/api/rules/conflicts").json()["duplicates"] == []


def test_a_trailing_space_is_not_reported_as_a_conflict(client):
    """"avia " does not occur inside "transavia"; reporting it would drown the
    real conflicts in noise."""
    shadowed = client.get("/api/rules/conflicts").json()["shadowed"]
    pairs = {(s["value"], s["shadowed_by"]) for s in shadowed}
    assert ("transavia", "avia ") not in pairs
    assert not any(by == "ns " for _, by in pairs)


def test_a_real_shadow_is_reported(client):
    """A broader earlier pattern that swallows a later one must surface."""
    import_fixture(client, "rabobank_current.csv")
    wonen = category_id(client, "Wonen")
    energie = category_id(client, "Energie")
    client.post("/api/rules/", json={"category_id": wonen, "value": "zonnepaneel", "priority": 2})
    client.post("/api/rules/", json={"category_id": energie, "value": "zonnepaneel-actie", "priority": 3})

    shadowed = client.get("/api/rules/conflicts").json()["shadowed"]
    assert any(s["value"] == "zonnepaneel-actie" and s["shadowed_by"] == "zonnepaneel" for s in shadowed)


# ─── batches ────────────────────────────────────────────────────────────────

def test_batch_two_never_outranks_batch_one(client):
    rules = client.get("/api/rules/").json()
    batch_one = max(r["priority"] for r in rules if r["seed_batch"] == 1)
    batch_two = min(r["priority"] for r in rules if r["seed_batch"] == 2)
    assert batch_two > batch_one, "a new keyword may only claim what nothing already claims"


def test_reseeding_is_idempotent(client):
    before = len(client.get("/api/rules/").json())
    client.post("/api/rules/reseed")
    assert len(client.get("/api/rules/").json()) == before


def test_a_keyword_already_present_is_not_added_twice(client):
    """Batch 2 reuses categories from batch 1; it must not re-add their
    keywords under a second rule."""
    values = [r["value"] for r in client.get("/api/rules/").json()]
    assert len(values) == len(set(values))


# ─── editing a rule ─────────────────────────────────────────────────────────

def test_every_part_of_a_rule_can_be_changed(client):
    import_fixture(client, "rabobank_current.csv")
    wonen = category_id(client, "Wonen")
    energie = category_id(client, "Energie")
    rule_id = client.post("/api/rules/", json={
        "category_id": wonen, "value": "oud", "field": "any",
        "operator": "contains", "priority": 100,
    }).json()["id"]

    client.put(f"/api/rules/{rule_id}", json={
        "category_id": energie, "value": "nieuw", "field": "counter_name",
        "operator": "startswith", "priority": 7, "active": False,
        "amount_min": 5, "amount_max": 500,
    })

    rule = next(r for r in client.get("/api/rules/").json() if r["id"] == rule_id)
    assert rule["category_name"] == "Energie"
    assert rule["value"] == "nieuw"
    assert rule["field"] == "counter_name"
    assert rule["operator"] == "startswith"
    assert rule["priority"] == 7
    assert rule["active"] is False
    assert rule["amount_min"] == 5 and rule["amount_max"] == 500


def test_priority_change_reorders_which_rule_wins(client):
    """Two rules matching the same row: the lower priority number decides."""
    import_fixture(client, "rabobank_current.csv")
    wonen = category_id(client, "Wonen")
    energie = category_id(client, "Energie")

    items = client.get("/api/transactions/", params={"page_size": 50}).json()["items"]
    target = next(i for i in items if "Supermarkt" in (i["counter_name"] or ""))

    first = client.post("/api/rules/", json={
        "category_id": wonen, "value": "Supermarkt", "priority": 5,
    }).json()["id"]
    client.post("/api/rules/", json={
        "category_id": energie, "value": "Supermarkt Voorbeeld", "priority": 6,
    })
    client.post("/api/rules/reapply", params={"include_locked": True})
    assert next(i for i in client.get("/api/transactions/", params={"page_size": 50}).json()["items"]
                if i["id"] == target["id"])["category_name"] == "Wonen"

    # Push the broad rule behind the specific one.
    rule = next(r for r in client.get("/api/rules/").json() if r["id"] == first)
    client.put(f"/api/rules/{first}", json={**{
        k: rule[k] for k in ("category_id", "value", "field", "operator", "active")
    }, "priority": 9})
    client.post("/api/rules/reapply", params={"include_locked": True})

    assert next(i for i in client.get("/api/transactions/", params={"page_size": 50}).json()["items"]
                if i["id"] == target["id"])["category_name"] == "Energie"


def test_preview_counts_before_you_save(client):
    import_fixture(client, "rabobank_current.csv")
    preview = client.get("/api/rules/preview", params={
        "field": "counter_name", "operator": "contains", "value": "Voorbeeld",
    }).json()
    assert preview["matches"] >= 1
    assert len(preview["samples"]) >= 1
    assert "would_change" in preview


def test_preview_respects_the_trailing_space(client):
    import_fixture(client, "rabobank_current.csv")
    wide = client.get("/api/rules/preview", params={"value": "ver"}).json()["matches"]
    narrow = client.get("/api/rules/preview", params={"value": "verhuurder "}).json()["matches"]
    assert narrow < wide


def test_preview_separates_locked_transactions(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 50}).json()["items"]
    target = next(i for i in items if "Supermarkt" in (i["counter_name"] or ""))
    client.patch(f"/api/transactions/{target['id']}/category",
                 json={"category_id": category_id(client, "Wonen")})

    preview = client.get("/api/rules/preview", params={
        "field": "counter_name", "value": "Supermarkt",
    }).json()
    assert preview["locked"] >= 1
    assert preview["would_change"] <= preview["matches"] - preview["locked"]
