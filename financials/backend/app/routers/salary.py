"""The salary page.

Your pay is one bank line that is several things: base pay plus travel and
working-from-home allowances. Splitting it matters because the base is what you
can build commitments on and the allowances are not — but doing that from the
transaction list means hunting one row among ten thousand, every month.

So the payments get their own page, with the previous month's division offered
as a template. The fixed parts almost never change; what changes is the
allowance, and that is exactly the part worth seeing move.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Transaction, TransactionSplit
from ..services import periods

router = APIRouter(prefix="/salary", tags=["salary"])


def _payment(tx: Transaction) -> dict:
    parts = [
        {
            "category_id": part.category_id,
            "category_name": part.category.name if part.category else None,
            "variable": bool(part.category and part.category.variable_income),
            "amount": part.amount_cents / 100,
            "note": part.note,
        }
        for part in tx.splits
    ]
    fixed = sum(p["amount"] for p in parts if not p["variable"])
    variable = sum(p["amount"] for p in parts if p["variable"])

    return {
        "transaction_id": tx.id,
        "date": tx.booked_on.isoformat(),
        "amount": tx.amount_cents / 100,
        "counter_name": tx.counter_name,
        "description": tx.description,
        "split": bool(parts),
        "parts": parts,
        # An unsplit payment counts wholly as fixed, which is the honest
        # default: nothing says otherwise yet.
        "fixed": fixed if parts else tx.amount_cents / 100,
        "variable": variable if parts else 0.0,
    }


def _overview(db: Session, limit: int = 24) -> dict:
    """Plain function, not the route.

    Calling a FastAPI endpoint directly hands it the `Query(...)` object as the
    default instead of the number, which then travels into SQLAlchemy and
    fails somewhere far away from the cause.
    """
    config = periods.load_config(db)
    source = config.salary

    if not source.configured:
        return {
            "configured": False,
            "source": None,
            "payments": [],
            "summary": None,
            "template": None,
            "suggestions": periods.propose_salary_source(db),
        }

    stmt = (
        select(Transaction)
        .where(
            Transaction.amount_cents >= source.min_amount_cents,
            Transaction.is_internal.is_(False),
            Transaction.counter_name.ilike(f"%{source.counterparty.strip()}%"),
        )
        .order_by(Transaction.booked_on.desc())
        .limit(limit)
    )
    if source.account_id:
        stmt = stmt.where(Transaction.account_id == source.account_id)

    payments = [_payment(tx) for tx in db.scalars(stmt).all()]
    split_payments = [p for p in payments if p["split"]]

    summary = None
    if payments:
        recent = payments[:12]
        summary = {
            "count": len(payments),
            "average": round(sum(p["amount"] for p in recent) / len(recent), 2),
            "average_fixed": round(sum(p["fixed"] for p in recent) / len(recent), 2),
            "average_variable": round(sum(p["variable"] for p in recent) / len(recent), 2),
            "split_count": len(split_payments),
            "unsplit_count": len(payments) - len(split_payments),
            "highest": max(p["amount"] for p in payments),
            "lowest": min(p["amount"] for p in payments),
        }

    # The most recent division doubles as the template for the next one.
    template = None
    if split_payments:
        latest = split_payments[0]
        template = {
            "from_date": latest["date"],
            "parts": [
                {
                    "category_id": part["category_id"],
                    "category_name": part["category_name"],
                    "variable": part["variable"],
                    "amount": part["amount"],
                }
                for part in latest["parts"]
            ],
        }

    return {
        "configured": True,
        "source": {
            "counterparty": source.counterparty,
            "min_amount": source.min_amount_cents / 100,
            "account_id": source.account_id,
        },
        "payments": payments,
        "summary": summary,
        "template": template,
        "income_categories": [
            {
                "id": c.id, "name": c.name, "color": c.color,
                "variable_income": c.variable_income,
            }
            for c in db.scalars(
                select(Category).where(Category.is_income.is_(True)).order_by(Category.name)
            ).all()
        ],
    }


@router.get("/")
def salary_overview(
    db: Session = Depends(get_db),
    limit: int = Query(24, ge=1, le=120),
):
    return _overview(db, limit)


class ApplyTemplate(BaseModel):
    transaction_id: int
    # Which part absorbs the difference. Left empty, the single variable
    # category takes it.
    remainder_category_id: Optional[int] = None


@router.post("/apply-template")
def apply_template(payload: ApplyTemplate, db: Session = Depends(get_db)):
    """Copy the previous division onto this payment.

    The fixed parts are carried over verbatim, because base pay is what stays
    the same. Whatever is left over lands on the variable part — that is where
    the month-to-month difference actually is, and forcing the user to
    recalculate it by hand would be busywork with a rounding error attached.
    """
    tx = db.get(Transaction, payload.transaction_id)
    if tx is None:
        raise HTTPException(404, "Transactie niet gevonden.")

    overview = _overview(db)
    template = overview.get("template")
    if not template:
        raise HTTPException(422, "Er is nog geen eerdere verdeling om over te nemen.")
    fixed_parts = [p for p in template["parts"] if not p["variable"]]
    variable_parts = [p for p in template["parts"] if p["variable"]]

    remainder_id = payload.remainder_category_id
    if remainder_id is None:
        if len(variable_parts) == 1:
            remainder_id = variable_parts[0]["category_id"]
        elif variable_parts:
            raise HTTPException(
                422,
                "Er zijn meerdere variabele delen; geef aan welk deel het verschil opvangt.",
            )

    fixed_cents = sum(int(round(p["amount"] * 100)) for p in fixed_parts)
    remainder = tx.amount_cents - fixed_cents

    if remainder == 0:
        parts = [(p["category_id"], int(round(p["amount"] * 100))) for p in fixed_parts]
    elif remainder_id is None:
        raise HTTPException(
            422,
            "Het bedrag wijkt af van de vaste delen en er is geen variabel deel om het verschil "
            "in te plaatsen.",
        )
    elif (remainder > 0) != (tx.amount_cents > 0):
        raise HTTPException(
            422,
            f"De vaste delen (€ {fixed_cents / 100:.2f}) zijn samen groter dan deze betaling "
            f"(€ {tx.amount_cents / 100:.2f}); pas de verdeling handmatig aan.",
        )
    else:
        parts = [(p["category_id"], int(round(p["amount"] * 100))) for p in fixed_parts]
        parts.append((remainder_id, remainder))

    if len(parts) < 2:
        raise HTTPException(422, "Een verdeling heeft minstens twee delen nodig.")

    tx.splits.clear()
    db.flush()
    for category_id, cents in parts:
        tx.splits.append(TransactionSplit(category_id=category_id, amount_cents=cents))
    tx.category_id = None
    tx.category_locked = True
    db.commit()

    return _payment(tx)
