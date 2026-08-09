"""Splitting one transaction across categories.

A salary is one bank line but several things at once: base pay plus travel and
working-from-home allowances. The bank cannot tell them apart, so you record
the parts here — and the parts, not the lump sum, are what category reporting
uses from then on.

The parts must add up to the transaction exactly. A split that does not
reconcile is worse than no split, because every total built on it would be
quietly wrong and nothing would say so.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Transaction, TransactionSplit

router = APIRouter(prefix="/splits", tags=["splits"])

MAX_PARTS = 20


class SplitPart(BaseModel):
    category_id: Optional[int] = None
    amount: float
    note: Optional[str] = Field(None, max_length=200)


class SplitIn(BaseModel):
    parts: list[SplitPart] = Field(default_factory=list, max_length=MAX_PARTS)


def _serialise(tx: Transaction) -> dict:
    return {
        "transaction_id": tx.id,
        "amount": tx.amount_cents / 100,
        "description": tx.description,
        "booked_on": tx.booked_on.isoformat(),
        "parts": [
            {
                "id": part.id,
                "category_id": part.category_id,
                "category_name": part.category.name if part.category else None,
                "variable_income": part.category.variable_income if part.category else False,
                "amount": part.amount_cents / 100,
                "note": part.note,
            }
            for part in tx.splits
        ],
    }


@router.get("/{transaction_id}")
def get_split(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(404, "Transactie niet gevonden.")
    return _serialise(tx)


@router.put("/{transaction_id}")
def set_split(transaction_id: int, payload: SplitIn, db: Session = Depends(get_db)):
    """Replace the split. An empty list removes it and the transaction falls
    back to its single category."""
    tx = db.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(404, "Transactie niet gevonden.")

    if not payload.parts:
        tx.splits.clear()
        db.commit()
        return _serialise(tx)

    if len(payload.parts) < 2:
        raise HTTPException(422, "Een verdeling heeft minstens twee delen nodig.")

    cents = [int(round(part.amount * 100)) for part in payload.parts]
    if any(value == 0 for value in cents):
        raise HTTPException(422, "Een deel mag niet € 0,00 zijn.")
    if any((value > 0) != (tx.amount_cents > 0) for value in cents):
        raise HTTPException(
            422, "Alle delen moeten dezelfde richting hebben als de transactie."
        )

    total = sum(cents)
    if total != tx.amount_cents:
        difference = (tx.amount_cents - total) / 100
        raise HTTPException(
            422,
            f"De delen tellen op tot € {total / 100:.2f} maar de transactie is "
            f"€ {tx.amount_cents / 100:.2f}. Er ontbreekt € {difference:.2f}.",
        )

    known = {c.id for c in db.scalars(select(Category)).all()}
    for part in payload.parts:
        if part.category_id is not None and part.category_id not in known:
            raise HTTPException(422, "Onbekende categorie in de verdeling.")

    tx.splits.clear()
    db.flush()
    for part, value in zip(payload.parts, cents):
        tx.splits.append(TransactionSplit(
            category_id=part.category_id, amount_cents=value, note=part.note
        ))

    # A split transaction no longer has one category, and leaving a stale one
    # behind would make the two disagree.
    tx.category_id = None
    tx.category_locked = True
    db.commit()
    return _serialise(tx)


@router.delete("/{transaction_id}")
def clear_split(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(404, "Transactie niet gevonden.")
    tx.splits.clear()
    tx.category_locked = False
    db.commit()
    return _serialise(tx)
