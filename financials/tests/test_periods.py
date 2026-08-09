"""Month boundaries, especially the salary-aligned ones.

Dutch employers pay on a fixed date but move it off weekends and around the
holidays. A boundary pinned to the calendar day therefore drops the salary into
the previous period in any month that shifts — which in real data is more than
half of them. These tests pin the behaviour that fixes it.
"""

from __future__ import annotations

from datetime import date

from conftest import import_fixture

HEADER = (
    '"IBAN/BBAN","Munt","Datum","Bedrag","Saldo na trn","Tegenrekening IBAN/BBAN",'
    '"Naam tegenpartij","Code","Omschrijving-1"'
)


def salary_rows(entries):
    rows = [HEADER]
    for day, amount, who in entries:
        rows.append(
            f'"NL00TEST0000000001","EUR","{day}","{amount}","5.000,00",'
            f'"NL00TEST0000000008","{who}","sb","Salaris"'
        )
    return ("\n".join(rows) + "\n").encode("utf-8")


def load(client, entries):
    preview = client.post(
        "/api/imports/upload",
        files={"file": ("salary.csv", salary_rows(entries), "text/csv")},
        data={"format_key": "rabobank_current"},
    ).json()
    client.post(f"/api/imports/{preview['batch_id']}/commit", params={"format_key": "rabobank_current"})


def use_salary_mode(client, counterparty="Werkgever"):
    client.put("/api/settings/salary-source", json={"counterparty": counterparty, "min_amount": 500})
    return client.put("/api/settings/period", json={"mode": "salary", "start_day": 25}).json()


# Mirrors the real pattern: paid on the 25th, moved to the Friday before
# whenever that lands in a weekend. Dates sit inside the window the settings
# page shows (the last 14 periods).
SHIFTING = [
    ("2026-01-23", "3.000,00", "Werkgever BV"),   # 25 Jan 2026 was a Sunday
    ("2026-02-25", "3.000,00", "Werkgever BV"),
    ("2026-03-25", "3.000,00", "Werkgever BV"),
    ("2026-04-24", "3.000,00", "Werkgever BV"),   # 25 Apr 2026 was a Saturday
    ("2026-05-22", "3.000,00", "Werkgever BV"),
    ("2026-06-25", "3.000,00", "Werkgever BV"),
]


def test_calendar_mode_is_untouched_by_all_of_this(client):
    import_fixture(client, "rabobank_current.csv")
    settings = client.get("/api/settings/period").json()
    assert settings["mode"] == "calendar"
    assert settings["effective_day"] == 1
    assert settings["shifted_months"] == 0


def test_boundary_follows_the_actual_salary_date(client):
    load(client, SHIFTING)
    settings = use_salary_mode(client)
    boundaries = {(b["year"], b["month"]): b for b in settings["boundaries"]}

    assert boundaries[(2026, 5)]["start"] == "2026-05-22"
    assert boundaries[(2026, 5)]["origin"] == "salarisdatum"
    assert boundaries[(2026, 2)]["start"] == "2026-02-25"


def test_a_shifted_salary_lands_in_its_own_period(client):
    """The bug this exists for: paid on the 23rd with a boundary on the 25th,
    the salary counts towards the previous month."""
    load(client, SHIFTING)

    client.put("/api/settings/salary-source", json={"counterparty": "Werkgever", "min_amount": 500})
    client.put("/api/settings/period", json={"mode": "day", "start_day": 25})
    fixed = client.get("/api/dashboard/summary", params={"year": 2026, "month": 5}).json()
    assert fixed["income"] == 0, "fixed boundary pushes the 22 May salary into April"

    client.put("/api/settings/period", json={"mode": "salary", "start_day": 25})
    dynamic = client.get("/api/dashboard/summary", params={"year": 2026, "month": 5}).json()
    assert dynamic["income"] == 3000.0


def test_cashflow_buckets_follow_the_same_boundaries(client):
    """The SQL bucketing and the Python bounds must agree, or the chart and the
    KPI row disagree with each other."""
    load(client, SHIFTING)
    use_salary_mode(client)

    rows = {r["period"]: r for r in client.get("/api/dashboard/cashflow", params={"months": 8}).json()}
    assert rows["2026-05"]["income"] == 3000.0
    assert rows["2026-04"]["income"] == 3000.0


