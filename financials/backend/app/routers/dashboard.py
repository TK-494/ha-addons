"""Overview and drill-down endpoints.

Two reading levels, and the difference matters:

* **household** — internal transfers are excluded, so income and expenses mean
  money entering and leaving the household.
* **one account** — transfers are included, because from that account's side
  the money really did move.

`account_id` switches between them.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, Category, Transaction, TransactionSplit
from ..services import periods, recurring, workdays

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _period_expr(config: periods.PeriodConfig):
    """SQL expression mapping a booking date to its period label `YYYY-MM`.

    The common case is arithmetic: with a start day of 24, 2026-08-23 belongs
    to 2026-07 and 2026-08-24 to 2026-08. Months whose real boundary differs —
    a salary paid on the Friday because the 25th was a Sunday — get an explicit
    branch covering just the days between the two dates. That keeps the CASE to
    one branch per shifted month instead of one per month in history.
    """
    start_day = config.effective_day
    if start_day <= 1:
        base = func.strftime("%Y-%m", Transaction.booked_on)
    else:
        base = case(
            (
                cast(func.strftime("%d", Transaction.booked_on), Integer) >= start_day,
                func.strftime("%Y-%m", Transaction.booked_on),
            ),
            else_=func.strftime("%Y-%m", func.date(Transaction.booked_on, "start of month", "-1 month")),
        )

    branches = []
    for (year, month), actual in sorted(config.overrides.items()):
        fixed = config.fixed_start(year, month)
        if actual == fixed:
            continue
        label = f"{year:04d}-{month:02d}"
        if actual < fixed:
            # Paid early: the days from the real date up to the fixed one
            # belong to this period, though the arithmetic says the previous.
            branches.append((
                and_(Transaction.booked_on >= actual, Transaction.booked_on < fixed), label
            ))
        else:
            # Paid late: those days still belong to the previous period.
            previous = periods.shift_period(year, month, -1)
            branches.append((
                and_(Transaction.booked_on >= fixed, Transaction.booked_on < actual),
                f"{previous[0]:04d}-{previous[1]:02d}",
            ))

    return case(*branches, else_=base) if branches else base


def _scope(stmt, account_id: Optional[int]):
    """Household scope hides internal transfers; a single-account scope keeps
    them, because that account's own cashflow includes them."""
    if account_id:
        return stmt.where(Transaction.account_id == account_id)
    return stmt.where(Transaction.is_internal.is_(False))


POSITIVE = case((Transaction.amount_cents > 0, Transaction.amount_cents), else_=0)
NEGATIVE = case((Transaction.amount_cents < 0, Transaction.amount_cents), else_=0)


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    year: Optional[int] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
    account_id: Optional[int] = None,
):
    """KPI row for one period, with the previous period for comparison."""
    config = periods.load_config(db)
    if year is None or month is None:
        year, month = periods.period_of(date.today(), config)

    def totals(y: int, m: int) -> dict:
        start, end = periods.period_bounds(y, m, config)
        stmt = _scope(
            select(
                func.coalesce(func.sum(POSITIVE), 0),
                func.coalesce(func.sum(NEGATIVE), 0),
                func.count(),
            ).where(Transaction.booked_on >= start, Transaction.booked_on < end),
            account_id,
        )
        income, expenses, count = db.execute(stmt).one()
        return {
            "income": (income or 0) / 100,
            "expenses": (expenses or 0) / 100,
            "net": ((income or 0) + (expenses or 0)) / 100,
            "transactions": count,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

    current = totals(year, month)
    previous = totals(*periods.shift_period(year, month, -1))

    # What actually moved into savings this period. Transfers are excluded from
    # income and expenses, so this is the honest "saved" figure — the amount
    # that left the current accounts and stayed inside the household.
    start, end = periods.period_bounds(year, month, config)
    saved = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0))
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.kind == "savings",
            Transaction.is_internal.is_(True),
            Transaction.booked_on >= start,
            Transaction.booked_on < end,
        )
    ) or 0

    savings_accounts = db.scalar(
        select(func.count()).select_from(Account).where(Account.kind == "savings")
    ) or 0

    income = current["income"]
    return {
        "savings_accounts": savings_accounts,
        "year": year,
        "month": month,
        "scope": "account" if account_id else "household",
        **current,
        "saved": saved / 100,
        "savings_rate": round(100 * (income + current["expenses"]) / income, 1) if income > 0 else None,
        "previous": previous,
        "delta_income": round(current["income"] - previous["income"], 2),
        "delta_expenses": round(current["expenses"] - previous["expenses"], 2),
    }


