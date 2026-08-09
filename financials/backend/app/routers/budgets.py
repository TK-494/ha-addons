"""Budgets per category per period.

Rollover is opt-in per budget: an underspent month adds its remainder to the
next one, which suits irregular categories (clothing, car maintenance) and
would only distort steady ones (rent).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Budget, Category, Transaction
from ..services import periods

router = APIRouter(prefix="/budgets", tags=["budgets"])


class BudgetIn(BaseModel):
    category_id: int
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    amount: float = Field(..., ge=0)
    rollover: bool = False


def _spent_cents(db: Session, category_id: int, year: int, month: int, config) -> int:
    start, end = periods.period_bounds(year, month, config)
    return abs(db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.category_id == category_id,
            Transaction.is_internal.is_(False),
            Transaction.amount_cents < 0,
            Transaction.booked_on >= start,
            Transaction.booked_on < end,
        )
    ) or 0)


@router.get("/")
def list_budgets(
    db: Session = Depends(get_db),
    year: Optional[int] = None,
    month: Optional[int] = Query(None, ge=1, le=12),
):
    config = periods.load_config(db)
    if year is None or month is None:
        year, month = periods.period_of(date.today(), config)

    budgets = db.scalars(
        select(Budget).where(Budget.year == year, Budget.month == month)
    ).all()
    by_category = {b.category_id: b for b in budgets}

    categories = db.scalars(
        select(Category).where(Category.is_income.is_(False),
                               Category.excluded_from_budget.is_(False))
        .order_by(Category.sort_order, Category.name)
    ).all()

    previous_year, previous_month = periods.shift_period(year, month, -1)

    rows = []
    for category in categories:
        budget = by_category.get(category.id)
        spent = _spent_cents(db, category.id, year, month, config)
        if budget is None and spent == 0:
            continue  # no budget and no spend: nothing to show

        planned = budget.amount_cents if budget else 0
        carried = 0
        if budget is not None and budget.rollover:
            previous = db.scalar(
                select(Budget).where(
                    Budget.category_id == category.id,
                    Budget.year == previous_year,
                    Budget.month == previous_month,
                )
            )
            if previous is not None:
                carried = max(
                    0,
                    previous.amount_cents
                    - _spent_cents(db, category.id, previous_year, previous_month, config),
                )

        available = planned + carried
        rows.append({
            "budget_id": budget.id if budget else None,
            "category_id": category.id,
            "category_name": category.name,
            "color": category.color,
            "planned": planned / 100,
            "carried_over": carried / 100,
            "available": available / 100,
            "spent": spent / 100,
            "remaining": (available - spent) / 100,
            "percentage": round(100 * spent / available, 1) if available else None,
            "rollover": bool(budget.rollover) if budget else False,
        })

    budgeted = sum(r["available"] for r in rows)
    spent_total = sum(r["spent"] for r in rows)
    return {
        "year": year,
        "month": month,
        "total_available": round(budgeted, 2),
        "total_spent": round(spent_total, 2),
        "total_remaining": round(budgeted - spent_total, 2),
        "rows": rows,
    }


@router.post("/")
def upsert_budget(payload: BudgetIn, db: Session = Depends(get_db)):
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(422, "Categorie bestaat niet.")

    budget = db.scalar(
        select(Budget).where(
            Budget.category_id == payload.category_id,
            Budget.year == payload.year,
            Budget.month == payload.month,
        )
    )
    amount_cents = int(round(payload.amount * 100))
    if budget is None:
        budget = Budget(
            category_id=payload.category_id, year=payload.year, month=payload.month,
            amount_cents=amount_cents, rollover=payload.rollover,
        )
        db.add(budget)
    else:
        budget.amount_cents = amount_cents
        budget.rollover = payload.rollover
    db.commit()
    return {"id": budget.id}


@router.delete("/{budget_id}")
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(404, "Budget niet gevonden.")
    db.delete(budget)
    db.commit()
    return {"deleted": budget_id}


@router.post("/copy-previous")
def copy_previous(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Copy last period's budgets into this one — the usual monthly ritual."""
    previous_year, previous_month = periods.shift_period(year, month, -1)
    source = db.scalars(
        select(Budget).where(Budget.year == previous_year, Budget.month == previous_month)
    ).all()

    existing = {
        b.category_id for b in db.scalars(
            select(Budget).where(Budget.year == year, Budget.month == month)
        ).all()
    }

    created = 0
    for budget in source:
        if budget.category_id in existing:
            continue
        db.add(Budget(
            category_id=budget.category_id, year=year, month=month,
            amount_cents=budget.amount_cents, rollover=budget.rollover,
        ))
        created += 1
    db.commit()
    return {"copied": created}


@router.post("/suggest")
def suggest(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    months: int = Query(6, ge=2, le=24),
    db: Session = Depends(get_db),
):
    """Propose budgets from the last N periods' median spend.

    Median rather than mean: one holiday should not set the grocery budget for
    the year. Returns proposals; it does not write anything.
    """
    config = periods.load_config(db)
    labels = periods.recent_periods(months, config)

    categories = db.scalars(
        select(Category).where(Category.is_income.is_(False),
                               Category.excluded_from_budget.is_(False))
    ).all()

    proposals = []
    for category in categories:
        history = [_spent_cents(db, category.id, y, m, config) for y, m in labels]
        active = sorted(v for v in history if v > 0)
        if len(active) < 2:
            continue
        middle = len(active) // 2
        median = active[middle] if len(active) % 2 else (active[middle - 1] + active[middle]) // 2
        proposals.append({
            "category_id": category.id,
            "category_name": category.name,
            "suggested": round(median / 100, 2),
            "months_with_spend": len(active),
        })

    proposals.sort(key=lambda p: p["suggested"], reverse=True)
    return {"year": year, "month": month, "based_on_months": months, "proposals": proposals}
