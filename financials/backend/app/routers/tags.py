"""Labels — the second dimension next to categories.

A transaction has exactly one category (that is the accounting) and any number
of labels (those answer the cross-cutting questions). Labels never touch the
income/expense totals; they are a filter and a report, so no figure can be
double-counted by adding one.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, delete, func, insert, select
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import Category, Tag, Transaction, transaction_tags

router = APIRouter(prefix="/tags", tags=["tags"])


class TagIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    color: str = Field("#0ea5e9", pattern=r"^#[0-9a-fA-F]{6}$")
    note: Optional[str] = Field(None, max_length=200)


def _totals(db: Session):
    """Spend and count per label, in one query rather than one per label."""
    rows = db.execute(
        select(
            transaction_tags.c.tag_id,
            func.count(),
            func.coalesce(func.sum(Transaction.amount_cents), 0),
            func.min(Transaction.booked_on),
            func.max(Transaction.booked_on),
        )
        .select_from(transaction_tags)
        .join(Transaction, Transaction.id == transaction_tags.c.transaction_id)
        .group_by(transaction_tags.c.tag_id)
    ).all()
    return {r[0]: r[1:] for r in rows}


@router.get("/")
def list_tags(db: Session = Depends(get_db)):
    totals = _totals(db)
    tags = db.scalars(select(Tag).order_by(Tag.name)).all()
    return [
        {
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
            "note": tag.note,
            "transactions": totals.get(tag.id, (0, 0, None, None))[0],
            "total": totals.get(tag.id, (0, 0, None, None))[1] / 100,
            "first_seen": totals.get(tag.id, (0, 0, None, None))[2],
            "last_seen": totals.get(tag.id, (0, 0, None, None))[3],
        }
        for tag in tags
    ]


@router.post("/")
def create_tag(payload: TagIn, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if db.scalar(select(Tag).where(func.lower(Tag.name) == name.lower())) is not None:
        raise HTTPException(409, "Er bestaat al een label met deze naam.")
    tag = Tag(name=name, color=payload.color, note=payload.note)
    db.add(tag)
    db.commit()
    return {"id": tag.id, "name": tag.name}


@router.put("/{tag_id}")
def update_tag(tag_id: int, payload: TagIn, db: Session = Depends(get_db)):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "Label niet gevonden.")
    name = payload.name.strip()
    clash = db.scalar(
        select(Tag).where(func.lower(Tag.name) == name.lower(), Tag.id != tag_id)
    )
    if clash is not None:
        raise HTTPException(409, "Er bestaat al een label met deze naam.")
    tag.name = name
    tag.color = payload.color
    tag.note = payload.note
    db.commit()
    return {"id": tag.id}


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """Deleting a label never deletes transactions — it only removes the
    label from them."""
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "Label niet gevonden.")
    affected = db.scalar(
        select(func.count()).select_from(transaction_tags)
        .where(transaction_tags.c.tag_id == tag_id)
    ) or 0
    db.delete(tag)
    db.commit()
    return {"deleted": tag_id, "untagged_transactions": affected}


class TagAssignment(BaseModel):
    tag_ids: list[int] = Field(default_factory=list, max_length=50)


@router.put("/transaction/{transaction_id}")
def set_transaction_tags(
    transaction_id: int, payload: TagAssignment, db: Session = Depends(get_db)
):
    """Replace the full label set of one transaction."""
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(404, "Transactie niet gevonden.")

    wanted = set(payload.tag_ids)
    tags = db.scalars(select(Tag).where(Tag.id.in_(wanted))).all() if wanted else []
    if len(tags) != len(wanted):
        raise HTTPException(422, "Onbekend label opgegeven.")

    transaction.tags = list(tags)
    db.commit()
    return {"transaction_id": transaction_id, "tags": [t.id for t in tags]}


class BulkTag(BaseModel):
    transaction_ids: list[int] = Field(..., max_length=config.MAX_BULK_IDS)
    tag_id: int
    action: str = Field("add", pattern="^(add|remove)$")


@router.post("/bulk")
def bulk_tag(payload: BulkTag, db: Session = Depends(get_db)):
    """Label a whole selection at once — how a holiday actually gets tagged:
    filter the date range, select everything, apply the label."""
    if db.get(Tag, payload.tag_id) is None:
        raise HTTPException(422, "Label bestaat niet.")
    if not payload.transaction_ids:
        return {"changed": 0}

    changed = 0
    # Chunked: SQLite's default variable limit is 999.
    for start in range(0, len(payload.transaction_ids), 400):
        chunk = payload.transaction_ids[start:start + 400]
        existing = set(db.scalars(
            select(transaction_tags.c.transaction_id).where(
                transaction_tags.c.tag_id == payload.tag_id,
                transaction_tags.c.transaction_id.in_(chunk),
            )
        ).all())

        if payload.action == "add":
            # Only insert what is missing, so re-applying a label is a no-op
            # rather than a primary-key violation.
            missing = [
                {"transaction_id": tid, "tag_id": payload.tag_id}
                for tid in db.scalars(select(Transaction.id).where(Transaction.id.in_(chunk))).all()
                if tid not in existing
            ]
            if missing:
                db.execute(insert(transaction_tags), missing)
                changed += len(missing)
        else:
            if existing:
                db.execute(
                    delete(transaction_tags).where(
                        transaction_tags.c.tag_id == payload.tag_id,
                        transaction_tags.c.transaction_id.in_(list(existing)),
                    )
                )
                changed += len(existing)

    db.commit()
    return {"changed": changed}


@router.get("/{tag_id}/breakdown")
def breakdown(
    tag_id: int,
    db: Session = Depends(get_db),
    direction: Optional[str] = Query(None, pattern="^(in|out)$"),
):
    """What a label cost, split by category — the payoff of the whole idea:
    “Vakantie 2019” totalled X, of which fuel Y, hotels Z."""
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "Label niet gevonden.")

    base = (
        select(Transaction)
        .join(transaction_tags, transaction_tags.c.transaction_id == Transaction.id)
        .where(transaction_tags.c.tag_id == tag_id)
        .subquery()
    )

    stmt = (
        select(
            Category.id, Category.name, Category.color,
            func.coalesce(func.sum(base.c.amount_cents), 0),
            func.count(),
        )
        .select_from(base)
        .join(Category, Category.id == base.c.category_id, isouter=True)
        .group_by(Category.id)
        .order_by(func.abs(func.sum(base.c.amount_cents)).desc())
    )
    if direction == "out":
        stmt = stmt.where(base.c.amount_cents < 0)
    elif direction == "in":
        stmt = stmt.where(base.c.amount_cents > 0)

    rows = db.execute(stmt).all()

    # CASE, not SQLite's two-argument MIN/MAX: that scalar form is a SQLite
    # extension and would break on any other backend.
    negative = case((base.c.amount_cents < 0, base.c.amount_cents), else_=0)
    positive = case((base.c.amount_cents > 0, base.c.amount_cents), else_=0)
    spent, received = db.execute(
        select(
            func.coalesce(func.sum(negative), 0),
            func.coalesce(func.sum(positive), 0),
        ).select_from(base)
    ).one()

    return {
        "tag": {"id": tag.id, "name": tag.name, "color": tag.color, "note": tag.note},
        "spent": abs(spent or 0) / 100,
        "received": (received or 0) / 100,
        "net": ((spent or 0) + (received or 0)) / 100,
        "categories": [
            {
                "category_id": cid,
                "name": name or "Zonder categorie",
                "color": color or "#94a3b8",
                "amount": abs(total or 0) / 100,
                "transactions": count,
            }
            for cid, name, color, total, count in rows
        ],
    }
