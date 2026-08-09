"""Transaction list, filtering, categorisation and export."""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .. import config
from ..database import get_db
from ..models import Account, Category, Rule, Transaction, transaction_tags
from ..security import csv_safe
from ..services import categorize, transfers

router = APIRouter(prefix="/transactions", tags=["transactions"])

SortField = Literal["date", "amount", "description"]


def _apply_filters(
    stmt,
    *,
    date_from: Optional[date],
    date_to: Optional[date],
    account_id: Optional[int],
    category_id: Optional[int],
    uncategorised: bool,
    internal: Optional[bool],
    direction: Optional[str],
    amount_min: Optional[float],
    amount_max: Optional[float],
    search: Optional[str],
    bank_code: Optional[str],
    tag_id: Optional[int] = None,
):
    if date_from:
        stmt = stmt.where(Transaction.booked_on >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.booked_on <= date_to)
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if uncategorised:
        stmt = stmt.where(Transaction.category_id.is_(None), Transaction.is_internal.is_(False))
    if internal is not None:
        stmt = stmt.where(Transaction.is_internal.is_(internal))
    if direction == "in":
        stmt = stmt.where(Transaction.amount_cents > 0)
    elif direction == "out":
        stmt = stmt.where(Transaction.amount_cents < 0)
    if amount_min is not None:
        stmt = stmt.where(func.abs(Transaction.amount_cents) >= int(round(amount_min * 100)))
    if amount_max is not None:
        stmt = stmt.where(func.abs(Transaction.amount_cents) <= int(round(amount_max * 100)))
    if bank_code:
        stmt = stmt.where(Transaction.bank_code == bank_code.lower())
    if tag_id:
        stmt = stmt.where(
            Transaction.id.in_(
                select(transaction_tags.c.transaction_id)
                .where(transaction_tags.c.tag_id == tag_id)
            )
        )
    if search:
        # SQLAlchemy binds the pattern as a parameter; the f-string only builds
        # the LIKE wildcards, never SQL.
        needle = f"%{search.strip()}%"
        stmt = stmt.where(or_(
            Transaction.description.ilike(needle),
            Transaction.counter_name.ilike(needle),
            Transaction.counter_iban.ilike(needle),
        ))
    return stmt


def _serialise(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "account_id": tx.account_id,
        "account_label": tx.account.label if tx.account else None,
        "booked_on": tx.booked_on.isoformat(),
        "amount": tx.amount_cents / 100,
        "balance_after": None if tx.balance_after_cents is None else tx.balance_after_cents / 100,
        "description": tx.description,
        "counter_name": tx.counter_name,
        "counter_iban": tx.counter_iban,
        "bank_code": tx.bank_code,
        "creditor_id": tx.creditor_id,
        "category_id": tx.category_id,
        "category_name": tx.category.name if tx.category else None,
        "category_color": tx.category.color if tx.category else None,
        "category_locked": tx.category_locked,
        "is_internal": tx.is_internal,
        "transfer_group": tx.transfer_group,
        "transfer_pending": tx.transfer_pending,
        "fx_amount": None if tx.fx_amount_cents is None else tx.fx_amount_cents / 100,
        "fx_currency": tx.fx_currency,
        "fx_rate": tx.fx_rate,
        "note": tx.note,
        "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in tx.tags],
    }


