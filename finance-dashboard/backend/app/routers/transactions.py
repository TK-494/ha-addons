from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from ..database import get_db
from ..models import Transaction, Category
from ..schemas import TransactionOut
from ..parsers.rabobank import parse_rabobank_csv

router = APIRouter(prefix="/transactions", tags=["transactions"])


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
    q = db.query(Transaction).options(joinedload(Transaction.category))
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
    return q.order_by(Transaction.date.desc()).offset(skip).limit(limit).all()


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
    records = parse_rabobank_csv(content)

    categories = {c.name: c for c in db.query(Category).all()}
    existing_hashes = {
        h for (h,) in db.query(Transaction.import_hash).all()
    }
    batch_hashes: set[str] = set()
    imported = 0
    skipped = 0

    for record in records:
        h = record["import_hash"]
        # Skip duplicates already in the DB AND duplicates within this same upload.
        # Without the in-batch check, two identical rows in one file (common with
        # zero-amount filler rows in Rabobank exports) both pass the DB lookup,
        # then commit() crashes with UNIQUE constraint failed: transactions.import_hash.
        if h in existing_hashes or h in batch_hashes:
            skipped += 1
            continue

        suggested = record.pop("suggested_category", None)
        cat_id = None
        if suggested and suggested in categories:
            cat_id = categories[suggested].id

        tx = Transaction(**{k: v for k, v in record.items() if k != "suggested_category"},
                         category_id=cat_id)
        db.add(tx)
        batch_hashes.add(h)
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped, "total": len(records)}
