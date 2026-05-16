from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract
from typing import List
from datetime import date

from ..database import get_db
from ..models import Budget, Transaction
from ..schemas import BudgetCreate, BudgetOut

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/", response_model=List[BudgetOut])
def list_budgets(
    year: int = None,
    month: int = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    year = year or today.year
    month = month or today.month
    return (
        db.query(Budget)
        .options(joinedload(Budget.category))
        .filter(Budget.year == year, Budget.month == month)
        .all()
    )


@router.post("/", response_model=BudgetOut)
def upsert_budget(budget: BudgetCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(Budget)
        .filter(
            Budget.category_id == budget.category_id,
            Budget.month == budget.month,
            Budget.year == budget.year,
        )
        .first()
    )
    if existing:
        existing.amount = budget.amount
        db.commit()
        db.refresh(existing)
        return existing
    db_budget = Budget(**budget.model_dump())
    db.add(db_budget)
    db.commit()
    db.refresh(db_budget)
    return db_budget


@router.delete("/{budget_id}")
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    b = db.query(Budget).filter(Budget.id == budget_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(b)
    db.commit()
    return {"ok": True}


@router.get("/progress")
def budget_progress(year: int = None, month: int = None, db: Session = Depends(get_db)):
    today = date.today()
    year = year or today.year
    month = month or today.month

    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    budgets = (
        db.query(Budget)
        .options(joinedload(Budget.category))
        .filter(Budget.year == year, Budget.month == month)
        .all()
    )

    result = []
    for b in budgets:
        spent = (
            db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.category_id == b.category_id,
                Transaction.date.between(start, end),
                Transaction.amount < 0,
            )
            .scalar()
            or 0.0
        )
        result.append({
            "budget_id": b.id,
            "category": b.category.name if b.category else "Onbekend",
            "color": b.category.color if b.category else "#94a3b8",
            "icon": b.category.icon if b.category else "💳",
            "budget": b.amount,
            "spent": abs(spent),
            "remaining": b.amount - abs(spent),
            "percent": min(round(abs(spent) / b.amount * 100, 1) if b.amount else 0, 100),
        })
    return result
