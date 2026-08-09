"""Accounts: the separation between them is the point (PLAN §11).

Every account keeps its own balance and its own history. `kind` decides how it
is read at household level — money moved to a `savings` account is saved, not
spent.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ACCOUNT_KINDS, Account, Transaction
from ..services import accounts as account_service
from ..services import transfers

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    kind: str | None = None
    include_in_networth: bool | None = None
    archived: bool | None = None

    def validated_kind(self) -> str | None:
        if self.kind is not None and self.kind not in ACCOUNT_KINDS:
            raise HTTPException(422, f"kind moet één van {ACCOUNT_KINDS} zijn.")
        return self.kind


def _serialise(db: Session, account: Account) -> dict:
    stats = db.execute(
        select(
            func.count(Transaction.id),
            func.min(Transaction.booked_on),
            func.max(Transaction.booked_on),
        ).where(Transaction.account_id == account.id)
    ).one()

    # The bank's own running balance on the newest transaction beats summing
    # 7000 amounts — and it reconciles against the statement by construction.
    latest = db.scalars(
        select(Transaction)
        .where(Transaction.account_id == account.id, Transaction.balance_after_cents.isnot(None))
        .order_by(Transaction.booked_on.desc(), Transaction.id.desc())
        .limit(1)
    ).first()
    if latest is not None:
        balance = latest.balance_after_cents
    else:
        balance = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0))
            .where(Transaction.account_id == account.id)
        )

    return {
        "id": account.id,
        "key": account.key,
        "label": account.label,
        "display_name": account.display_name,
        "kind": account.kind,
        "kind_auto": account.kind_auto,
        "iban": account.iban,
        "card_last4": account.card_last4,
        "product_name": account.product_name,
        "settlement_iban": account.settlement_iban,
        "currency": account.currency,
        "include_in_networth": account.include_in_networth,
        "archived": account.archived,
        "balance": (balance or 0) / 100,
        "transaction_count": stats[0],
        "first_transaction": stats[1].isoformat() if stats[1] else None,
        "last_transaction": stats[2].isoformat() if stats[2] else None,
    }


class AccountCreate(BaseModel):
    """Declare an account as yours before its CSV exists.

    Accounts are normally created by importing their export, which leaves a
    gap: money sent to an account you own but have not imported looks exactly
    like spending. Registering the IBAN here closes it — transfers to it are
    recognised immediately and flagged as awaiting the other side.
    """

    iban: str = Field(..., min_length=8, max_length=40)
    display_name: str | None = Field(default=None, max_length=120)
    kind: str = "checking"
    include_in_networth: bool = False


@router.post("/")
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    if payload.kind not in ACCOUNT_KINDS:
        raise HTTPException(422, f"kind moet één van {ACCOUNT_KINDS} zijn.")

    iban = payload.iban.replace(" ", "").upper()
    if db.scalar(select(Account).where(Account.key == iban)) is not None:
        raise HTTPException(409, "Deze rekening bestaat al.")

    account = Account(
        key=iban, iban=iban, kind=payload.kind,
        display_name=(payload.display_name or "").strip() or None,
        # An account with no imported transactions has no known balance, so it
        # would drag the net-worth total to a wrong number if counted.
        include_in_networth=payload.include_in_networth,
    )
    db.add(account)
    db.commit()

    stats = transfers.rematch_all(db)
    return {
        **_serialise(db, account),
        "rematched": {"pairs": stats.pairs_matched, "pending": stats.legs_pending},
    }


@router.get("/")
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.scalars(select(Account).order_by(Account.kind, Account.id)).all()
    return [_serialise(db, a) for a in accounts]


@router.patch("/{account_id}")
def update_account(account_id: int, payload: AccountUpdate, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(404, "Rekening niet gevonden.")

    kind = payload.validated_kind()
    if kind is not None:
        account.kind = kind
        # A hand-picked kind is final: automatic classification must never
        # overrule it on the next import.
        account.kind_auto = False
    if payload.display_name is not None:
        account.display_name = payload.display_name.strip() or None
    if payload.include_in_networth is not None:
        account.include_in_networth = payload.include_in_networth
    if payload.archived is not None:
        account.archived = payload.archived

    db.commit()
    return _serialise(db, account)


@router.post("/classify")
def classify(db: Session = Depends(get_db)):
    """Re-run savings detection over accounts you have not set by hand."""
    changed = account_service.classify_savings(db)
    return {
        "changed": [
            {"account_id": c.account_id, "label": c.label, "kind": c.kind, "reason": c.reason}
            for c in changed
        ]
    }


@router.post("/rematch-transfers")
def rematch(db: Session = Depends(get_db)):
    """Re-run internal transfer matching over the whole ledger."""
    stats = transfers.rematch_all(db)
    account_service.classify_savings(db)
    return {
        "pairs_matched": stats.pairs_matched,
        "legs_pending": stats.legs_pending,
        "settlements_matched": stats.settlements_matched,
    }
