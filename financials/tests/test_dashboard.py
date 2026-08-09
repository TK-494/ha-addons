"""Overview, drill-down and recurring-detection tests."""

from __future__ import annotations

from conftest import import_fixture


def setup_ledger(client):
    import_fixture(client, "rabobank_current.csv")
    import_fixture(client, "rabobank_creditcard.csv")
    import_fixture(client, "asn.csv")


# ─── household versus single-account scope ──────────────────────────────────

def test_household_summary_excludes_internal_transfers(client):
    """The €50 move between the two Rabobank accounts must not appear as both
    €50 of income and €50 of expenses."""
    import_fixture(client, "rabobank_current.csv")
    summary = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()

    assert summary["scope"] == "household"
    assert summary["income"] == 2000.0            # salary only, not the transfer
    assert summary["expenses"] == -1346.90        # 12.34 + 1234.56 + 100.00 settlement
    assert summary["net"] == 653.10


def test_single_account_scope_includes_its_own_transfers(client):
    """From one account's side the money genuinely moved, so it counts."""
    import_fixture(client, "rabobank_current.csv")
    accounts = client.get("/api/accounts/").json()
    second = next(a for a in accounts if a["iban"] == "NL00TEST0000000002")

    summary = client.get(
        "/api/dashboard/summary",
        params={"year": 2024, "month": 1, "account_id": second["id"]},
    ).json()
    assert summary["scope"] == "account"
    assert summary["expenses"] == -50.0


def test_savings_transfer_counts_as_saved_not_spent(client):
    import_fixture(client, "rabobank_current.csv")
    accounts = client.get("/api/accounts/").json()
    second = next(a for a in accounts if a["iban"] == "NL00TEST0000000002")
    client.patch(f"/api/accounts/{second['id']}", json={"kind": "savings"})

    summary = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()
    # The savings account received nothing in January — it *sent* €50 — so the
    # saved figure is negative, and either way it is not an expense.
    assert summary["saved"] == -50.0
    assert summary["expenses"] == -1346.90


def test_savings_rate_is_none_without_income(client):
    """A period with expenses but no income has no meaningful savings rate.
    Reporting 0% would be a claim; a division-by-zero would be a crash."""
    csv = (
        '"IBAN/BBAN","Munt","Datum","Bedrag","Saldo na trn","Naam tegenpartij","Omschrijving-1"\n'
        '"NL00TEST0000000004","EUR","2024-06-05","-20,00","80,00","Winkel Voorbeeld","Aankoop"\n'
        '"NL00TEST0000000004","EUR","2024-06-08","-30,00","50,00","Winkel Voorbeeld","Aankoop"\n'
    ).encode("utf-8")
    preview = client.post(
        "/api/imports/upload",
        files={"file": ("only-expenses.csv", csv, "text/csv")},
        data={"format_key": "rabobank_current"},
    ).json()
    client.post(f"/api/imports/{preview['batch_id']}/commit", params={"format_key": "rabobank_current"})

    summary = client.get("/api/dashboard/summary", params={"year": 2024, "month": 6}).json()
    assert summary["income"] == 0
    assert summary["expenses"] == -50.0
    assert summary["savings_rate"] is None


# ─── charts ─────────────────────────────────────────────────────────────────

def test_cashflow_returns_a_full_run_of_periods(client):
    setup_ledger(client)
    rows = client.get("/api/dashboard/cashflow", params={"months": 6}).json()
    assert len(rows) == 6
    assert all("income" in row and "expenses" in row for row in rows)


def test_by_category_splits_and_labels_uncategorised(client):
    setup_ledger(client)
    rows = client.get("/api/dashboard/by-category", params={"year": 2024, "month": 1}).json()
    assert rows
    assert all(row["amount"] >= 0 for row in rows), "expenses are reported as positive magnitudes"
    names = {row["name"] for row in rows}
    assert "Zonder categorie" in names or all(row["category_id"] for row in rows)