@router.get("/")
def list_transactions(
    db: Session = Depends(get_db),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    uncategorised: bool = False,
    internal: Optional[bool] = None,
    direction: Optional[Literal["in", "out"]] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    search: Optional[str] = Query(None, max_length=120),
    bank_code: Optional[str] = Query(None, max_length=10),
    tag_id: Optional[int] = None,
    sort: SortField = "date",
    desc: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=config.MAX_PAGE_SIZE),
):
    """Server-side pagination — 10k rows must never be shipped to the browser."""
    filters = dict(
        date_from=date_from, date_to=date_to, account_id=account_id,
        category_id=category_id, uncategorised=uncategorised, internal=internal,
        direction=direction, amount_min=amount_min, amount_max=amount_max,
        search=search, bank_code=bank_code, tag_id=tag_id,
    )

    total = db.scalar(_apply_filters(select(func.count()).select_from(Transaction), **filters))
    # CASE rather than SQLite's two-argument MAX(): the scalar form is a
    # SQLite extension and would break on any other backend.
    positive = case((Transaction.amount_cents > 0, Transaction.amount_cents), else_=0)
    negative = case((Transaction.amount_cents < 0, Transaction.amount_cents), else_=0)
    sums = db.execute(_apply_filters(
        select(
            func.coalesce(func.sum(positive), 0),
            func.coalesce(func.sum(negative), 0),
        ).select_from(Transaction),
        **filters,
    )).one()

    order = {
        "date": Transaction.booked_on,
        "amount": Transaction.amount_cents,
        "description": Transaction.description,
    }[sort]
    order = order.desc() if desc else order.asc()

    stmt = _apply_filters(select(Transaction), **filters)
    stmt = (
        stmt.options(selectinload(Transaction.account), selectinload(Transaction.category))
        .order_by(order, Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "sum_in": (sums[0] or 0) / 100,
        "sum_out": (sums[1] or 0) / 100,
        "items": [_serialise(tx) for tx in db.scalars(stmt).all()],
    }


@router.get("/ids")
def matching_ids(
    db: Session = Depends(get_db),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    uncategorised: bool = False,
    internal: Optional[bool] = None,
    direction: Optional[Literal["in", "out"]] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    search: Optional[str] = Query(None, max_length=120),
    bank_code: Optional[str] = Query(None, max_length=10),
    tag_id: Optional[int] = None,
):
    """Every id matching the current filter, so "select all" can mean all
    matching rows rather than just the visible page.

    Capped at MAX_BULK_IDS, which is also the ceiling on the bulk endpoints —
    a selection that cannot be acted on is not worth returning.
    """
    stmt = _apply_filters(
        select(Transaction.id),
        date_from=date_from, date_to=date_to, account_id=account_id,
        category_id=category_id, uncategorised=uncategorised, internal=internal,
        direction=direction, amount_min=amount_min, amount_max=amount_max,
        search=search, bank_code=bank_code, tag_id=tag_id,
    ).limit(config.MAX_BULK_IDS + 1)

    ids = list(db.scalars(stmt).all())
    truncated = len(ids) > config.MAX_BULK_IDS
    return {
        "ids": ids[:config.MAX_BULK_IDS],
        "truncated": truncated,
        "limit": config.MAX_BULK_IDS,
    }


class CategoryAssign(BaseModel):
    category_id: Optional[int] = None


@router.patch("/{tx_id}/category")
def set_category(tx_id: int, payload: CategoryAssign, db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(404, "Transactie niet gevonden.")
    if payload.category_id is not None and db.get(Category, payload.category_id) is None:
        raise HTTPException(422, "Categorie bestaat niet.")

    tx.category_id = payload.category_id
    # A hand-picked category is pinned: rule re-runs must not undo it.
    tx.category_locked = payload.category_id is not None
    db.commit()
    return _serialise(tx)


class BulkCategory(BaseModel):
    transaction_ids: list[int] = Field(..., max_length=config.MAX_BULK_IDS)
    category_id: Optional[int] = None


@router.post("/bulk-category")
def bulk_category(payload: BulkCategory, db: Session = Depends(get_db)):
    if not payload.transaction_ids:
        return {"updated": 0}
    if payload.category_id is not None and db.get(Category, payload.category_id) is None:
        raise HTTPException(422, "Categorie bestaat niet.")

    updated = 0
    # Chunked: SQLite's default variable limit is 999.
    for start in range(0, len(payload.transaction_ids), 500):
        chunk = payload.transaction_ids[start:start + 500]
        for tx in db.scalars(select(Transaction).where(Transaction.id.in_(chunk))).all():
            tx.category_id = payload.category_id
            tx.category_locked = payload.category_id is not None
            updated += 1
    db.commit()
    return {"updated": updated}


class RuleFromTransaction(BaseModel):
    category_id: int
    field: Literal["any", "description", "counter_name", "counter_iban", "creditor_id"] = "counter_name"
    value: str = Field(..., min_length=2, max_length=200)
    apply_to_existing: bool = True
    overwrite_locked: bool = False


@router.get("/{tx_id}/rule-preview")
def rule_preview(
    tx_id: int,
    field: str = Query("counter_name"),
    value: str = Query(..., min_length=2, max_length=200),
    db: Session = Depends(get_db),
):
    """How many rows a proposed rule would touch — shown *before* it is
    created, so "categorise everything like this" is never a blind action."""
    if db.get(Transaction, tx_id) is None:
        raise HTTPException(404, "Transactie niet gevonden.")

    column = {
        "description": Transaction.description,
        "counter_name": Transaction.counter_name,
        "counter_iban": Transaction.counter_iban,
        "creditor_id": Transaction.creditor_id,
    }.get(field)

    needle = f"%{value.strip()}%"
    if column is None:
        condition = or_(
            Transaction.description.ilike(needle), Transaction.counter_name.ilike(needle)
        )
    else:
        condition = column.ilike(needle)

    total = db.scalar(select(func.count()).select_from(Transaction).where(condition))
    locked = db.scalar(
        select(func.count()).select_from(Transaction)
        .where(condition, Transaction.category_locked.is_(True))
    )
    return {"matches": total or 0, "locked": locked or 0}


@router.post("/{tx_id}/rule")
def create_rule_from_transaction(
    tx_id: int, payload: RuleFromTransaction, db: Session = Depends(get_db)
):
    """Turn "categorise this and everything like it" into a stored rule."""
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(404, "Transactie niet gevonden.")
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(422, "Categorie bestaat niet.")

    # Priority 1: a rule the user wrote by hand outranks every seeded keyword.
    rule = Rule(
        priority=1, field=payload.field, operator="contains",
        value=payload.value.strip(), category_id=payload.category_id, is_seed=False,
    )
    db.add(rule)
    db.commit()

    updated = 0
    if payload.apply_to_existing:
        rules = categorize.compile_rules(db)
        everything = db.scalars(select(Transaction)).all()
        updated = categorize.apply_rules(
            db, everything, rules, overwrite_locked=payload.overwrite_locked
        )
        db.commit()

    return {"rule_id": rule.id, "updated": updated}


class NoteUpdate(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)


@router.patch("/{tx_id}/note")
def set_note(tx_id: int, payload: NoteUpdate, db: Session = Depends(get_db)):
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(404, "Transactie niet gevonden.")
    tx.note = (payload.note or "").strip() or None
    db.commit()
    return _serialise(tx)


class LinkRequest(BaseModel):
    other_id: int


@router.post("/{tx_id}/link-transfer")
def link_transfer(tx_id: int, payload: LinkRequest, db: Session = Depends(get_db)):
    try:
        group = transfers.link_manually(db, tx_id, payload.other_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"transfer_group": group}


@router.delete("/transfer-group/{group}")
def unlink_transfer(group: str, db: Session = Depends(get_db)):
    count = transfers.unlink(db, group)
    if count == 0:
        raise HTTPException(404, "Koppeling niet gevonden.")
    return {"unlinked": count}


@router.get("/export")
def export_csv(
    db: Session = Depends(get_db),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    search: Optional[str] = Query(None, max_length=120),
    tag_id: Optional[int] = None,
):
    """Export the current selection. Every cell goes through `csv_safe`, so a
    merchant name starting with `=` cannot become a formula in Excel."""
    stmt = _apply_filters(
        select(Transaction), date_from=date_from, date_to=date_to,
        account_id=account_id, category_id=category_id, uncategorised=False,
        internal=None, direction=None, amount_min=None, amount_max=None,
        search=search, bank_code=None, tag_id=tag_id,
    ).options(selectinload(Transaction.account), selectinload(Transaction.category)) \
     .order_by(Transaction.booked_on.desc()).limit(100_000)

    def rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow([
            "Datum", "Rekening", "Bedrag", "Omschrijving", "Tegenpartij",
            "Tegenrekening", "Categorie", "Labels", "Intern", "Notitie",
        ])
        yield buffer.getvalue()
        buffer.seek(0), buffer.truncate(0)

        for tx in db.scalars(stmt).yield_per(500):
            writer.writerow([
                tx.booked_on.isoformat(),
                csv_safe(tx.account.label if tx.account else ""),
                f"{tx.amount_cents / 100:.2f}".replace(".", ","),
                csv_safe(tx.description),
                csv_safe(tx.counter_name),
                csv_safe(tx.counter_iban),
                csv_safe(tx.category.name if tx.category else ""),
                csv_safe(", ".join(tag.name for tag in tx.tags)),
                "ja" if tx.is_internal else "nee",
                csv_safe(tx.note or ""),
            ])
            yield buffer.getvalue()
            buffer.seek(0), buffer.truncate(0)

    return StreamingResponse(
        rows(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="transacties.csv"'},
    )
