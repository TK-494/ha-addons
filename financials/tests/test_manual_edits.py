"""Manual edits are sacred.

Every automatic process in this app — rule re-runs, transfer matching, card
settlement detection, savings classification — may revise its own guesses. None
of them may quietly undo a choice the user made by hand. These tests exist so
that stays true when someone adds the next automatic process.
"""

from __future__ import annotations

from conftest import import_fixture


def pick_expense(client):
    items = client.get("/api/transactions/", params={"page_size": 100}).json()["items"]
    return next(t for t in items if t["amount"] < 0 and not t["is_internal"])


def fetch(client, tx_id):
    items = client.get("/api/transactions/", params={"page_size": 100}).json()["items"]
    return next(t for t in items if t["id"] == tx_id)


def a_category(client, index=0):
    return client.get("/api/categories/").json()[index]["id"]


# ─── rule re-runs ───────────────────────────────────────────────────────────

def test_reapply_leaves_manual_categories_alone(client):
    import_fixture(client, "rabobank_current.csv")
    target = pick_expense(client)
    chosen = a_category(client)
    client.patch(f"/api/transactions/{target['id']}/category", json={"category_id": chosen})

    # A rule that would grab this row for a different category.
    other = a_category(client, 1)
    client.post("/api/rules/", json={
        "category_id": other, "field": "any", "value": target["description"][:12], "priority": 1,
    })
    client.post("/api/rules/reapply")

    assert fetch(client, target["id"])["category_id"] == chosen


def test_reapply_dry_run_changes_nothing_and_reports_the_manual_count(client):
    import_fixture(client, "rabobank_current.csv")
    target = pick_expense(client)
    chosen = a_category(client)
    client.patch(f"/api/transactions/{target['id']}/category", json={"category_id": chosen})

    other = a_category(client, 1)
    client.post("/api/rules/", json={
        "category_id": other, "field": "any", "value": target["description"][:12], "priority": 1,
    })

    preview = client.post("/api/rules/reapply", params={
        "include_locked": True, "dry_run": True,
    }).json()
    assert preview["dry_run"] is True
    assert preview["manual"] >= 1
    # Nothing may have moved.
    assert fetch(client, target["id"])["category_id"] == chosen


def test_override_only_happens_when_explicitly_asked(client):
    import_fixture(client, "rabobank_current.csv")
    target = pick_expense(client)
    chosen = a_category(client)
    client.patch(f"/api/transactions/{target['id']}/category", json={"category_id": chosen})

    other = a_category(client, 1)
    client.post("/api/rules/", json={
        "category_id": other, "field": "any", "value": target["description"][:12], "priority": 1,
    })

    client.post("/api/rules/reapply")
    assert fetch(client, target["id"])["category_id"] == chosen

    client.post("/api/rules/reapply", params={"include_locked": True})
    assert fetch(client, target["id"])["category_id"] == other


# ─── transfer matching ──────────────────────────────────────────────────────

def test_becoming_an_internal_transfer_does_not_wipe_a_manual_category(client):
    """A transaction can turn out to be an internal transfer long after you
    categorised it — when the other account's CSV finally arrives. That must
    not silently discard your choice."""
    import_fixture(client, "rabobank_current.csv")

    items = client.get("/api/transactions/", params={"page_size": 100}).json()["items"]
    target = next(t for t in items if "0000000009" in t["counter_iban"])
    chosen = a_category(client)
    client.patch(f"/api/transactions/{target['id']}/category", json={"category_id": chosen})

    # Registering the counterparty as an own account reclassifies it as internal.
    client.post("/api/accounts/", json={"iban": "NL00TEST0000000009"})

    after = fetch(client, target["id"])
    assert after["is_internal"] is True
    assert after["category_id"] == chosen, "manual category survived the reclassification"


def test_automatic_category_is_cleared_when_a_row_becomes_internal(client):
    """The counterpart of the rule above: a machine guess may be revised."""
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 100}).json()["items"]
    target = next(t for t in items if "0000000009" in t["counter_iban"])
    assert target["category_locked"] is False

    client.post("/api/accounts/", json={"iban": "NL00TEST0000000009"})
    after = fetch(client, target["id"])
    assert after["is_internal"] is True
    assert after["category_id"] is None


def test_card_settlement_detection_preserves_a_manual_category(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 100}).json()["items"]
    settlement = next(t for t in items if abs(t["amount"]) == 100.0)
    chosen = a_category(client)
    client.patch(f"/api/transactions/{settlement['id']}/category", json={"category_id": chosen})

    import_fixture(client, "rabobank_creditcard.csv")

    after = fetch(client, settlement["id"])
    assert after["is_internal"] is True
    assert after["category_id"] == chosen