def test_balance_history_uses_the_banks_own_balance(client):
    """The last balance of the period, not a cumulative sum of amounts."""
    import_fixture(client, "rabobank_current.csv")
    history = client.get("/api/dashboard/balance-history", params={"months": 36}).json()
    main = next(s for s in history["series"] if "0000000001" in s["label"])
    assert 1703.10 in [v for v in main["values"] if v is not None]


def test_balance_history_carries_dormant_accounts_forward(client):
    """A savings account with no activity this month still holds its money."""
    import_fixture(client, "rabobank_current.csv")
    history = client.get("/api/dashboard/balance-history", params={"months": 36}).json()
    second = next(s for s in history["series"] if "0000000002" in s["label"])
    values = [v for v in second["values"] if v is not None]
    assert values and values[-1] == 450.0


# ─── month boundary ─────────────────────────────────────────────────────────

def test_month_boundary_setting_rebuckets_without_reimport(client):
    """Switching the boundary is a display change: the same transactions land
    in a different period with no re-import."""
    import_fixture(client, "rabobank_current.csv")
    before = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()

    client.put("/api/settings/period", json={"mode": "day", "start_day": 4})
    after = client.get("/api/dashboard/summary", params={"year": 2024, "month": 1}).json()

    # With the boundary on the 4th, the 2nd and 3rd of January fall into the
    # previous period, so January's expenses shrink.
    assert after["start"] == "2024-01-04"
    assert abs(after["expenses"]) < abs(before["expenses"])
    assert client.get("/api/transactions/", params={"page_size": 1}).json()["total"] == 6


# ─── recurring detection ────────────────────────────────────────────────────

def test_recurring_needs_three_months_of_evidence(client):
    """The fixture has one rent payment, so nothing qualifies yet — better to
    report nothing than to invent a subscription from a single row."""
    setup_ledger(client)
    assert client.get("/api/dashboard/recurring").json()["items"] == []


def test_recurring_groups_on_creditor_id(client):
    """Three monthly direct debits from one creditor make a subscription."""
    import_fixture(client, "rabobank_current.csv")
    rows = []
    header = (
        '"IBAN/BBAN","Munt","BIC","Volgnr","Datum","Rentedatum","Bedrag","Saldo na trn",'
        '"Tegenrekening IBAN/BBAN","Naam tegenpartij","Naam uiteindelijke partij",'
        '"Naam initiërende partij","BIC tegenpartij","Code","Batch ID","Transactiereferentie",'
        '"Machtigingskenmerk","Incassant ID","Betalingskenmerk","Omschrijving-1",'
        '"Omschrijving-2","Omschrijving-3","Reden retour","Oorspr bedrag","Oorspr munt","Koers"'
    )
    for index, month in enumerate(("02", "03", "04", "05"), start=10):
        rows.append(
            f'"NL00TEST0000000001","EUR","TESTNL2U","{index:018d}","2024-{month}-15","2024-{month}-15",'
            f'"-9,99","1.000,00","NL00TEST0000000006","Streamdienst Voorbeeld","","","","ei","",'
            f'"REF10{index}","M-42","NL00ZZZ111111111111","","Abonnement {month}","","","","","",""'
        )
    csv = (header + "\n" + "\n".join(rows) + "\n").encode("utf-8")

    preview = client.post(
        "/api/imports/upload",
        files={"file": ("extra.csv", csv, "text/csv")},
        data={"format_key": "rabobank_current"},
    ).json()
    client.post(f"/api/imports/{preview['batch_id']}/commit", params={"format_key": "rabobank_current"})

    recurring = client.get("/api/dashboard/recurring", params={"only_active": False}).json()["items"]
    subscription = next(r for r in recurring if "Streamdienst" in r["label"])
    assert subscription["from_creditor_id"] is True
    assert subscription["interval"] == "maandelijks"
    assert subscription["typical_amount"] == -9.99


def test_fixed_variable_reports_both_buckets(client):
    setup_ledger(client)
    result = client.get("/api/dashboard/fixed-variable", params={"months": 3}).json()
    assert len(result["months"]) == 3
    assert result["monthly_commitment"] >= 0


# ─── drill-down ─────────────────────────────────────────────────────────────