def test_months_without_a_salary_fall_back_to_the_fixed_day(client):
    load(client, [("2026-01-23", "3.000,00", "Werkgever BV")])
    settings = use_salary_mode(client)
    row = next(b for b in settings["boundaries"] if (b["year"], b["month"]) == (2026, 3))
    assert row["origin"] == "vaste dag"
    assert row["start"] == "2026-03-25"


def test_loan_payouts_do_not_move_the_boundary(client):
    """Matching on the payer, not on the amount: a €10.000 loan on the 2nd must
    not become "the salary date"."""
    load(client, SHIFTING + [("2026-03-02", "10.000,00", "Geldverstrekker NV")])
    settings = use_salary_mode(client)
    row = next(b for b in settings["boundaries"] if (b["year"], b["month"]) == (2026, 3))
    assert row["start"] == "2026-03-25"


def test_manual_override_wins_and_can_be_reset(client):
    load(client, SHIFTING)
    use_salary_mode(client)

    after = client.put("/api/settings/period-override", json={
        "year": 2026, "month": 5, "start_date": "2026-05-20",
    }).json()
    row = next(b for b in after["boundaries"] if (b["year"], b["month"]) == (2026, 5))
    assert row["start"] == "2026-05-20"
    assert row["origin"] == "handmatig"

    restored = client.request("DELETE", "/api/settings/period-override/2026/5").json()
    row = next(b for b in restored["boundaries"] if (b["year"], b["month"]) == (2026, 5))
    assert row["start"] == "2026-05-22"
    assert row["origin"] == "salarisdatum"


def test_override_rejects_a_date_from_another_month(client):
    load(client, SHIFTING)
    use_salary_mode(client)
    response = client.put("/api/settings/period-override", json={
        "year": 2026, "month": 5, "start_date": "2023-05-20",
    })
    assert response.status_code == 422


def test_deleting_a_missing_override_is_a_404(client):
    assert client.request("DELETE", "/api/settings/period-override/2026/7").status_code == 404


def test_employer_is_proposed_from_the_data(client):
    load(client, SHIFTING)
    suggestions = client.get("/api/settings/period").json()["suggestions"]
    assert suggestions[0]["counterparty"] == "Werkgever BV"
    assert suggestions[0]["payments"] == 6


def test_switching_modes_rewrites_nothing(client):
    load(client, SHIFTING)
    before = client.get("/api/transactions/", params={"page_size": 1}).json()["total"]
    use_salary_mode(client)
    client.put("/api/settings/period", json={"mode": "calendar", "start_day": 1})
    assert client.get("/api/transactions/", params={"page_size": 1}).json()["total"] == before


def test_switching_to_salary_mode_adopts_the_obvious_payer(client):
    """Choosing the mode without naming a payer used to silently behave like
    the fixed-day mode. If the data names one candidate, take it."""
    load(client, SHIFTING)
    result = client.put("/api/settings/period", json={"mode": "salary", "start_day": 25}).json()

    assert result["auto_selected_salary_source"] == "Werkgever BV"
    assert result["salary"]["configured"] is True
    assert result["shifted_months"] > 0


def test_a_configured_payer_is_never_overwritten_by_the_switch(client):
    load(client, SHIFTING)
    client.put("/api/settings/salary-source", json={"counterparty": "Iets Anders", "min_amount": 500})
    result = client.put("/api/settings/period", json={"mode": "salary", "start_day": 25}).json()

    assert result["auto_selected_salary_source"] is None
    assert result["salary"]["counterparty"] == "Iets Anders"


def test_the_may_case(client):
    """The reported symptom: salary booked on 22 May, with the usual day the
    25th, must count towards May and not April."""
    load(client, SHIFTING)
    client.put("/api/settings/period", json={"mode": "salary", "start_day": 25})

    april = client.get("/api/dashboard/summary", params={"year": 2026, "month": 4}).json()
    may = client.get("/api/dashboard/summary", params={"year": 2026, "month": 5}).json()

    assert may["start"] == "2026-05-22"
    assert may["income"] == 3000.0
    assert april["income"] == 3000.0, "April keeps its own salary, not two of them"
