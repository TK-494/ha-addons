"""Work out what kind of account each one is.

Nothing in a Dutch bank CSV says "this is a savings account", so every import
used to land as a current account. That quietly broke the *Gespaard* figure:
it only counts accounts marked as savings, so it read €0,00 forever unless the
user happened to find the setting on the Rekeningen page and change it by hand.
A number that requires a hidden step to become true is worse than no number.

The data settles it without asking. A savings account has no card payments, no
iDEAL, no direct debits — money only moves between it and your other accounts.
A current account has thousands of all three.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..models import Account, Transaction

log = logging.getLogger("financials.accounts")

# Codes that mean someone spent money in the real world: card terminals, ATMs,
# iDEAL, and collected direct debits. Rabobank and ASN spellings both included.
#
# `db` is deliberately absent. It looks like "doorlopende incasso" and is not:
# Rabobank uses it for *diverse boekingen* — bank charges and plain internal
# bookings. In this dataset all 1,989 `db` rows carry no creditor id at all,
# while every one of the 1,679 real direct debits is coded `ei`. Including `db`
# disqualified a savings account whose every single row is coded `db`.
SPENDING_CODES = {"bc", "ba", "bea", "ga", "gb", "id", "ide", "ei", "ec", "ios", "ioi", "eic"}

# Enough rows to be evidence rather than coincidence.
MIN_TRANSACTIONS = 15
# A savings account's traffic is almost entirely to and from your own accounts.
MIN_INTERNAL_SHARE = 0.8


@dataclass
class Classification:
    account_id: int
    label: str
    kind: str
    reason: str


def classify_savings(db: Session) -> list[Classification]:
    """Mark obvious savings accounts. Only touches accounts still carrying the
    app's own guess (`kind_auto`), so a manual choice is never overridden."""
    changed: list[Classification] = []

    candidates = db.scalars(
        select(Account).where(
            Account.kind_auto.is_(True),
            Account.card_last4.is_(None),   # a card is never a savings account
        )
    ).all()

    for account in candidates:
        total, spending, internal, has_creditor = db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(
                    case((Transaction.bank_code.in_(SPENDING_CODES), 1), else_=0)
                ), 0),
                func.coalesce(func.sum(
                    case((Transaction.is_internal.is_(True), 1), else_=0)
                ), 0),
                func.coalesce(func.sum(
                    case((Transaction.creditor_id != "", 1), else_=0)
                ), 0),
            ).where(Transaction.account_id == account.id)
        ).one()

        if total < MIN_TRANSACTIONS:
            continue
        if spending or has_creditor:
            continue  # somebody paid for something from here: current account
        if internal / total < MIN_INTERNAL_SHARE:
            continue

        if account.kind != "savings":
            account.kind = "savings"
            changed.append(Classification(
                account_id=account.id,
                label=account.label,
                kind="savings",
                reason=(
                    f"{total} transacties, geen pinbetalingen of incasso's, "
                    f"{round(100 * internal / total)}% eigen overboekingen"
                ),
            ))

    if changed:
        db.commit()
        for item in changed:
            log.info("Rekening herkend als spaarrekening: %s (%s)", item.label, item.reason)
    return changed