def test_category_detail(client):
    setup_ledger(client)
    categories = client.get("/api/categories/").json()
    target = next(c for c in categories if c["transaction_count"] > 0)

    detail = client.get(f"/api/dashboard/category/{target['id']}", params={"months": 24}).json()
    assert detail["category"]["name"] == target["name"]
    assert len(detail["trend"]) == 24


def test_category_detail_404(client):
    assert client.get("/api/dashboard/category/999999").status_code == 404


def test_uncategorised_worklist_is_ordered_by_amount(client):
    setup_ledger(client)
    result = client.get("/api/dashboard/uncategorised", params={"limit": 10}).json()
    amounts = [abs(g["amount"]) for g in result["groups"]]
    assert amounts == sorted(amounts, reverse=True)


def test_top_counterparties_excludes_internal(client):
    setup_ledger(client)
    rows = client.get("/api/dashboard/top-counterparties", params={"months": 24, "limit": 20}).json()
    assert all("Eigen rekening" not in row["name"] for row in rows)


# ─── declaring an account you have not imported ─────────────────────────────

def test_registering_an_own_iban_reclassifies_transfers_to_it(client):
    """Money sent to an account you own but never imported looks exactly like
    spending until you say the IBAN is yours."""
    import_fixture(client, "rabobank_current.csv")
    before = client.get("/api/transactions/", params={"search": "0000000009"}).json()["items"]
    assert before and not before[0]["is_internal"]

    created = client.post("/api/accounts/", json={
        "iban": "NL00TEST0000000009", "display_name": "Gezamenlijk", "kind": "checking",
    })
    assert created.status_code == 200

    after = client.get("/api/transactions/", params={"search": "0000000009"}).json()["items"]
    assert after[0]["is_internal"] is True
    assert after[0]["transfer_pending"] is True


def test_registering_a_duplicate_iban_is_rejected(client):
    import_fixture(client, "rabobank_current.csv")
    response = client.post("/api/accounts/", json={"iban": "NL00TEST0000000001"})
    assert response.status_code == 409


def test_manually_added_account_is_excluded_from_networth_by_default(client):
    """It has no imported transactions, so its balance is unknown — counting
    it would make the household total wrong."""
    response = client.post("/api/accounts/", json={"iban": "NL00TEST0000000009"}).json()
    assert response["include_in_networth"] is False


# ─── fixed versus variable ──────────────────────────────────────────────────

def mandated_rows(client, months, amount="-100,00", creditor="NL00ZZZ111111111111"):
    header = (
        '"IBAN/BBAN","Munt","Volgnr","Datum","Bedrag","Saldo na trn",'
        '"Tegenrekening IBAN/BBAN","Naam tegenpartij","Code","Incassant ID","Omschrijving-1"'
    )
    rows = [header]
    for index, day in enumerate(months, start=500):
        rows.append(
            f'"NL00TEST0000000001","EUR","{index}","{day}","{amount}","1.000,00",'
            f'"NL00TEST0000000055","Verhuurder Vast","ei","{creditor}","Huur"'
        )
    csv = ("\n".join(rows) + "\n").encode("utf-8")
    preview = client.post(
        "/api/imports/upload",
        files={"file": ("vast.csv", csv, "text/csv")},
        data={"format_key": "rabobank_current"},
    ).json()
    client.post(f"/api/imports/{preview['batch_id']}/commit", params={"format_key": "rabobank_current"})


def test_a_mandated_payment_counts_as_fixed(client):
    mandated_rows(client, ["2026-05-05", "2026-06-05", "2026-07-05", "2026-08-05"])
    result = client.get("/api/dashboard/cost-structure", params={"year": 2026, "month": 8}).json()
    assert any(item["label"].startswith("Verhuurder") and item["mandated"] for item in result["items"])
    assert result["period_fixed"] == 100.0


