"""Categories and the rules that assign them."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Rule, Transaction
from ..services import importer

router = APIRouter(tags=["categories"])


# ─── categories ─────────────────────────────────────────────────────────────

class CategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    color: str = Field("#64748b", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: Optional[str] = Field(None, max_length=40)
    parent_id: Optional[int] = None
    is_income: bool = False
    excluded_from_budget: bool = False
    sort_order: int = 100


@router.get("/categories/")
def list_categories(db: Session = Depends(get_db)):
    counts = dict(db.execute(
        select(Transaction.category_id, func.count()).group_by(Transaction.category_id)
    ).all())
    categories = db.scalars(select(Category).order_by(Category.sort_order, Category.name)).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "color": c.color,
            "icon": c.icon,
            "is_income": c.is_income,
            "excluded_from_budget": c.excluded_from_budget,
            "sort_order": c.sort_order,
            "transaction_count": counts.get(c.id, 0),
        }
        for c in categories
    ]


@router.post("/categories/")
def create_category(payload: CategoryIn, db: Session = Depends(get_db)):
    if payload.parent_id is not None and db.get(Category, payload.parent_id) is None:
        raise HTTPException(422, "Bovenliggende categorie bestaat niet.")
    exists = db.scalar(select(Category).where(
        Category.name == payload.name, Category.parent_id == payload.parent_id
    ))
    if exists is not None:
        raise HTTPException(409, "Er bestaat al een categorie met deze naam.")

    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    return {"id": category.id}


@router.put("/categories/{category_id}")
def update_category(category_id: int, payload: CategoryIn, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Categorie niet gevonden.")
    if payload.parent_id == category_id:
        raise HTTPException(422, "Een categorie kan niet haar eigen bovenliggende zijn.")
    for key, value in payload.model_dump().items():
        setattr(category, key, value)
    db.commit()
    return {"id": category.id}


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Deleting a category un-categorises its transactions; it never deletes
    them. The FK is ON DELETE SET NULL, so this is the database's behaviour
    rather than something the route has to remember."""
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Categorie niet gevonden.")
    affected = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.category_id == category_id)
    )
    db.delete(category)
    db.commit()
    return {"uncategorised": affected or 0}


# ─── rules ──────────────────────────────────────────────────────────────────

RuleField = Literal["any", "description", "counter_name", "counter_iban", "creditor_id", "bank_code"]
RuleOperator = Literal["contains", "equals", "startswith"]


class RuleIn(BaseModel):
    category_id: int
    value: str = Field(..., min_length=1, max_length=200)
    field: RuleField = "any"
    operator: RuleOperator = "contains"
    priority: int = Field(50, ge=1, le=10_000)
    active: bool = True
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    account_id: Optional[int] = None


def _cents(value: Optional[float]) -> Optional[int]:
    return None if value is None else int(round(value * 100))


@router.get("/rules/")
def list_rules(
    db: Session = Depends(get_db),
    category_id: Optional[int] = None,
    search: Optional[str] = Query(None, max_length=100),
):
    stmt = select(Rule).order_by(Rule.priority, Rule.id)
    if category_id:
        stmt = stmt.where(Rule.category_id == category_id)
    if search:
        stmt = stmt.where(Rule.value.ilike(f"%{search.strip()}%"))

    names = dict(db.execute(select(Category.id, Category.name)).all())
    return [
        {
            "id": r.id,
            "priority": r.priority,
            "active": r.active,
            "field": r.field,
            "operator": r.operator,
            "value": r.value,
            "amount_min": None if r.amount_min_cents is None else r.amount_min_cents / 100,
            "amount_max": None if r.amount_max_cents is None else r.amount_max_cents / 100,
            "account_id": r.account_id,
            "category_id": r.category_id,
            "category_name": names.get(r.category_id),
            "is_seed": r.is_seed,
        }
        for r in db.scalars(stmt).all()
    ]


@router.post("/rules/")
def create_rule(payload: RuleIn, db: Session = Depends(get_db)):
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(422, "Categorie bestaat niet.")
    rule = Rule(
        category_id=payload.category_id, value=payload.value.strip(), field=payload.field,
        operator=payload.operator, priority=payload.priority, active=payload.active,
        amount_min_cents=_cents(payload.amount_min), amount_max_cents=_cents(payload.amount_max),
        account_id=payload.account_id,
    )
    db.add(rule)
    db.commit()
    return {"id": rule.id}


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, payload: RuleIn, db: Session = Depends(get_db)):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(404, "Regel niet gevonden.")
    rule.category_id = payload.category_id
    rule.value = payload.value.strip()
    rule.field = payload.field
    rule.operator = payload.operator
    rule.priority = payload.priority
    rule.active = payload.active
    rule.amount_min_cents = _cents(payload.amount_min)
    rule.amount_max_cents = _cents(payload.amount_max)
    rule.account_id = payload.account_id
    db.commit()
    return {"id": rule.id}


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(404, "Regel niet gevonden.")
    db.delete(rule)
    db.commit()
    return {"deleted": rule_id}


@router.post("/rules/reapply")
def reapply(
    include_locked: bool = Query(False),
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Re-run all rules over the ledger.

    Hand-picked categories survive by default. `include_locked` overrides them
    and is only ever reached through an explicit confirmation in the UI, which
    first calls this with `dry_run` to show exactly how many manual choices
    would be replaced.
    """
    return importer.reapply_rules_to_all(
        db, include_locked=include_locked, dry_run=dry_run
    )
