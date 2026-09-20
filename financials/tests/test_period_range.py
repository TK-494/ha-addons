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


def test_cashflow_window_ends_at_to(client):
    import_fixture(client, "rabobank_current.csv")
    rows = client.get("/api/dashboard/cashflow", params={"months": 3, "to": "2024-02"}).json()
    assert [r["period"] for r in rows] == ["2023-12", "2024-01", "2024-02"]
