from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from ..database import get_db
from ..models import Transaction, Category, UserSettings
from ..schemas import TransactionOut
from ..parsers import detect_bank, parse_bank_csv

router = APIRouter(prefix="/transactions", tags=["transactions"])


class BulkCategoryUpdate(BaseModel):
    transaction_ids: List[int]
    category_id: Optional[int] = None


def _apply_list_filters(q, year, month, category_id, search):
    """Shared filter logic between /transactions/ and /transactions/ids — keep
    them in lockstep so 'select all matching filter' selects exactly what the
    list view shows."""
    if year:
        q = q.filter(Transaction.date.between(f"{year}-01-01", f"{year}-12-31"))
    if month and year:
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        q = q.filter(Transaction.date.between(
            f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day}"
        ))
    if category_id is not None:
        q = q.filter(Transaction.category_id == category_id)
    if search:
        q = q.filter(
            Transaction.description.ilike(f"%{search}%") |
            Transaction.counter_name.ilike(f"%{search}%")
        )
    return q


OWN_IBANS_KEY = "own_ibans"


def _load_own_ibans(db: Session) -> set[str]:
    row = db.query(UserSettings).filter(UserSettings.key == OWN_IBANS_KEY).first()
    if not row or not row.value:
        return set()
    return {p.strip() for p in row.value.split(",") if p.strip()}


def _save_own_ibans(db: Session, ibans: set[str]) -> None:
    val = ",".join(sorted(ibans))
    row = db.query(UserSettings).filter(UserSettings.key == OWN_IBANS_KEY).first()
    if row:
        row.value = val
    else:
        db.add(UserSettings(key=OWN_IBANS_KEY, value=val))


@router.get("/own-accounts")
def list_own_accounts(db: Session = Depends(get_db)):
    return {"own_ibans": sorted(_load_own_ibans(db))}


@router.post("/own-accounts")
def add_own_account(iban: str, db: Session = Depends(get_db)):
    iban = iban.strip().upper().replace(" ", "")
    if not iban:
        raise HTTPException(status_code=400, detail="IBAN is empty")
    ibans = _load_own_ibans(db)
    ibans.add(iban)
    _save_own_ibans(db, ibans)
    # Backfill flag on any historical transactions to/from this IBAN.
    db.query(Transaction).filter(
        Transaction.counter_iban == iban,
        Transaction.is_transfer == False,  # noqa: E712 (SQLAlchemy)
    ).update({Transaction.is_transfer: True}, synchronize_session=False)
    db.commit()
    return {"own_ibans": sorted(ibans)}


@router.delete("/own-accounts")
def remove_own_account(iban: str, db: Session = Depends(get_db)):
    iban = iban.strip().upper().replace(" ", "")
    ibans = _load_own_ibans(db)
    ibans.discard(iban)
    _save_own_ibans(db, ibans)
    db.commit()
    return {"own_ibans": sorted(ibans)}


@router.get("/", response_model=List[TransactionOut])
def list_transactions(
    skip: int = 0,
    limit: int = 200,
    year: Optional[int] = None,
    month: Optional[int] = None,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = _apply_list_filters(
        db.query(Transaction).options(joinedload(Transaction.category)),
        year, month, category_id, search,
    )
    return q.order_by(Transaction.date.desc()).offset(skip).limit(limit).all()


@router.get("/ids")
def list_transaction_ids(
    year: Optional[int] = None,
    month: Optional[int] = None,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return just the IDs matching the same filter the list view uses.
    Used by the frontend's 'Select all matching filter' bulk-action button,
    which needs the full result set even when the visible page is capped."""
    q = _apply_list_filters(db.query(Transaction.id), year, month, category_id, search)
    return {"ids": [r[0] for r in q.all()]}


@router.post("/bulk-category")
def bulk_set_category(payload: BulkCategoryUpdate, db: Session = Depends(get_db)):
    if not payload.transaction_ids:
        return {"updated": 0}
    # Validate the category if one is provided — bare-id input from the UI.
    if payload.category_id is not None:
        if not db.query(Category).filter(Category.id == payload.category_id).first():
            raise HTTPException(status_code=404, detail="Category not found")
    updated = (
        db.query(Transaction)
        .filter(Transaction.id.in_(payload.transaction_ids))
        .update({Transaction.category_id: payload.category_id}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated, "category_id": payload.category_id}


@router.patch("/{transaction_id}/category")
def set_category(transaction_id: int, category_id: Optional[int], db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tx.category_id = category_id
    db.commit()
    return {"ok": True}


@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(tx)
    db.commit()
    return {"ok": True}


@router.post("/upload")
async def upload_bank_statement(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    bank = detect_bank(content)
    records = parse_bank_csv(content)

    # Every IBAN that ever appears as the *own* side of an imported statement
    # is, by definition, an account the user owns. Persist the union so that a
    # later import from account A can flag transfers TO account B (and vice
    # versa) as inter-account moves, not real income/expense.
    own_ibans = _load_own_ibans(db)
    own_ibans |= {r["own_iban"] for r in records if r.get("own_iban")}
    _save_own_ibans(db, own_ibans)

    categories = {c.name: c for c in db.query(Category).all()}
    existing_hashes = {
        h for (h,) in db.query(Transaction.import_hash).all()
    }
    batch_hashes: set[str] = set()
    imported = 0
    skipped = 0
    transfer_count = 0

    for record in records:
        h = record["import_hash"]
        # Skip duplicates already in the DB AND duplicates within this same upload.
        if h in existing_hashes or h in batch_hashes:
            skipped += 1
            continue

        suggested = record.pop("suggested_category", None)
        is_transfer = bool(record.get("counter_iban")) and record["counter_iban"] in own_ibans

        cat_id = None
        # Don't auto-categorize transfers — they shouldn't land in 'Boodschappen' etc.
        if not is_transfer and suggested and suggested in categories:
            cat_id = categories[suggested].id

        tx = Transaction(
            **{k: v for k, v in record.items() if k != "suggested_category"},
            category_id=cat_id,
            is_transfer=is_transfer,
        )
        db.add(tx)
        batch_hashes.add(h)
        imported += 1
        if is_transfer:
            transfer_count += 1

    # Re-flag historical rows: when account B was imported AFTER account A,
    # the A->B transfers in A's statement were stored before B was known.
    if own_ibans:
        db.query(Transaction).filter(
            Transaction.counter_iban.in_(own_ibans),
            Transaction.is_transfer == False,  # noqa: E712
        ).update({Transaction.is_transfer: True}, synchronize_session=False)

    db.commit()
    return {
        "bank": bank,
        "imported": imported,
        "skipped": skipped,
        "total": len(records),
        "transfers_flagged_in_batch": transfer_count,
        "own_ibans": sorted(own_ibans),
    }