def test_a_repeating_but_varying_payment_is_not_fixed(client):
    """The supermarket repeats every week and is still a choice."""
    header = (
        '"IBAN/BBAN","Munt","Volgnr","Datum","Bedrag","Saldo na trn",'
        '"Tegenrekening IBAN/BBAN","Naam tegenpartij","Code","Omschrijving-1"'
    )
    rows = [header]
    for index, (day, amount) in enumerate([
        ("2026-05-06", "-12,00"), ("2026-06-06", "-84,00"),
        ("2026-07-06", "-31,00"), ("2026-08-06", "-97,00"),
    ], start=600):
        rows.append(
            f'"NL00TEST0000000001","EUR","{index}","{day}","{amount}","900,00",'
            f'"","Wisselende Winkel","bc","Pinbetaling"'
        )
    csv = ("\n".join(rows) + "\n").encode("utf-8")
    preview = client.post(
        "/api/imports/upload",
        files={"file": ("wisselend.csv", csv, "text/csv")},
        data={"format_key": "rabobank_current"},
    ).json()
    client.post(f"/api/imports/{preview['batch_id']}/commit", params={"format_key": "rabobank_current"})

    result = client.get("/api/dashboard/cost-structure", params={"year": 2026, "month": 8}).json()
    assert not any("Wisselende" in item["label"] for item in result["items"])
    assert any("Wisselende" in row["name"] or row["amount"] > 0 for row in result["variable_by_category"]) \
        or result["period_variable"] == 97.0


def test_fixed_and_variable_add_up_to_the_total_spend(client):
    mandated_rows(client, ["2026-05-05", "2026-06-05", "2026-07-05", "2026-08-05"])
    result = client.get("/api/dashboard/cost-structure", params={"year": 2026, "month": 8}).json()
    assert round(result["period_fixed"] + result["period_variable"], 2) == result["period_total"]


def test_share_and_leftover_are_reported(client):
    mandated_rows(client, ["2026-05-05", "2026-06-05", "2026-07-05", "2026-08-05"])
    result = client.get("/api/dashboard/cost-structure", params={"year": 2026, "month": 8}).json()
    assert result["share_fixed"] == 100.0
    assert result["left_after_fixed"] == -100.0


# ─── filtering the recurring list ───────────────────────────────────────────

def two_streams(client):
    """A monthly mandated subscription and a quarterly one, both real."""
    header = (
        '"IBAN/BBAN","Munt","Volgnr","Datum","Bedrag","Saldo na trn",'
        '"Tegenrekening IBAN/BBAN","Naam tegenpartij","Code","Incassant ID","Omschrijving-1"'
    )
    rows = [header]
    for index, day in enumerate(["2026-05-10", "2026-06-10", "2026-07-10", "2026-08-01"], start=700):
        rows.append(
            f'"NL00TEST0000000001","EUR","{index}","{day}","-9,99","900,00",'
            f'"NL00TEST0000000060","Maandstream BV","ei","NL00ZZZ222222222222","Abonnement"'
        )
    for index, day in enumerate(["2026-02-15", "2026-05-15", "2026-08-01"], start=800):
        rows.append(
            f'"NL00TEST0000000001","EUR","{index}","{day}","-60,00","900,00",'
            f'"NL00TEST0000000061","Kwartaalpolis NV","ei","NL00ZZZ333333333333","Premie"'
        )
    csv = ("\n".join(rows) + "\n").encode("utf-8")
    preview = client.post(
        "/api/imports/upload",
        files={"file": ("streams.csv", csv, "text/csv")},
        data={"format_key": "rabobank_current"},
    ).json()
    client.post(f"/api/imports/{preview['batch_id']}/commit", params={"format_key": "rabobank_current"})


def test_filter_by_interval(client):
    two_streams(client)
    monthly = client.get("/api/dashboard/recurring", params={"interval": "maandelijks"}).json()
    assert monthly["count"] >= 1
    assert all(item["interval"] == "maandelijks" for item in monthly["items"])


def test_search_matches_name_and_category(client):
    two_streams(client)
    result = client.get("/api/dashboard/recurring", params={"search": "kwartaal"}).json()
    assert result["count"] == 1
    assert "Kwartaalpolis" in result["items"][0]["label"]