@router.get("/cashflow")
def cashflow(
    db: Session = Depends(get_db),
    months: int = Query(12, ge=1, le=120),
    account_id: Optional[int] = None,
):
    """Income, expenses and net per period — one query for the whole range."""
    config = periods.load_config(db)
    labels = periods.recent_periods(months, config)
    first_start, _ = periods.period_bounds(*labels[0], config)
    _, last_end = periods.period_bounds(*labels[-1], config)

    period = _period_expr(config).label("period")
    stmt = _scope(
        select(
            period,
            func.coalesce(func.sum(POSITIVE), 0),
            func.coalesce(func.sum(NEGATIVE), 0),
        ).where(Transaction.booked_on >= first_start, Transaction.booked_on < last_end),
        account_id,
    ).group_by(period)

    rows = {p: (income, expenses) for p, income, expenses in db.execute(stmt).all()}

    result = []
    for y, m in labels:
        income, expenses = rows.get(f"{y:04d}-{m:02d}", (0, 0))
        result.append({
            "period": f"{y:04d}-{m:02d}",
            "label": f"{m:02d}-{y}",
            "income": (income or 0) / 100,
            "expenses": abs(expenses or 0) / 100,
            "net": ((income or 0) + (expenses or 0)) / 100,
        })
    return result


@router.get("/by-category")
def by_category(
    db: Session = Depends(get_db),
    year: Optional[int] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
    account_id: Optional[int] = None,
    direction: Literal["out", "in"] = "out",
):
    config = periods.load_config(db)
    if year is None or month is None:
        year, month = periods.period_of(date.today(), config)
    start, end = periods.period_bounds(year, month, config)

    amount_filter = Transaction.amount_cents < 0 if direction == "out" else Transaction.amount_cents > 0

    # Whole transactions — everything that has not been split apart.
    split_ids = select(TransactionSplit.transaction_id).distinct()
    whole = _scope(
        select(
            Category.id, Category.name, Category.color,
            func.coalesce(func.sum(Transaction.amount_cents), 0),
            func.count(),
        )
        .join(Category, Category.id == Transaction.category_id, isouter=True)
        .where(
            Transaction.booked_on >= start, Transaction.booked_on < end, amount_filter,
            Transaction.id.not_in(split_ids),
        ),
        account_id,
    ).group_by(Category.id)

    # The parts of split transactions count individually: a salary divided into
    # base pay and travel allowance belongs to both, in the right proportions.
    part_amount = TransactionSplit.amount_cents
    parts = _scope(
        select(
            Category.id, Category.name, Category.color,
            func.coalesce(func.sum(part_amount), 0),
            func.count(),
        )
        .select_from(TransactionSplit)
        .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
        .join(Category, Category.id == TransactionSplit.category_id, isouter=True)
        .where(
            Transaction.booked_on >= start, Transaction.booked_on < end,
            part_amount < 0 if direction == "out" else part_amount > 0,
        ),
        account_id,
    ).group_by(Category.id)

    totals: dict = {}
    for cid, name, color, total, count in db.execute(whole).all() + db.execute(parts).all():
        entry = totals.setdefault(cid, {"name": name, "color": color, "cents": 0, "count": 0})
        entry["cents"] += total or 0
        entry["count"] += count

    return [
        {
            "category_id": cid,
            "name": entry["name"] or "Zonder categorie",
            "color": entry["color"] or "#94a3b8",
            "amount": abs(entry["cents"]) / 100,
            "transactions": entry["count"],
        }
        for cid, entry in sorted(totals.items(), key=lambda kv: -abs(kv[1]["cents"]))
    ]