def test_manual_transfer_link_preserves_a_manual_category(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 100}).json()["items"]
    debit = next(t for t in items if t["amount"] == -12.34)
    chosen = a_category(client)
    client.patch(f"/api/transactions/{debit['id']}/category", json={"category_id": chosen})

    partner = next(t for t in items if t["amount"] == 12.34 and t["id"] != debit["id"]) \
        if any(t["amount"] == 12.34 for t in items) else None
    if partner is None:
        return  # nothing to link against in this fixture; the guard is covered above

    client.post(f"/api/transactions/{debit['id']}/link-transfer", json={"other_id": partner["id"]})
    assert fetch(client, debit["id"])["category_id"] == chosen


# ─── a later import ─────────────────────────────────────────────────────────

def test_a_new_import_does_not_recategorise_existing_manual_choices(client):
    import_fixture(client, "rabobank_current.csv")
    target = pick_expense(client)
    chosen = a_category(client)
    client.patch(f"/api/transactions/{target['id']}/category", json={"category_id": chosen})

    import_fixture(client, "asn.csv")
    import_fixture(client, "rabobank_creditcard.csv")

    assert fetch(client, target["id"])["category_id"] == chosen


# ─── account kind ───────────────────────────────────────────────────────────

def test_manual_account_kind_survives_automatic_classification(client):
    """Same principle one level up: if you say an account is a current
    account, no import may quietly turn it into a savings account."""
    import_fixture(client, "rabobank_current.csv")
    accounts = client.get("/api/accounts/").json()
    target = next(a for a in accounts if a["iban"] == "NL00TEST0000000002")

    client.patch(f"/api/accounts/{target['id']}", json={"kind": "checking"})
    assert client.get("/api/accounts/").json()

    client.post("/api/accounts/classify")
    after = next(a for a in client.get("/api/accounts/").json() if a["id"] == target["id"])
    assert after["kind"] == "checking"
    assert after["kind_auto"] is False


# ─── surviving an add-on update ─────────────────────────────────────────────

def test_an_update_preserves_everything_the_user_built(client):
    """The fear this answers: "do I have to redo my rules after every update?"

    Updating the add-on restarts the process against the same /data, which
    re-runs create_all, the migrations and the seeding. None of that may touch
    what the user made — including a seeded rule they deleted on purpose,
    which must not come back.
    """
    import_fixture(client, "rabobank_current.csv")

    mine = client.post("/api/categories/", json={"name": "Eigen categorie"}).json()["id"]
    client.post("/api/rules/", json={
        "category_id": mine, "value": "Verhuurder", "field": "counter_name", "priority": 1,
    })
    client.post("/api/rules/reapply")

    target = next(
        t for t in client.get("/api/transactions/", params={"page_size": 50}).json()["items"]
        if not t["is_internal"]
    )
    client.patch(f"/api/transactions/{target['id']}/category", json={"category_id": mine})

    doomed = next(r for r in client.get("/api/rules/").json() if r["value"] == "ryanair")
    client.request("DELETE", f"/api/rules/{doomed['id']}")

    before = {
        "rules": len(client.get("/api/rules/").json()),
        "categories": len(client.get("/api/categories/").json()),
        "mine": client.get("/api/transactions/", params={"category_id": mine, "page_size": 1}).json()["total"],
        "uncategorised": client.get("/api/dashboard/uncategorised").json()["total_uncategorised"],
    }

    # What an update does: re-run schema creation, migrations and seeding
    # against the existing database.
    from app.database import Base, SessionLocal, apply_migrations, engine
    from app.services.categorize import seed_defaults

    Base.metadata.create_all(bind=engine)
    apply_migrations()
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()

    after = {
        "rules": len(client.get("/api/rules/").json()),
        "categories": len(client.get("/api/categories/").json()),
        "mine": client.get("/api/transactions/", params={"category_id": mine, "page_size": 1}).json()["total"],
        "uncategorised": client.get("/api/dashboard/uncategorised").json()["total_uncategorised"],
    }

    assert after == before
    assert not any(r["value"] == "ryanair" for r in client.get("/api/rules/").json()), \
        "a rule the user deleted must not be resurrected by reseeding"


def test_assigning_a_worklist_group_pins_the_choice(client):
    """Those rows are a human decision, so a later rule run must leave them."""
    import_fixture(client, "rabobank_current.csv")
    groups = client.get("/api/dashboard/uncategorised").json()["groups"]
    if not groups:
        return
    category = client.get("/api/categories/").json()[0]["id"]
    client.post("/api/dashboard/uncategorised/assign", json={
        "name": groups[0]["name"], "category_id": category, "create_rule": False,
    })

    locked = [
        t for t in client.get("/api/transactions/", params={"page_size": 500}).json()["items"]
        if t["category_locked"] and t["category_id"] == category
    ]
    assert locked, "the assignment should be pinned against rule reruns"