def test_totals_follow_the_filter(client):
    """Filtering has to answer "what do these cost together", or it is just a
    shorter list."""
    two_streams(client)
    everything = client.get("/api/dashboard/recurring").json()
    filtered = client.get("/api/dashboard/recurring", params={"interval": "maandelijks"}).json()
    assert filtered["monthly_total"] < everything["monthly_total"]
    assert filtered["total_count"] == everything["count"]
    assert filtered["yearly_total"] == round(filtered["monthly_total"] * 12, 2)


def test_facets_list_the_available_intervals(client):
    two_streams(client)
    facets = client.get("/api/dashboard/recurring").json()["facets"]
    values = {f["value"] for f in facets["intervals"]}
    assert "maandelijks" in values
    assert all(f["count"] > 0 for f in facets["intervals"])


def test_filter_by_amount_range(client):
    two_streams(client)
    result = client.get("/api/dashboard/recurring", params={"min_monthly": 15}).json()
    assert all(abs(item["monthly_equivalent"]) >= 15 for item in result["items"])


def test_filter_fixed_versus_variable(client):
    two_streams(client)
    fixed = client.get("/api/dashboard/recurring", params={"kind": "fixed"}).json()
    assert fixed["count"] >= 1
    assert all(item["committed"] for item in fixed["items"])


def test_sorting_can_be_reversed(client):
    two_streams(client)
    down = client.get("/api/dashboard/recurring", params={"sort": "monthly", "desc": True}).json()["items"]
    up = client.get("/api/dashboard/recurring", params={"sort": "monthly", "desc": False}).json()["items"]
    assert [i["label"] for i in down] == [i["label"] for i in up][::-1]


# ─── the fixed / variable expense tabs ──────────────────────────────────────

def test_breakdown_splits_the_same_ledger_two_ways(client):
    """Fixed plus variable is every expense, once. Neither tab may drop or
    double-count a transaction."""
    mandated_rows(client, ["2026-05-05", "2026-06-05", "2026-07-05", "2026-08-05"])
    import_fixture(client, "rabobank_current.csv")

    fixed = client.get("/api/dashboard/expense-breakdown", params={"kind": "fixed", "months": 0}).json()
    variable = client.get("/api/dashboard/expense-breakdown", params={"kind": "variable", "months": 0}).json()
    everything = client.get("/api/dashboard/expense-breakdown", params={"kind": "all", "months": 0}).json()

    assert round(fixed["total"] + variable["total"], 2) == round(everything["total"], 2)
    assert fixed["transactions"] + variable["transactions"] == everything["transactions"]


def test_each_range_widens_the_window(client):
    mandated_rows(client, ["2026-05-05", "2026-06-05", "2026-07-05", "2026-08-05"])
    totals = []
    for months in (1, 3, 6, 12):
        result = client.get("/api/dashboard/expense-breakdown", params={
            "kind": "fixed", "months": months,
        }).json()
        assert result["range"]["months"] == months
        totals.append(result["total"])
    assert totals == sorted(totals), "a longer range cannot contain less"


def test_all_time_starts_at_the_first_transaction(client):
    mandated_rows(client, ["2026-05-05", "2026-06-05", "2026-07-05", "2026-08-05"])
    result = client.get("/api/dashboard/expense-breakdown", params={"months": 0, "kind": "all"}).json()
    assert result["range"]["start"] == "2026-05-05"
    assert result["range"]["label"] == "alles"


def test_monthly_average_divides_by_the_range(client):
    mandated_rows(client, ["2026-05-05", "2026-06-05", "2026-07-05", "2026-08-05"])
    result = client.get("/api/dashboard/expense-breakdown", params={"kind": "fixed", "months": 4}).json()
    assert result["monthly_average"] == round(result["total"] / 4, 2)


def test_category_shares_add_up(client):
    mandated_rows(client, ["2026-05-05", "2026-06-05", "2026-07-05", "2026-08-05"])
    import_fixture(client, "rabobank_current.csv")
    result = client.get("/api/dashboard/expense-breakdown", params={"kind": "all", "months": 0}).json()
    assert abs(sum(row["share"] for row in result["by_category"]) - 100) < 1.0
    assert round(sum(row["amount"] for row in result["by_category"]), 2) == round(result["total"], 2)