@router.get("/balance-history")
def balance_history(
    db: Session = Depends(get_db),
    months: int = Query(24, ge=1, le=240),
):
    """Closing balance per account per period, plus the household total.

    Uses the bank's own running balance rather than a cumulative sum of
    amounts, so the line matches the statement exactly.
    """
    config = periods.load_config(db)
    labels = periods.recent_periods(months, config)
    first_start, _ = periods.period_bounds(*labels[0], config)

    period = _period_expr(config).label("period")
    ranked = (
        select(
            Transaction.account_id,
            period,
            Transaction.balance_after_cents,
            func.row_number().over(
                partition_by=[Transaction.account_id, period],
                order_by=[Transaction.booked_on.desc(), Transaction.id.desc()],
            ).label("rn"),
        )
        .where(
            Transaction.balance_after_cents.isnot(None),
            Transaction.booked_on >= first_start,
        )
        .subquery()
    )

    rows = db.execute(
        select(ranked.c.account_id, ranked.c.period, ranked.c.balance_after_cents)
        .where(ranked.c.rn == 1)
    ).all()

    accounts = {
        a.id: a for a in db.scalars(select(Account).where(Account.archived.is_(False))).all()
    }
    by_account: dict[int, dict[str, int]] = {}
    for account_id, period_label, balance in rows:
        by_account.setdefault(account_id, {})[period_label] = balance

    series = []
    for account_id, account in accounts.items():
        points = by_account.get(account_id, {})
        carried = None
        values = []
        for y, m in labels:
            key = f"{y:04d}-{m:02d}"
            # Carry the last known balance through months without activity —
            # a dormant savings account still holds its money.
            carried = points.get(key, carried)
            values.append(None if carried is None else carried / 100)
        series.append({
            "account_id": account_id,
            "label": account.label,
            "kind": account.kind,
            "include_in_networth": account.include_in_networth,
            "values": values,
        })

    totals = []
    for index in range(len(labels)):
        present = [
            s["values"][index] for s in series
            if s["include_in_networth"] and s["values"][index] is not None
        ]
        totals.append(round(sum(present), 2) if present else None)

    return {
        "periods": [f"{m:02d}-{y}" for y, m in labels],
        "series": series,
        "total": totals,
    }


@router.get("/fixed-variable")
def fixed_variable(
    db: Session = Depends(get_db),
    months: int = Query(6, ge=1, le=36),
):
    """Recurring commitments versus discretionary spend.

    "What do I actually need per month" is the number this answers, and it is
    only meaningful because recurring detection is real rather than a guess
    from category names.
    """
    config = periods.load_config(db)
    groups = recurring.detect(db, config)
    fixed_ids = recurring.recurring_transaction_ids(groups)

    labels = periods.recent_periods(months, config)
    first_start, _ = periods.period_bounds(*labels[0], config)
    _, last_end = periods.period_bounds(*labels[-1], config)

    period = _period_expr(config).label("period")
    rows = db.execute(
        select(period, Transaction.id, Transaction.amount_cents)
        .where(
            Transaction.is_internal.is_(False),
            Transaction.amount_cents < 0,
            Transaction.booked_on >= first_start,
            Transaction.booked_on < last_end,
        )
    ).all()

    buckets: dict[str, dict[str, int]] = {}
    for period_label, tx_id, amount in rows:
        bucket = buckets.setdefault(period_label, {"fixed": 0, "variable": 0})
        bucket["fixed" if tx_id in fixed_ids else "variable"] += abs(amount)

    result = []
    for y, m in labels:
        bucket = buckets.get(f"{y:04d}-{m:02d}", {"fixed": 0, "variable": 0})
        result.append({
            "period": f"{y:04d}-{m:02d}",
            "label": f"{m:02d}-{y}",
            "fixed": bucket["fixed"] / 100,
            "variable": bucket["variable"] / 100,
        })

    active = [g for g in groups if g.is_active]
    return {
        "months": result,
        "recurring_count": len(active),
        "monthly_commitment": round(sum(abs(g.monthly_equivalent_cents) for g in active) / 100, 2),
    }


