import calendar
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import date, timedelta
from typing import List, Tuple

from ..database import get_db
from ..models import Transaction, Category, UserSettings
from ..schemas import DashboardStats, MonthlyTrend, CategorySpend

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


MONTH_START_DAY_KEY = "month_start_day"
DEFAULT_MONTH_START_DAY = 1


def _month_start_day(db: Session) -> int:
    row = db.query(UserSettings).filter(UserSettings.key == MONTH_START_DAY_KEY).first()
    if not row or not row.value:
        return DEFAULT_MONTH_START_DAY
    try:
        return max(1, min(31, int(row.value)))
    except (ValueError, TypeError):
        return DEFAULT_MONTH_START_DAY


def _period_for(year: int, month: int, start_day: int) -> Tuple[date, date]:
    """Financial month labeled `year-month` runs from start_day of that
    calendar month through the day before start_day of the next month. So
    May 2025 with start_day=24 → 2025-05-24 .. 2025-06-23. start_day is
    clamped per-month (e.g. 31 in a 30-day month becomes 30)."""
    sd = min(start_day, calendar.monthrange(year, month)[1])
    start = date(year, month, sd)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    next_sd = min(start_day, calendar.monthrange(next_y, next_m)[1])
    end = date(next_y, next_m, next_sd) - timedelta(days=1)
    return start, end


@router.get("/settings")
def get_dashboard_settings(db: Session = Depends(get_db)):
    return {"month_start_day": _month_start_day(db)}


@router.post("/settings")
def save_dashboard_settings(month_start_day: int, db: Session = Depends(get_db)):
    val = str(max(1, min(31, month_start_day)))
    row = db.query(UserSettings).filter(UserSettings.key == MONTH_START_DAY_KEY).first()
    if row:
        row.value = val
    else:
        db.add(UserSettings(key=MONTH_START_DAY_KEY, value=val))
    db.commit()
    return {"month_start_day": int(val)}


@router.get("/stats")
def get_stats(year: int = None, month: int = None, db: Session = Depends(get_db)):
    today = date.today()
    year = year or today.year
    month = month or today.month

    start, end = _period_for(year, month, _month_start_day(db))

    txs = (
        db.query(Transaction)
        .filter(
            Transaction.date.between(start, end),
            Transaction.is_transfer == False,  # noqa: E712 (SQLAlchemy comparison)
        )
        .all()
    )

    income = sum(t.amount for t in txs if t.amount > 0)
    expenses = sum(t.amount for t in txs if t.amount < 0)

    return {
        "total_income": round(income, 2),
        "total_expenses": round(abs(expenses), 2),
        "net": round(income + expenses, 2),
        "transaction_count": len(txs),
        "month": month,
        "year": year,
    }


@router.get("/trend")
def get_trend(months: int = 6, db: Session = Depends(get_db)):
    today = date.today()
    start_day = _month_start_day(db)
    result = []
    month_names = ["jan", "feb", "mrt", "apr", "mei", "jun",
                   "jul", "aug", "sep", "okt", "nov", "dec"]

    for i in range(months - 1, -1, -1):
        # Step back i calendar months from today (anchored on the 1st to
        # avoid day-arithmetic drift), then ask _period_for for the actual
        # salary-aligned window.
        first_of_current = today.replace(day=1)
        target = (first_of_current - timedelta(days=i * 28)).replace(day=1)
        start, end = _period_for(target.year, target.month, start_day)

        txs = (
            db.query(Transaction)
            .filter(
                Transaction.date.between(start, end),
                Transaction.is_transfer == False,  # noqa: E712
            )
            .all()
        )
        income = sum(t.amount for t in txs if t.amount > 0)
        expenses = abs(sum(t.amount for t in txs if t.amount < 0))

        result.append({
            "month": f"{month_names[target.month - 1]} {target.year}",
            "income": round(income, 2),
            "expenses": round(expenses, 2),
        })

    return result


@router.get("/by-category")
def get_by_category(year: int = None, month: int = None, db: Session = Depends(get_db)):
    today = date.today()
    year = year or today.year
    month = month or today.month

    start, end = _period_for(year, month, _month_start_day(db))

    rows = (
        db.query(
            Category.name,
            Category.color,
            Category.icon,
            func.sum(Transaction.amount).label("total"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.date.between(start, end),
            Transaction.amount < 0,
            Transaction.is_transfer == False,  # noqa: E712
        )
        .group_by(Category.id)
        .order_by(func.sum(Transaction.amount))
        .all()
    )

    return [
        {
            "category": r.name,
            "amount": round(abs(r.total), 2),
            "color": r.color,
            "icon": r.icon,
        }
        for r in rows
    ]


@router.get("/balance-history")
def get_balance_history(days: int = 90, db: Session = Depends(get_db)):
    today = date.today()
    start = today - timedelta(days=days)

    txs = (
        db.query(Transaction)
        .filter(
            Transaction.date >= start,
            Transaction.is_transfer == False,  # noqa: E712
        )
        .order_by(Transaction.date)
        .all()
    )

    running = 0.0
    points = []
    by_date = {}
    for tx in txs:
        d = str(tx.date)
        by_date.setdefault(d, 0.0)
        by_date[d] += tx.amount

    for d in sorted(by_date.keys()):
        running += by_date[d]
        points.append({"date": d, "balance": round(running, 2)})

    return points