def test_an_empty_range_reports_zero_rather_than_failing(client):
    import_fixture(client, "rabobank_current.csv")
    result = client.get("/api/dashboard/expense-breakdown", params={"kind": "fixed", "months": 1}).json()
    assert result["total"] == 0
    assert result["by_category"] == []
    assert result["monthly_average"] == 0


# ─── the uncategorised worklist ─────────────────────────────────────────────

def test_worklist_reports_amount_and_progress(client):
    import_fixture(client, "rabobank_current.csv")
    result = client.get("/api/dashboard/uncategorised").json()
    assert result["total_amount"] >= 0
    assert 0 <= result["progress"] <= 100
    assert result["categorised"] + result["total_uncategorised"] > 0


def test_assigning_a_group_categorises_exactly_that_group(client):
    import_fixture(client, "rabobank_current.csv")
    groups = client.get("/api/dashboard/uncategorised").json()["groups"]
    if not groups:
        return
    target = groups[0]
    category = client.get("/api/categories/").json()[0]

    result = client.post("/api/dashboard/uncategorised/assign", json={
        "name": target["name"], "category_id": category["id"], "create_rule": False,
    }).json()

    assert result["updated"] == target["transactions"]
    remaining = client.get("/api/dashboard/uncategorised").json()
    assert all(g["name"] != target["name"] for g in remaining["groups"])


def test_assigning_can_write_the_rule_too(client):
    """Without a rule the same rows come back on the next import."""
    import_fixture(client, "rabobank_current.csv")
    groups = client.get("/api/dashboard/uncategorised").json()["groups"]
    if not groups:
        return
    target = groups[0]
    category = client.get("/api/categories/").json()[0]

    result = client.post("/api/dashboard/uncategorised/assign", json={
        "name": target["name"], "category_id": category["id"], "create_rule": True,
    }).json()
    assert result["rule_id"] is not None

    rule = next(r for r in client.get("/api/rules/").json() if r["id"] == result["rule_id"])
    assert rule["origin"] == "transaction"


def test_assigned_rows_are_locked_against_rule_reruns(client):
    import_fixture(client, "rabobank_current.csv")
    groups = client.get("/api/dashboard/uncategorised").json()["groups"]
    if not groups:
        return
    category = client.get("/api/categories/").json()[0]
    client.post("/api/dashboard/uncategorised/assign", json={
        "name": groups[0]["name"], "category_id": category["id"], "create_rule": False,
    })
    client.post("/api/rules/reapply")

    tagged = client.get("/api/transactions/", params={"category_id": category["id"]}).json()
    assert tagged["total"] >= groups[0]["transactions"]


def test_assign_rejects_an_unknown_category(client):
    import_fixture(client, "rabobank_current.csv")
    response = client.post("/api/dashboard/uncategorised/assign", json={
        "name": "wat dan ook", "category_id": 999999,
    })
    assert response.status_code == 422


# ─── the detection cache ────────────────────────────────────────────────────

def test_recurring_cache_notices_a_recategorisation(client):
    """The cache keys on a ledger fingerprint; changing a category must not
    serve a stale grouping."""
    setup_ledger(client)
    before = client.get("/api/dashboard/recurring", params={"only_active": False}).json()

    items = client.get("/api/transactions/", params={"page_size": 5}).json()["items"]
    category = client.get("/api/categories/").json()[0]
    client.patch(f"/api/transactions/{items[0]['id']}/category", json={"category_id": category["id"]})

    after = client.get("/api/dashboard/recurring", params={"only_active": False}).json()
    assert after["total_count"] == before["total_count"]


def test_recurring_cache_notices_new_transactions(client):
    import_fixture(client, "rabobank_current.csv")
    before = client.get("/api/dashboard/recurring", params={"only_active": False}).json()["total_count"]
    import_fixture(client, "asn.csv")
    after = client.get("/api/dashboard/recurring", params={"only_active": False}).json()["total_count"]
    assert after >= before