@router.get("/recurring")
def recurring_payments(db: Session = Depends(get_db), only_active: bool = True):
    """Detected subscriptions and standing charges."""
    config = periods.load_config(db)
    groups = recurring.detect(db, config)
    if only_active:
        groups = [g for g in groups if g.is_active]
    groups.sort(key=lambda g: abs(g.monthly_equivalent_cents), reverse=True)
    return [recurring.serialise(g) for g in groups]


@router.get("/top-counterparties")
def top_counterparties(
    db: Session = Depends(get_db),
    year: Optional[int] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
    months: int = Query(1, ge=1, le=120),
    limit: int = Query(10, ge=1, le=50),
):
    config = periods.load_config(db)
    if year is None or month is None:
        year, month = periods.period_of(date.today(), config)
    labels = periods.recent_periods(months, config) if months > 1 else [(year, month)]
    start, _ = periods.period_bounds(*labels[0], config)
    _, end = periods.period_bounds(*labels[-1], config)

    name = func.coalesce(func.nullif(Transaction.counter_name, ""), Transaction.description)
    stmt = (
        select(name, func.sum(Transaction.amount_cents), func.count())
        .where(
            Transaction.is_internal.is_(False),
            Transaction.amount_cents < 0,
            Transaction.booked_on >= start,
            Transaction.booked_on < end,
        )
        .group_by(name)
        .order_by(func.sum(Transaction.amount_cents))
        .limit(limit)
    )
    return [
        {"name": counterparty, "amount": abs(total or 0) / 100, "transactions": count}
        for counterparty, total, count in db.execute(stmt).all()
    ]


@router.get("/year-over-year")
def year_over_year(db: Session = Depends(get_db), years: int = Query(3, ge=2, le=9)):
    """Per-year totals and a month-by-month comparison. Worth having only
    because the Rabobank export reaches back to 2018."""
    current_year = date.today().year
    first = current_year - years + 1

    rows = db.execute(
        select(
            func.strftime("%Y", Transaction.booked_on),
            func.strftime("%m", Transaction.booked_on),
            func.coalesce(func.sum(POSITIVE), 0),
            func.coalesce(func.sum(NEGATIVE), 0),
        )
        .where(
            Transaction.is_internal.is_(False),
            Transaction.booked_on >= date(first, 1, 1),
        )
        .group_by(func.strftime("%Y", Transaction.booked_on), func.strftime("%m", Transaction.booked_on))
    ).all()

    per_year: dict[int, dict] = {}
    for year_text, month_text, income, expenses in rows:
        year = int(year_text)
        entry = per_year.setdefault(year, {"year": year, "income": 0, "expenses": 0, "months": [0] * 12})
        entry["income"] += (income or 0) / 100
        entry["expenses"] += abs(expenses or 0) / 100
        entry["months"][int(month_text) - 1] = abs(expenses or 0) / 100

    return sorted(per_year.values(), key=lambda e: e["year"])


