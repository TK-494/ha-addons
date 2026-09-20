"""When is an account "not up to date"?

Not when its last transaction is old — a savings account that moves once a
month is quiet, not stale. And not when the last booking is old but the CSV
that covers it was uploaded yesterday: then the data *is* current. These tests
pin both, because the old rule (ten days since the last transaction, for every
account) produced warnings about accounts that were simply rarely used.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

TODAY = date(2026, 9, 20)


@pytest.fixture()
def seeded(client):
    """Two accounts with different rhythms, both last seen in an upload of a
    month ago: a current account moving every day, and a savings account
    moving once a month. Both have their last booking 20 days back."""
    from app.database import SessionLocal
    from app.models import Account, ImportBatch, Transaction

    db = SessionLocal()
    try:
        batch = ImportBatch(
            original_filename="x.csv", sha256="0" * 64, format_key="t", format_label="t",
            committed=True, uploaded_at=datetime(2026, 8, 20, 12, 0),
        )
        db.add(batch)
        current = Account(key="cur", iban="NL00TEST0000000001", display_name="Betaal", kind="checking")
        savings = Account(key="sav", iban="NL00TEST0000000002", display_name="Spaar", kind="savings")
        db.add_all([current, savings])
        db.flush()

        last = TODAY - timedelta(days=20)
        for i in range(120):                       # daily, ending 20 days ago
            db.add(Transaction(
                account_id=current.id, import_hash=f"c{i}", booked_on=last - timedelta(days=i),
                amount_cents=-100, import_batch_id=batch.id,
            ))
        for i in range(8):                         # monthly, ending 20 days ago
            db.add(Transaction(
                account_id=savings.id, import_hash=f"s{i}", booked_on=last - timedelta(days=30 * i),
                amount_cents=5000, import_batch_id=batch.id,
            ))
        db.commit()
        return {"current": current.id, "savings": savings.id}
    finally:
        db.close()


def coverage(client, account_id, today=TODAY):
    from app.database import SessionLocal
    from app.models import Account
    from app.routers.dashboard import _coverage_of

    db = SessionLocal()
    try:
        return _coverage_of(db, db.get(Account, account_id), today)
    finally:
        db.close()


def test_a_daily_account_twenty_days_behind_is_stale(client, seeded):
    c = coverage(client, seeded["current"])
    assert c["typical_gap_days"] == 1
    assert c["stale_after_days"] == 10
    assert c["stale"] is True


def test_a_monthly_account_twenty_days_behind_is_just_quiet(client, seeded):
    c = coverage(client, seeded["savings"])
    assert c["typical_gap_days"] == 30
    assert c["stale_after_days"] == 90
    assert c["stale"] is False, "same 20 days behind, but that is normal for this account"


def test_a_fresh_upload_makes_an_account_current_even_without_new_bookings(client, seeded):
    """The CSV you uploaded today covers up to today, whatever the last booking was."""
    from app.database import SessionLocal
    from app.models import ImportBatch

    db = SessionLocal()
    try:
        db.query(ImportBatch).update({"uploaded_at": datetime(2026, 9, 19, 9, 0)})
        db.commit()
    finally:
        db.close()

    c = coverage(client, seeded["current"])
    assert c["last_transaction"] == "2026-08-31"
    assert c["last_upload"] == "2026-09-19"
    assert c["current_through"] == "2026-09-19"
    assert c["days_behind"] == 1
    assert c["stale"] is False


def test_the_panel_reports_only_the_stale_ones(client, seeded):
    data = client.get("/api/dashboard/available").json()
    labels = {c["label"] for c in data["stale_accounts"]}
    # `today` in the endpoint is the real today; both accounts' data ends in
    # 2026, so what matters is the *relative* judgement, not the exact count.
    assert "Spaar" not in labels or "Betaal" in labels, \
        "a quiet account must never be flagged while a busy one is not"
