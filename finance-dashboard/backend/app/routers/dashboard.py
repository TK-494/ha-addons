from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import date, timedelta
from typing import List

from ..database import get_db
from ..models import Transaction, Category
from ..schemas import DashboardStats, MonthlyTrend, CategorySpend

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_stats(year: int = None, month: int = None, db: Session = Depends(get_db)):
    today = date.today()
    year = year or today.year
    month = month or today.month

    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    txs = db.query(Transaction).filter(Transaction.date.between(start, end)).all()

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
    result = []

    for i in range(months - 1, -1, -1):
        # Calculate the month 'i' months ago
        first_of_current = today.replace(day=1)
        target = (first_of_current - timedelta(days=i * 28)).replace(day=1)
        import calendar
        last_day = calendar.monthrange(target.year, target.month)[1]
        start = date(target.year, target.month, 1)
        end = date(target.year, target.month, last_day)

        txs = db.query(Transaction).filter(Transaction.date.between(start, end)).all()
        income = sum(t.amount for t in txs if t.amount > 0)
        expenses = abs(sum(t.amount for t in txs if t.amount < 0))

        month_names = ["jan", "feb", "mrt", "apr", "mei", "jun",
                       "jul", "aug", "sep", "okt", "nov", "dec"]
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

    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

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
        .filter(Transaction.date >= start)
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