@router.get("/category/{category_id}")
def category_detail(
    category_id: int,
    db: Session = Depends(get_db),
    months: int = Query(12, ge=1, le=120),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Categorie niet gevonden.")

    config = periods.load_config(db)
    labels = periods.recent_periods(months, config)
    first_start, _ = periods.period_bounds(*labels[0], config)
    _, last_end = periods.period_bounds(*labels[-1], config)

    period = _period_expr(config).label("period")
    rows = dict(db.execute(
        select(period, func.coalesce(func.sum(Transaction.amount_cents), 0))
        .where(
            Transaction.category_id == category_id,
            Transaction.is_internal.is_(False),
            Transaction.booked_on >= first_start,
            Transaction.booked_on < last_end,
        )
        .group_by(period)
    ).all())

    trend = [
        {"label": f"{m:02d}-{y}", "amount": abs(rows.get(f"{y:04d}-{m:02d}", 0) or 0) / 100}
        for y, m in labels
    ]

    name = func.coalesce(func.nullif(Transaction.counter_name, ""), Transaction.description)
    merchants = db.execute(
        select(name, func.sum(Transaction.amount_cents), func.count())
        .where(
            Transaction.category_id == category_id,
            Transaction.booked_on >= first_start,
        )
        .group_by(name)
        .order_by(func.sum(Transaction.amount_cents))
        .limit(10)
    ).all()

    amounts = [point["amount"] for point in trend]
    active = [a for a in amounts if a > 0]
    return {
        "category": {"id": category.id, "name": category.name, "color": category.color},
        "trend": trend,
        "average": round(sum(active) / len(active), 2) if active else 0,
        "total": round(sum(amounts), 2),
        "merchants": [
            {"name": n, "amount": abs(total or 0) / 100, "transactions": count}
            for n, total, count in merchants
        ],
    }


@router.get("/counterparty")
def counterparty_detail(
    db: Session = Depends(get_db),
    name: str = Query(..., min_length=2, max_length=200),
):
    needle = f"%{name.strip()}%"
    condition = or_(Transaction.counter_name.ilike(needle), Transaction.description.ilike(needle))

    total, count, first, last = db.execute(
        select(
            func.coalesce(func.sum(Transaction.amount_cents), 0),
            func.count(),
            func.min(Transaction.booked_on),
            func.max(Transaction.booked_on),
        ).where(condition, Transaction.is_internal.is_(False))
    ).one()

    config = periods.load_config(db)
    period = _period_expr(config).label("period")
    history = db.execute(
        select(period, func.coalesce(func.sum(Transaction.amount_cents), 0))
        .where(condition, Transaction.is_internal.is_(False))
        .group_by(period)
        .order_by(period)
    ).all()

    return {
        "name": name,
        "total": abs(total or 0) / 100,
        "transactions": count,
        "first_seen": first if isinstance(first, str) else (first.isoformat() if first else None),
        "last_seen": last if isinstance(last, str) else (last.isoformat() if last else None),
        "history": [{"label": p, "amount": abs(amount or 0) / 100} for p, amount in history],
    }


@router.get("/uncategorised")
def uncategorised(db: Session = Depends(get_db), limit: int = Query(25, ge=1, le=100)):
    """Worklist: what the rules did not catch, biggest amounts first, so the
    money that matters gets handled before the €2 coffees."""
    name = func.coalesce(func.nullif(Transaction.counter_name, ""), Transaction.description)
    rows = db.execute(
        select(name, func.sum(Transaction.amount_cents), func.count(), func.max(Transaction.id))
        .where(Transaction.category_id.is_(None), Transaction.is_internal.is_(False))
        .group_by(name)
        .order_by(func.abs(func.sum(Transaction.amount_cents)).desc())
        .limit(limit)
    ).all()

    total = db.scalar(
        select(func.count()).select_from(Transaction)
        .where(Transaction.category_id.is_(None), Transaction.is_internal.is_(False))
    ) or 0

    return {
        "total_uncategorised": total,
        "groups": [
            {
                "name": n,
                "amount": (amount or 0) / 100,
                "transactions": count,
                "sample_transaction_id": sample_id,
            }
            for n, amount, count, sample_id in rows
        ],
    }


@router.get("/available")
def available(
    db: Session = Depends(get_db),
    year: Optional[int] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
):
    """How much of this period is still yours to spend, and how long it has to
    last.

    "Income minus what you spent" is not the answer: the rent has not gone out
    yet on the 3rd. So the recurring commitments still due before the period
    ends are subtracted too — otherwise the figure looks generous exactly when
    it should not.

    Income is reported split into fixed and variable, because a travel
    allowance is not something to build a standing commitment on.
    """
    config = periods.load_config(db)
    if year is None or month is None:
        year, month = periods.period_of(date.today(), config)
    start, end = periods.period_bounds(year, month, config)
    today = date.today()

    # ── how far the data actually reaches ───────────────────────────────────
    accounts = db.scalars(select(Account).where(Account.archived.is_(False))).all()
    coverage = []
    for account in accounts:
        last = db.scalar(
            select(func.max(Transaction.booked_on)).where(Transaction.account_id == account.id)
        )
        last_date = date.fromisoformat(last) if isinstance(last, str) else last
        coverage.append({
            "account_id": account.id,
            "label": account.label,
            "last_transaction": last_date.isoformat() if last_date else None,
            "days_behind": (today - last_date).days if last_date else None,
        })

    dated = [c for c in coverage if c["last_transaction"]]
    data_through = max((c["last_transaction"] for c in dated), default=None)
    stale = [c for c in dated if c["days_behind"] is not None and c["days_behind"] > 10]

    # ── income, split into what you can and cannot count on ─────────────────
    def income_parts() -> tuple[int, int]:
        fixed = variable = 0

        split_ids = select(TransactionSplit.transaction_id).distinct()
        rows = db.execute(
            select(Transaction.amount_cents, Category.variable_income)
            .join(Category, Category.id == Transaction.category_id, isouter=True)
            .where(
                Transaction.is_internal.is_(False),
                Transaction.amount_cents > 0,
                Transaction.booked_on >= start, Transaction.booked_on < end,
                Transaction.id.not_in(split_ids),
            )
        ).all()
        part_rows = db.execute(
            select(TransactionSplit.amount_cents, Category.variable_income)
            .select_from(TransactionSplit)
            .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
            .join(Category, Category.id == TransactionSplit.category_id, isouter=True)
            .where(
                Transaction.is_internal.is_(False),
                TransactionSplit.amount_cents > 0,
                Transaction.booked_on >= start, Transaction.booked_on < end,
            )
        ).all()

        for amount, is_variable in rows + part_rows:
            if is_variable:
                variable += amount
            else:
                fixed += amount
        return fixed, variable

    fixed_income, variable_income = income_parts()

    spent = abs(db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.is_internal.is_(False),
            Transaction.amount_cents < 0,
            Transaction.booked_on >= start, Transaction.booked_on < end,
        )
    ) or 0)

    # ── recurring commitments still to come in this period ──────────────────
    # Only genuine commitments, which means a direct-debit mandate. Recurring
    # detection also finds the supermarket and the takeaway — those repeat, but
    # nobody is going to collect them, and counting them as money already spoken
    # for makes the free figure look far worse than it is.
    groups = [g for g in recurring.detect(db, config) if g.is_active and g.creditor_id]
    upcoming = []
    for group in groups:
        if any(start <= value < end for value in group.dates):
            continue  # already collected this period
        cadence = max(round(group.cadence_days or 30.0), 1)
        expected = group.last_seen + timedelta(days=cadence)
        # Roll forward rather than clamp: a date before the period start means
        # the cadence has lapped, not that it is due today.
        while expected < start:
            expected += timedelta(days=cadence)
        if expected >= end:
            continue
        upcoming.append({
            "label": group.label,
            "amount": abs(group.typical_amount_cents) / 100,
            "expected": expected.isoformat(),
            "category": group.category_name,
        })
    upcoming.sort(key=lambda item: item["expected"])
    committed = int(round(sum(item["amount"] for item in upcoming) * 100))

    income_total = fixed_income + variable_income
    free = income_total - spent - committed

    days_left = max(0, (end - max(today, start)).days)
    salary = periods.next_salary_estimate(db, config)

    return {
        "period": {"year": year, "month": month, "start": start.isoformat(), "end": end.isoformat()},
        "data_through": data_through,
        "coverage": sorted(coverage, key=lambda c: c["last_transaction"] or ""),
        "stale_accounts": stale,
        "income": {
            "total": income_total / 100,
            "fixed": fixed_income / 100,
            "variable": variable_income / 100,
        },
        "spent": spent / 100,
        "committed": committed / 100,
        "upcoming": upcoming[:12],
        "available": free / 100,
        "days_left": days_left,
        "per_day": round(free / 100 / days_left, 2) if days_left else None,
        "next_salary": salary,
    }
