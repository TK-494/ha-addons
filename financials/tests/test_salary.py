"""The salary page.

Base pay is what you can build commitments on; travel and working-from-home
allowances are not. The bank shows one lump sum, so the division is recorded —
and since the base almost never changes, last month's division carries over
with the difference landing on the variable part.
"""

from __future__ import annotations

from conftest import import_fixture

HEADER = (
    '"IBAN/BBAN","Munt","Datum","Bedrag","Saldo na trn","Tegenrekening IBAN/BBAN",'
    '"Naam tegenpartij","Code","Omschrijving-1"'
)

PAYMENTS = [
    ("2026-04-24", "3.200,00"),
    ("2026-05-22", "5.400,00"),   # holiday pay month
    ("2026-06-25", "3.250,00"),
    ("2026-07-24", "3.300,00"),
]


def load_salaries(client):
    rows = [HEADER] + [
        f'"NL00TEST0000000001","EUR","{day}","{amount}","9.000,00",'
        f'"NL00TEST0000000008","Werkgever BV","sb","Salaris"'
        for day, amount in PAYMENTS
    ]
    csv = ("\n".join(rows) + "\n").encode("utf-8")
    preview = client.post(
        "/api/imports/upload",
        files={"file": ("salaris.csv", csv, "text/csv")},
        data={"format_key": "rabobank_current"},
    ).json()
    client.post(f"/api/imports/{preview['batch_id']}/commit", params={"format_key": "rabobank_current"})
    client.put("/api/settings/salary-source", json={"counterparty": "Werkgever", "min_amount": 500})


def categories(client):
    base = next(c["id"] for c in client.get("/api/categories/").json() if c["name"] == "Inkomen")
    allowance = client.post("/api/categories/", json={
        "name": "Reiskostenvergoeding", "is_income": True, "variable_income": True,
    }).json()["id"]
    return base, allowance


def test_without_a_payer_the_page_says_so(client):
    import_fixture(client, "rabobank_current.csv")
    result = client.get("/api/salary/").json()
    assert result["configured"] is False
    assert result["payments"] == []


def test_payments_are_listed_newest_first(client):
    load_salaries(client)
    payments = client.get("/api/salary/").json()["payments"]
    assert [p["date"] for p in payments] == ["2026-07-24", "2026-06-25", "2026-05-22", "2026-04-24"]


def test_an_unsplit_payment_counts_wholly_as_fixed(client):
    """What is known, not a claim that there was no allowance in it."""
    load_salaries(client)
    payment = client.get("/api/salary/").json()["payments"][0]
    assert payment["split"] is False
    assert payment["fixed"] == 3300.0
    assert payment["variable"] == 0.0


def test_splitting_reports_fixed_and_variable(client):
    load_salaries(client)
    base, allowance = categories(client)
    payment = client.get("/api/salary/").json()["payments"][0]

    client.put(f"/api/splits/{payment['transaction_id']}", json={"parts": [
        {"category_id": base, "amount": 3100},
        {"category_id": allowance, "amount": 200},
    ]})

    updated = client.get("/api/salary/").json()["payments"][0]
    assert updated["fixed"] == 3100.0
    assert updated["variable"] == 200.0


def test_the_latest_split_becomes_the_template(client):
    load_salaries(client)
    base, allowance = categories(client)
    payment = client.get("/api/salary/").json()["payments"][0]
    client.put(f"/api/splits/{payment['transaction_id']}", json={"parts": [
        {"category_id": base, "amount": 3100},
        {"category_id": allowance, "amount": 200},
    ]})

    template = client.get("/api/salary/").json()["template"]
    assert template["from_date"] == "2026-07-24"
    assert [p["amount"] for p in template["parts"]] == [3100.0, 200.0]


def test_applying_the_template_keeps_fixed_and_moves_the_difference(client):
    """The base is the same every month; the allowance is the part that moves."""
    load_salaries(client)
    base, allowance = categories(client)
    payments = client.get("/api/salary/").json()["payments"]
    client.put(f"/api/splits/{payments[0]['transaction_id']}", json={"parts": [
        {"category_id": base, "amount": 3100},
        {"category_id": allowance, "amount": 200},
    ]})

    # The holiday-pay month is much larger; the surplus must land on the
    # variable part rather than being spread or rejected.
    holiday = next(p for p in payments if p["date"] == "2026-05-22")
    result = client.post("/api/salary/apply-template", json={
        "transaction_id": holiday["transaction_id"],
    }).json()

    assert result["fixed"] == 3100.0
    assert result["variable"] == 2300.0
    assert result["fixed"] + result["variable"] == holiday["amount"]


def test_the_template_refuses_when_fixed_exceeds_the_payment(client):
    load_salaries(client)
    base, allowance = categories(client)
    payments = client.get("/api/salary/").json()["payments"]
    client.put(f"/api/splits/{payments[0]['transaction_id']}", json={"parts": [
        {"category_id": base, "amount": 3299},
        {"category_id": allowance, "amount": 1},
    ]})

    smallest = next(p for p in payments if p["date"] == "2026-04-24")
    response = client.post("/api/salary/apply-template", json={
        "transaction_id": smallest["transaction_id"],
    })
    assert response.status_code == 422
    assert "groter" in response.json()["detail"]


def test_no_template_no_apply(client):
    load_salaries(client)
    payment = client.get("/api/salary/").json()["payments"][0]
    response = client.post("/api/salary/apply-template", json={
        "transaction_id": payment["transaction_id"],
    })
    assert response.status_code == 422


def test_summary_averages_fixed_and_variable(client):
    load_salaries(client)
    base, allowance = categories(client)
    for payment in client.get("/api/salary/").json()["payments"]:
        client.put(f"/api/splits/{payment['transaction_id']}", json={"parts": [
            {"category_id": base, "amount": 3000},
            {"category_id": allowance, "amount": round(payment["amount"] - 3000, 2)},
        ]})

    summary = client.get("/api/salary/").json()["summary"]
    assert summary["split_count"] == 4
    assert summary["unsplit_count"] == 0
    assert summary["average_fixed"] == 3000.0
    assert summary["average_variable"] == round((200 + 2400 + 250 + 300) / 4, 2)
