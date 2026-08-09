"""Splitting a transaction across categories.

The salary case: one bank line that is base pay plus a travel allowance. The
parts must reconcile exactly, and they — not the lump sum — must drive the
category reporting.
"""

from __future__ import annotations

from conftest import import_fixture


def category_id(client, name):
    return next(c["id"] for c in client.get("/api/categories/").json() if c["name"] == name)


def salary(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 50}).json()["items"]
    return next(i for i in items if i["amount"] == 2000.0)


def test_a_split_must_add_up_exactly(client):
    tx = salary(client)
    inkomen = category_id(client, "Inkomen")
    response = client.put(f"/api/splits/{tx['id']}", json={"parts": [
        {"category_id": inkomen, "amount": 1000},
        {"category_id": inkomen, "amount": 500},
    ]})
    assert response.status_code == 422
    assert "1500" in response.json()["detail"] or "500" in response.json()["detail"]


def test_a_balanced_split_is_accepted(client):
    tx = salary(client)
    inkomen = category_id(client, "Inkomen")
    reis = client.post("/api/categories/", json={
        "name": "Reiskosten", "is_income": True, "variable_income": True,
    }).json()["id"]

    result = client.put(f"/api/splits/{tx['id']}", json={"parts": [
        {"category_id": inkomen, "amount": 1800, "note": "basis"},
        {"category_id": reis, "amount": 200, "note": "reiskosten"},
    ]}).json()
    assert [p["amount"] for p in result["parts"]] == [1800.0, 200.0]
    assert [p["variable_income"] for p in result["parts"]] == [False, True]


def test_parts_must_point_the_same_way_as_the_transaction(client):
    tx = salary(client)
    inkomen = category_id(client, "Inkomen")
    response = client.put(f"/api/splits/{tx['id']}", json={"parts": [
        {"category_id": inkomen, "amount": 2500},
        {"category_id": inkomen, "amount": -500},
    ]})
    assert response.status_code == 422


def test_a_split_needs_at_least_two_parts(client):
    tx = salary(client)
    response = client.put(f"/api/splits/{tx['id']}", json={"parts": [
        {"category_id": category_id(client, "Inkomen"), "amount": 2000},
    ]})
    assert response.status_code == 422


def test_category_totals_use_the_parts_not_the_lump_sum(client):
    tx = salary(client)
    inkomen = category_id(client, "Inkomen")
    reis = client.post("/api/categories/", json={
        "name": "Reiskosten", "is_income": True, "variable_income": True,
    }).json()["id"]
    client.put(f"/api/splits/{tx['id']}", json={"parts": [
        {"category_id": inkomen, "amount": 1800},
        {"category_id": reis, "amount": 200},
    ]})

    rows = {r["name"]: r["amount"] for r in client.get(
        "/api/dashboard/by-category", params={"year": 2024, "month": 1, "direction": "in"}
    ).json()}
    assert rows.get("Inkomen") == 1800.0
    assert rows.get("Reiskosten") == 200.0


def test_income_is_reported_fixed_versus_variable(client):
    tx = salary(client)
    inkomen = category_id(client, "Inkomen")
    reis = client.post("/api/categories/", json={
        "name": "Reiskosten", "is_income": True, "variable_income": True,
    }).json()["id"]
    client.put(f"/api/splits/{tx['id']}", json={"parts": [
        {"category_id": inkomen, "amount": 1800},
        {"category_id": reis, "amount": 200},
    ]})

    available = client.get("/api/dashboard/available", params={"year": 2024, "month": 1}).json()
    assert available["income"]["fixed"] == 1800.0
    assert available["income"]["variable"] == 200.0
    assert available["income"]["total"] == 2000.0


def test_clearing_a_split_restores_the_whole_transaction(client):
    tx = salary(client)
    inkomen = category_id(client, "Inkomen")
    client.put(f"/api/splits/{tx['id']}", json={"parts": [
        {"category_id": inkomen, "amount": 1500},
        {"category_id": inkomen, "amount": 500},
    ]})
    client.request("DELETE", f"/api/splits/{tx['id']}")

    assert client.get(f"/api/splits/{tx['id']}").json()["parts"] == []
    rows = {r["name"]: r["amount"] for r in client.get(
        "/api/dashboard/by-category", params={"year": 2024, "month": 1, "direction": "in"}
    ).json()}
    assert sum(rows.values()) == 2000.0


def test_deleting_the_transaction_takes_its_split_with_it(client):
    tx = salary(client)
    inkomen = category_id(client, "Inkomen")
    client.put(f"/api/splits/{tx['id']}", json={"parts": [
        {"category_id": inkomen, "amount": 1500},
        {"category_id": inkomen, "amount": 500},
    ]})
    batch = client.get("/api/imports/").json()[0]
    client.request("DELETE", f"/api/imports/{batch['id']}", params={"delete_transactions": True})
    assert client.get(f"/api/splits/{tx['id']}").status_code == 404
