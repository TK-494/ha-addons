"""Budget tests."""

from __future__ import annotations

from conftest import import_fixture


def category_id(client, name: str) -> int:
    return next(c["id"] for c in client.get("/api/categories/").json() if c["name"] == name)


def test_budget_tracks_spend_in_its_period(client):
    import_fixture(client, "rabobank_current.csv")
    wonen = category_id(client, "Wonen")  # the €1234,56 rent row lands here

    client.post("/api/budgets/", json={
        "category_id": wonen, "year": 2024, "month": 1, "amount": 1300, "rollover": False,
    })
    result = client.get("/api/budgets/", params={"year": 2024, "month": 1}).json()
    row = next(r for r in result["rows"] if r["category_id"] == wonen)

    assert row["planned"] == 1300.0
    assert row["spent"] == 1234.56
    assert row["remaining"] == 65.44
    assert row["percentage"] == 95.0


def test_overspending_is_reported_as_negative_remaining(client):
    import_fixture(client, "rabobank_current.csv")
    wonen = category_id(client, "Wonen")
    client.post("/api/budgets/", json={
        "category_id": wonen, "year": 2024, "month": 1, "amount": 1000, "rollover": False,
    })
    row = next(
        r for r in client.get("/api/budgets/", params={"year": 2024, "month": 1}).json()["rows"]
        if r["category_id"] == wonen
    )
    assert row["remaining"] < 0


def test_internal_transfers_never_consume_a_budget(client):
    """Moving money to your own account is not spending, so it must not eat
    into any category's budget."""
    import_fixture(client, "rabobank_current.csv")
    rows = client.get("/api/budgets/", params={"year": 2024, "month": 1}).json()["rows"]
    assert all(r["spent"] != 50.0 for r in rows)


def test_rollover_carries_the_remainder_forward(client):
    import_fixture(client, "rabobank_current.csv")
    wonen = category_id(client, "Wonen")
    # January: €1300 budget, €1234.56 spent → €65.44 left over.
    client.post("/api/budgets/", json={
        "category_id": wonen, "year": 2024, "month": 1, "amount": 1300, "rollover": True,
    })
    client.post("/api/budgets/", json={
        "category_id": wonen, "year": 2024, "month": 2, "amount": 1300, "rollover": True,
    })

    february = next(
        r for r in client.get("/api/budgets/", params={"year": 2024, "month": 2}).json()["rows"]
        if r["category_id"] == wonen
    )
    assert february["carried_over"] == 65.44
    assert february["available"] == 1365.44


def test_rollover_is_opt_in(client):
    import_fixture(client, "rabobank_current.csv")
    wonen = category_id(client, "Wonen")
    client.post("/api/budgets/", json={
        "category_id": wonen, "year": 2024, "month": 1, "amount": 1300, "rollover": False,
    })
    client.post("/api/budgets/", json={
        "category_id": wonen, "year": 2024, "month": 2, "amount": 1300, "rollover": False,
    })
    february = next(
        r for r in client.get("/api/budgets/", params={"year": 2024, "month": 2}).json()["rows"]
        if r["category_id"] == wonen
    )
    assert february["carried_over"] == 0


def test_upsert_replaces_rather_than_duplicates(client):
    import_fixture(client, "rabobank_current.csv")
    wonen = category_id(client, "Wonen")
    for amount in (100, 200, 300):
        client.post("/api/budgets/", json={
            "category_id": wonen, "year": 2024, "month": 1, "amount": amount, "rollover": False,
        })
    rows = [
        r for r in client.get("/api/budgets/", params={"year": 2024, "month": 1}).json()["rows"]
        if r["category_id"] == wonen
    ]
    assert len(rows) == 1
    assert rows[0]["planned"] == 300.0


def test_copy_previous_month(client):
    import_fixture(client, "rabobank_current.csv")
    wonen = category_id(client, "Wonen")
    client.post("/api/budgets/", json={
        "category_id": wonen, "year": 2024, "month": 1, "amount": 1300, "rollover": False,
    })
    copied = client.post("/api/budgets/copy-previous", params={"year": 2024, "month": 2}).json()
    assert copied["copied"] == 1

    # Running it twice must not duplicate.
    again = client.post("/api/budgets/copy-previous", params={"year": 2024, "month": 2}).json()
    assert again["copied"] == 0


def test_unknown_category_is_rejected(client):
    response = client.post("/api/budgets/", json={
        "category_id": 999999, "year": 2024, "month": 1, "amount": 100, "rollover": False,
    })
    assert response.status_code == 422


def test_negative_budget_is_rejected(client):
    import_fixture(client, "rabobank_current.csv")
    response = client.post("/api/budgets/", json={
        "category_id": category_id(client, "Wonen"),
        "year": 2024, "month": 1, "amount": -50, "rollover": False,
    })
    assert response.status_code == 422


def test_suggestions_do_not_write_anything(client):
    import_fixture(client, "rabobank_current.csv")
    before = client.get("/api/budgets/", params={"year": 2024, "month": 3}).json()
    client.post("/api/budgets/suggest", params={"year": 2024, "month": 3, "months": 6})
    after = client.get("/api/budgets/", params={"year": 2024, "month": 3}).json()
    assert before["total_available"] == after["total_available"] == 0
