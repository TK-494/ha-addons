"""A range of periods is the unit every dashboard page works in.

One month is a range of length one. These tests pin the resolver's
precedence, the "previous" comparison window, and that summing a range
equals summing its months — the invariant a picker can rely on.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date

import pytest
from conftest import import_fixture

TODAY = date(2026, 9, 20)


@pytest.fixture()
def periods():
    """The module reads its database location at import, so point it at a
    throwaway directory before touching it — the pure functions never open it."""
    os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="financials-test-"))
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.environ['DATA_DIR']}/unused.db")
    from app.services import periods as module
    return module


@pytest.fixture()
def rng(periods):
    config = periods.PeriodConfig()
    return lambda **kwargs: periods.resolve_range(config, today=TODAY, **kwargs)


# ─── resolver precedence ─────────────────────────────────────────────────────

def test_nothing_means_the_current_period(rng):
    r = rng()
    assert (r.first, r.last) == ((2026, 9), (2026, 9))
    assert r.single and r.count == 1


def test_months_counts_back_from_now(rng):
    r = rng(months=3)
    assert (r.first, r.last) == ((2026, 7), (2026, 9))
    assert r.count == 3


def test_year_and_month_name_one_period(rng):
    r = rng(year=2025, month=3)
    assert (r.first, r.last) == ((2025, 3), (2025, 3))


def test_year_month_plus_months_ends_there(rng):
    r = rng(year=2025, month=3, months=6)
    assert (r.first, r.last) == ((2024, 10), (2025, 3))


def test_from_and_to_win_over_everything_else(rng):
    r = rng(from_label="2025-01", to_label="2025-03", year=2020, month=1, months=12)
    assert (r.first, r.last) == ((2025, 1), (2025, 3))
    assert r.labels == [(2025, 1), (2025, 2), (2025, 3)]


def test_from_alone_is_one_period_and_to_alone_is_one_period(rng):
    assert rng(from_label="2025-05").labels == [(2025, 5)]
    assert rng(to_label="2025-05").labels == [(2025, 5)]


def test_to_with_months_is_a_window_ending_there(rng):
    assert rng(to_label="2025-05", months=3).labels == [(2025, 3), (2025, 4), (2025, 5)]


def test_reversed_bounds_are_swapped_not_rejected(rng):
    r = rng(from_label="2025-06", to_label="2025-02")
    assert (r.first, r.last) == ((2025, 2), (2025, 6))


@pytest.mark.parametrize("bad", ["2025", "2025-13", "maart", "2025-00", ""])
def test_malformed_labels_raise(periods, bad):
    with pytest.raises(ValueError):
        periods.parse_label(bad)


# ─── the comparison window ───────────────────────────────────────────────────

def test_previous_of_a_quarter_is_the_quarter_before(periods, rng):
    r = rng(from_label="2025-04", to_label="2025-06")
    p = r.previous(periods.PeriodConfig())
    assert (p.first, p.last) == ((2025, 1), (2025, 3))
    assert p.end == r.start, "the two windows meet exactly"


def test_bounds_respect_the_month_boundary_setting(periods):
    config = periods.PeriodConfig(mode=periods.MODE_DAY, start_day=25)
    r = periods.resolve_range(config, from_label="2025-01", to_label="2025-02", today=TODAY)
    assert r.start == date(2025, 1, 25)
    assert r.end == date(2025, 3, 25)


def test_label_reads_as_dutch(rng):
    assert rng(from_label="2025-01", to_label="2025-03").to_dict()["label"] == "januari 2025 t/m maart 2025"
    assert rng(year=2025, month=1).to_dict()["label"] == "januari 2025"


# ─── through the API ─────────────────────────────────────────────────────────

def test_periods_endpoint_runs_from_now_back_to_the_oldest_transaction(client):
    import_fixture(client, "rabobank_current.csv")
    data = client.get("/api/dashboard/periods").json()
    assert data["earliest"] == "2024-01"
    assert data["options"][0]["value"] == data["current"], "newest first"
    assert data["options"][-1]["value"] == "2024-01"
    assert data["options"][-1]["label"] == "januari 2024"
    assert data["options"][-1]["start"] == "2024-01-01"
    assert data["options"][-1]["end"] == "2024-02-01"
    assert data["boundary"] == {"mode": "calendar", "day": 1}


def test_periods_carry_their_real_dates_when_the_month_starts_on_a_salary_day(client):
    """The case that looked like a missing month: with the boundary on the
    25th, the running period is still called after the month it started in,
    and its dates are what tell you September is in there."""
    import_fixture(client, "rabobank_current.csv")
    client.put("/api/settings/period", json={"mode": "day", "start_day": 25})
    data = client.get("/api/dashboard/periods").json()
    assert data["boundary"]["day"] == 25
    first = data["options"][0]
    assert first["start"].endswith("-25")
    assert first["end"].endswith("-25")


def test_summary_over_a_range_equals_the_sum_of_its_months(client):
    import_fixture(client, "rabobank_current.csv")
    jan = client.get("/api/dashboard/summary", params={"from": "2024-01", "to": "2024-01"}).json()
    feb = client.get("/api/dashboard/summary", params={"from": "2024-02", "to": "2024-02"}).json()
    both = client.get("/api/dashboard/summary", params={"from": "2024-01", "to": "2024-02"}).json()

    assert both["range"]["periods"] == 2
    assert both["range"]["single"] is False
    assert both["transactions"] == jan["transactions"] + feb["transactions"]
    assert both["expenses"] == pytest.approx(jan["expenses"] + feb["expenses"])
    assert both["income"] == pytest.approx(jan["income"] + feb["income"])


def test_summary_previous_window_is_equally_long(client):
    import_fixture(client, "rabobank_current.csv")
    both = client.get("/api/dashboard/summary", params={"from": "2024-01", "to": "2024-02"}).json()
    assert both["previous"]["start"] == "2023-11-01"
    assert both["previous"]["end"] == "2024-01-01"


def test_summary_without_range_params_still_works_the_old_way(client):
    import_fixture(client, "rabobank_current.csv")
    data = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()
    assert data["range"] == {
        "from": "2024-01", "to": "2024-01", "start": "2024-01-01", "end": "2024-02-01",
        "periods": 1, "single": True, "label": "januari 2024",
    }


def test_malformed_range_is_a_422_not_a_500(client):
    import_fixture(client, "rabobank_current.csv")
    assert client.get("/api/dashboard/summary", params={"from": "maart"}).status_code == 422


def test_by_category_accepts_a_range(client):
    import_fixture(client, "rabobank_current.csv")
    jan = client.get("/api/dashboard/by-category", params={"from": "2024-01", "to": "2024-01"}).json()
    both = client.get("/api/dashboard/by-category", params={"from": "2024-01", "to": "2024-02"}).json()
    assert sum(r["transactions"] for r in both) >= sum(r["transactions"] for r in jan)


def test_expense_breakdown_range_reports_what_it_covered(client):
    import_fixture(client, "rabobank_current.csv")
    data = client.get(
        "/api/dashboard/expense-breakdown",
        params={"kind": "all", "from": "2024-01", "to": "2024-02"},
    ).json()
    assert data["range"]["from"] == "2024-01"
    assert data["range"]["to"] == "2024-02"
    assert data["range"]["periods"] == 2
    assert [t["label"] for t in data["trend"]] == ["01-2024", "02-2024"]
    assert data["total"] == pytest.approx(sum(t["amount"] for t in data["trend"]))
    # Every category row can be clicked through to its transactions.
    assert all("category_id" in row for row in data["by_category"])


def test_cashflow_window_ends_at_to(client):
    import_fixture(client, "rabobank_current.csv")
    rows = client.get("/api/dashboard/cashflow", params={"months": 3, "to": "2024-02"}).json()
    assert [r["period"] for r in rows] == ["2023-12", "2024-01", "2024-02"]


def test_categories_list_alphabetically(client):
    """Every dropdown in the app is fed by this list."""
    client.post("/api/categories/", json={"name": "zebra"})
    client.post("/api/categories/", json={"name": "Aardappels"})
    names = [c["name"] for c in client.get("/api/categories/").json()]
    assert names == sorted(names, key=str.lower)
    assert names.index("Aardappels") < names.index("zebra")


def test_summary_splits_salary_from_other_income(client):
    """A Tikkie is money in, but not income to plan on — the tile says which is which."""
    import_fixture(client, "rabobank_current.csv")
    before = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()
    assert before["income_salary"] is None, "nothing to split on until a payer is set"

    items = client.get("/api/transactions/", params={"direction": "in", "page_size": 50}).json()["items"]
    biggest = max((t for t in items if not t["is_internal"]), key=lambda t: t["amount"])
    client.put("/api/settings/salary-source", json={"counterparty": biggest["counter_name"], "min_amount_cents": 100})

    after = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()
    assert after["income_salary"] is not None
    assert after["income_salary"] + after["income_other"] == pytest.approx(after["income"])
    assert after["income_salary"] >= biggest["amount"] or after["income_salary"] == 0


def test_expense_breakdown_reports_a_median_beside_the_mean(client):
    """The mean is the wrong summary for spending: one expensive month drags it
    somewhere no month actually was. These fixtures are small, so the point
    being pinned is that both numbers are present and consistent."""
    import_fixture(client, "rabobank_current.csv")
    data = client.get(
        "/api/dashboard/expense-breakdown",
        params={"kind": "all", "from": "2024-01", "to": "2024-02"},
    ).json()

    amounts = sorted(row["amount"] for row in data["trend"])
    assert len(amounts) == 2
    assert data["monthly_median"] == pytest.approx(round(sum(amounts) / 2, 2))
    assert data["monthly_average"] == pytest.approx(round(data["total"] / 2, 2))
    assert data["busiest_period"]["amount"] == max(amounts)


def test_a_single_period_has_no_busiest_month_to_point_at(client):
    import_fixture(client, "rabobank_current.csv")
    data = client.get(
        "/api/dashboard/expense-breakdown", params={"kind": "all", "from": "2024-01", "to": "2024-01"},
    ).json()
    assert data["busiest_period"] is None
    assert data["monthly_median"] == pytest.approx(data["monthly_average"])


def test_an_outlier_month_pulls_the_mean_above_the_median(client):
    """The case behind the request: a mean of 3000 where no normal month is.

    Three periods, because the median of two values *is* their mean — so a
    two-month window can never show the divergence this warns about.
    """
    import_fixture(client, "rabobank_current.csv")
    account_id = client.get("/api/accounts/").json()[0]["id"]

    from app.database import SessionLocal
    from app.models import Transaction

    db = SessionLocal()
    try:
        db.add(Transaction(
            account_id=account_id, import_hash="quiet", booked_on=date(2023, 12, 10),
            amount_cents=-5000, description="rustige maand",
        ))
        db.add(Transaction(
            account_id=account_id, import_hash="outlier", booked_on=date(2024, 2, 10),
            amount_cents=-900000, description="eenmalige grote uitgave",
        ))
        db.commit()
    finally:
        db.close()

    data = client.get(
        "/api/dashboard/expense-breakdown",
        params={"kind": "all", "from": "2023-12", "to": "2024-02"},
    ).json()

    assert [row["label"] for row in data["trend"]] == ["12-2023", "01-2024", "02-2024"]
    assert data["monthly_average"] > data["monthly_median"] * 1.25, \
        "the mean must visibly diverge, which is what the warning keys on"
    assert data["busiest_period"]["label"] == "02-2024"

    middle = sorted(row["amount"] for row in data["trend"])[1]
    assert data["monthly_median"] == pytest.approx(middle), "the median is a month that happened"
    assert data["monthly_average"] > middle * 2, "the mean is nowhere near any normal month"


def test_money_that_round_trips_is_named_not_buried(client):
    """A savings account the app has not been told about looks like spending.
    Over €1500 out and €1200 back in a month, that single unregistered account
    can be most of a "variable expenses" total — so it gets listed."""
    import_fixture(client, "rabobank_current.csv")
    account_id = client.get("/api/accounts/").json()[0]["id"]

    from app.database import SessionLocal
    from app.models import Transaction

    db = SessionLocal()
    try:
        db.add(Transaction(
            account_id=account_id, import_hash="out-to-own", booked_on=date(2024, 1, 5),
            amount_cents=-150000, counter_iban="NL99OTHER0000000001",
            counter_name="Eigen spaarrekening elders", description="overboeking",
        ))
        db.add(Transaction(
            account_id=account_id, import_hash="back-from-own", booked_on=date(2024, 1, 25),
            amount_cents=120000, counter_iban="NL99OTHER0000000001",
            counter_name="Eigen spaarrekening elders", description="terug",
        ))
        db.commit()
    finally:
        db.close()

    data = client.get(
        "/api/dashboard/expense-breakdown", params={"kind": "all", "from": "2024-01", "to": "2024-01"},
    ).json()

    parties = data["round_trip"]["parties"]
    assert [p["iban"] for p in parties] == ["NL99OTHER0000000001"]
    assert parties[0]["paid_out"] == 1500.0
    assert parties[0]["received"] == 1200.0
    assert parties[0]["net"] == 300.0, "only the net 300 was really spent"
    assert data["round_trip"]["total"] == 1500.0
    assert data["round_trip"]["share"] > 50, "this one account dominates the total"


def test_an_ordinary_shop_is_not_a_round_trip(client):
    """The supermarket never pays you, so it must not show up here."""
    import_fixture(client, "rabobank_current.csv")
    data = client.get(
        "/api/dashboard/expense-breakdown", params={"kind": "all", "from": "2024-01", "to": "2024-02"},
    ).json()
    assert data["round_trip"]["parties"] == []
    assert data["round_trip"]["total"] == 0


def mark_one_off(client, description):
    items = client.get("/api/transactions/", params={"page_size": 200}).json()["items"]
    tx = next(t for t in items if t["description"] == description)
    assert client.patch(f"/api/transactions/{tx['id']}/one-off", json={"one_off": True}).status_code == 200
    return tx["id"]


def breakdown(client, **params):
    return client.get("/api/dashboard/expense-breakdown", params={"kind": "all", **params}).json()


def test_a_one_off_leaves_the_monthly_figures_but_stays_in_the_total(client):
    """The motorbike case: €9000 in one month must not become €750/month."""
    import_fixture(client, "rabobank_current.csv")
    account_id = client.get("/api/accounts/").json()[0]["id"]

    from app.database import SessionLocal
    from app.models import Transaction

    db = SessionLocal()
    try:
        db.add(Transaction(
            account_id=account_id, import_hash="motor", booked_on=date(2024, 2, 10),
            amount_cents=-900000, description="motor",
        ))
        db.commit()
    finally:
        db.close()

    before = breakdown(client, **{"from": "2024-01", "to": "2024-02"})
    mark_one_off(client, "motor")
    after = breakdown(client, **{"from": "2024-01", "to": "2024-02"})

    assert after["total"] == pytest.approx(before["total"]), "the money was still spent"
    assert after["one_off"] == {"total": 9000.0, "transactions": 1}
    assert after["monthly_average"] == pytest.approx(before["monthly_average"] - 4500)
    assert sum(row["amount"] for row in after["trend"]) == pytest.approx(after["total"] - 9000)
    assert after["busiest_period"]["amount"] < 9000, "the outlier month is no longer the outlier"


def test_a_one_off_keeps_its_category_and_its_place_in_the_pie(client):
    """Excluding it from the average must not hide what it was."""
    import_fixture(client, "rabobank_current.csv")
    account_id = client.get("/api/accounts/").json()[0]["id"]
    category = client.post("/api/categories/", json={"name": "Grote aankopen"}).json()["id"]

    from app.database import SessionLocal
    from app.models import Transaction

    db = SessionLocal()
    try:
        db.add(Transaction(
            account_id=account_id, import_hash="motor2", booked_on=date(2024, 1, 10),
            amount_cents=-900000, description="motor", category_id=category, category_locked=True,
        ))
        db.commit()
    finally:
        db.close()

    mark_one_off(client, "motor")
    data = breakdown(client, **{"from": "2024-01", "to": "2024-01"})
    row = next(r for r in data["by_category"] if r["name"] == "Grote aankopen")
    assert row["amount"] == 9000.0, "still visible as what it was"


def test_marking_one_off_is_a_manual_choice_no_rule_run_undoes(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 200}).json()["items"]
    target = next(t for t in items if t["amount"] < 0 and not t["is_internal"])
    client.patch(f"/api/transactions/{target['id']}/one-off", json={"one_off": True})

    client.post("/api/rules/reapply", params={"include_locked": True})

    after = next(
        t for t in client.get("/api/transactions/", params={"page_size": 200}).json()["items"]
        if t["id"] == target["id"]
    )
    assert after["one_off"] is True


def test_unmarking_puts_it_back(client):
    import_fixture(client, "rabobank_current.csv")
    items = client.get("/api/transactions/", params={"page_size": 200}).json()["items"]
    target = next(t for t in items if t["amount"] < 0 and not t["is_internal"])
    client.patch(f"/api/transactions/{target['id']}/one-off", json={"one_off": True})
    client.patch(f"/api/transactions/{target['id']}/one-off", json={"one_off": False})
    data = breakdown(client, **{"from": "2024-01", "to": "2024-02"})
    assert data["one_off"] == {"total": 0, "transactions": 0}
