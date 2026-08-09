"""Internal transfer matching (PLAN §11).

The problem: moving €200 from Rabobank to ASN produces two real transactions.
Counted naively that is €200 of expenses *and* €200 of income, which makes the
savings rate meaningless. Deleting one side is worse — the account balances
then stop reconciling against the bank's own `Saldo na trn`.

So: link, never delete. Both legs keep existing, keep belonging to their own
account and keep moving that account's balance. They gain a shared
`transfer_group` and `is_internal = True`, and only the *household-level*
income/expense/savings figures skip them. Per-account views still show them,
because from that account's side the money genuinely moved.

Matching re-runs over the whole table after every import, not just over the
new rows. That is deliberate: an IBAN only becomes "one of yours" once its own
CSV has been imported, so a Rabobank→ASN transfer from before the ASN export
existed looks like ordinary spend until the ASN file arrives. Re-running is
what lets those pair up retroactively.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Transaction

# Bank booking dates for the two legs rarely differ by more than a day, but a
# weekend can stretch it. Three days is wide enough for a Friday→Monday
# transfer and narrow enough that two unrelated round-number payments between
# the same pair of accounts don't get glued together.
MATCH_WINDOW_DAYS = 3


# A card statement is collected from the current account a few days after the
# card books it, so this window is wider than the IBAN-to-IBAN one.
SETTLEMENT_WINDOW_DAYS = 6

# Rabobank codes the credit-card collection `cc`. Description keywords are the
# fallback for banks that don't, and for the card side of the pair.
SETTLEMENT_BANK_CODES = {"cc"}
SETTLEMENT_KEYWORDS = (
    "verrekening", "overboeking naar creditcard", "creditcard",
    "betaling ontvangen", "payment received", "incasso creditcard",
)


@dataclass
class MatchStats:
    pairs_matched: int = 0
    legs_pending: int = 0
    legs_cleared: int = 0
    settlements_matched: int = 0


def _clear_auto_category(tx: Transaction) -> None:
    """Drop an automatically assigned category when a transaction turns out to
    be an internal transfer — but never a category the user set by hand.

    A machine guess may be replaced by a better machine guess. A human decision
    may not be undone by one, silently or otherwise.
    """
    if not tx.category_locked:
        tx.category_id = None


def _normalise(iban: str) -> str:
    return iban.replace(" ", "").upper()


def rematch_all(db: Session) -> MatchStats:
    """Recompute internal-transfer state for every transaction.

    Manual links (`transfer_manual`) are never touched — the matcher proposes,
    the user overrides, and the override wins on every subsequent run.
    """
    accounts = db.scalars(select(Account)).all()
    own_ibans = {_normalise(a.iban): a.id for a in accounts if a.iban}
    iban_by_account = {a.id: _normalise(a.iban) for a in accounts if a.iban}

    stats = MatchStats()

    transactions = db.scalars(
        select(Transaction).where(Transaction.transfer_manual.is_(False))
    ).all()

    # Reset the automatic verdict before recomputing, so a leg that stops
    # qualifying (account removed, IBAN corrected) doesn't stay marked.
    for tx in transactions:
        if tx.is_internal:
            stats.legs_cleared += 1
        tx.is_internal = False
        tx.transfer_group = None
        tx.transfer_pending = False

    # Index credit legs by (receiving account IBAN, paying IBAN, amount) so
    # each debit leg is one dict lookup rather than a scan of 10k rows.
    index: dict[tuple[str, str, int], list[Transaction]] = defaultdict(list)
    candidates = []
    for tx in transactions:
        own = iban_by_account.get(tx.account_id)
        counter = _normalise(tx.counter_iban)
        if not own or not counter or counter == own or counter not in own_ibans:
            continue
        candidates.append(tx)
        if tx.amount_cents > 0:
            index[(own, counter, tx.amount_cents)].append(tx)

    used: set[int] = set()

    for tx in candidates:
        if tx.amount_cents >= 0:
            continue  # drive the pairing from the paying side
        own = iban_by_account[tx.account_id]
        counter = _normalise(tx.counter_iban)

        # The mirror leg: on the receiving account, paid by this account,
        # for exactly the opposite amount.
        partners = index.get((counter, own, -tx.amount_cents), [])
        best = None
        best_gap = None
        for partner in partners:
            if partner.id in used:
                continue
            gap = abs((partner.booked_on - tx.booked_on).days)
            if gap > MATCH_WINDOW_DAYS:
                continue
            if best_gap is None or gap < best_gap:
                best, best_gap = partner, gap

        if best is not None:
            group = uuid.uuid4().hex
            for leg in (tx, best):
                leg.is_internal = True
                leg.transfer_group = group
                leg.transfer_pending = False
                # An internal transfer is not spending, so a spend category the
                # rules guessed for it is simply wrong. A category *you* chose
                # is left exactly where it is.
                _clear_auto_category(leg)
            used.add(best.id)
            used.add(tx.id)
            stats.pairs_matched += 1

    # Whatever is left points at one of your own accounts but has no partner
    # in the database. It is still a transfer — the counter-IBAN proves that —
    # so it stays out of spend, but it is flagged rather than silently netted.
    for tx in candidates:
        if tx.id in used:
            continue
        tx.is_internal = True
        tx.transfer_pending = True
        _clear_auto_category(tx)
        stats.legs_pending += 1

    _match_card_settlements(db, accounts, transactions, used, stats)

    db.commit()
    return stats


def _looks_like_settlement(tx: Transaction) -> bool:
    if tx.bank_code in SETTLEMENT_BANK_CODES:
        return True
    haystack = f"{tx.description} {tx.counter_name}".lower()
    return any(word in haystack for word in SETTLEMENT_KEYWORDS)


def _match_card_settlements(
    db: Session,
    accounts: list[Account],
    transactions: list[Transaction],
    used: set[int],
    stats: MatchStats,
) -> None:
    """Net the monthly card collection against the card's own statement credit.

    A credit-card statement is the same money twice: once as the individual
    purchases on the card, and once as the lump-sum collection from the current
    account. Counting both doubles the card's spend. The purchases are the real
    expense — they carry the merchant and the category — so it is the *pair* of
    settlement lines that is marked internal and netted out.

    Cards have no IBAN, so this cannot ride on the counter-IBAN matching above;
    it keys on the card's `settlement_iban` instead. A match additionally has to
    look like a settlement on at least one side, otherwise an ordinary refund
    that happens to equal some debit that week would be swallowed.
    """
    cards = [a for a in accounts if a.card_last4 and a.settlement_iban]
    if not cards:
        return

    by_account: dict[int, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        by_account[tx.account_id].append(tx)

    account_by_iban = {_normalise(a.iban): a for a in accounts if a.iban}

    for card in cards:
        target = account_by_iban.get(_normalise(card.settlement_iban))
        if target is None:
            continue  # the settlement account's own CSV has not been imported

        debits = [
            tx for tx in by_account.get(target.id, [])
            if tx.amount_cents < 0 and tx.id not in used and not tx.is_internal
        ]
        index: dict[int, list[Transaction]] = defaultdict(list)
        for tx in debits:
            index[-tx.amount_cents].append(tx)

        for credit in by_account.get(card.id, []):
            if credit.amount_cents <= 0 or credit.id in used:
                continue

            best, best_gap = None, None
            for debit in index.get(credit.amount_cents, []):
                if debit.id in used:
                    continue
                gap = abs((debit.booked_on - credit.booked_on).days)
                if gap > SETTLEMENT_WINDOW_DAYS:
                    continue
                if not (_looks_like_settlement(debit) or _looks_like_settlement(credit)):
                    continue
                if best_gap is None or gap < best_gap:
                    best, best_gap = debit, gap

            if best is not None:
                group = uuid.uuid4().hex
                for leg in (credit, best):
                    leg.is_internal = True
                    leg.transfer_group = group
                    leg.transfer_pending = False
                    _clear_auto_category(leg)
                used.add(credit.id)
                used.add(best.id)
                stats.settlements_matched += 1

        # Money sent to the card whose card-side row was never imported — the
        # card export usually covers a far shorter period than the current
        # account. These are unmistakably card movements (the bank's own `cc`
        # code, or the card number in the description), so counting them as
        # household spend would double the card's real cost. Flagged pending,
        # exactly like a half-imported IBAN transfer.
        for debit in debits:
            if debit.id in used or debit.is_internal:
                continue
            haystack = f"{debit.description} {debit.counter_name}".lower()
            if debit.bank_code in SETTLEMENT_BANK_CODES or (
                card.card_last4 and card.card_last4 in haystack
            ):
                debit.is_internal = True
                debit.transfer_pending = True
                _clear_auto_category(debit)
                used.add(debit.id)
                stats.legs_pending += 1


def link_manually(db: Session, tx_id_a: int, tx_id_b: int) -> str:
    """Link two transactions the matcher missed. Returns the group id."""
    a = db.get(Transaction, tx_id_a)
    b = db.get(Transaction, tx_id_b)
    if a is None or b is None:
        raise ValueError("Transactie niet gevonden.")
    if a.id == b.id:
        raise ValueError("Een transactie kan niet aan zichzelf gekoppeld worden.")
    if a.account_id == b.account_id:
        raise ValueError("Beide transacties staan op dezelfde rekening.")
    if a.amount_cents + b.amount_cents != 0:
        raise ValueError("De bedragen zijn niet elkaars tegengestelde.")

    group = uuid.uuid4().hex
    for leg in (a, b):
        leg.is_internal = True
        leg.transfer_manual = True
        leg.transfer_group = group
        leg.transfer_pending = False
        _clear_auto_category(leg)
    db.commit()
    return group


def unlink(db: Session, group: str) -> int:
    """Break a link the matcher got wrong and pin the decision, so the next
    automatic run does not simply re-create it."""
    legs = db.scalars(select(Transaction).where(Transaction.transfer_group == group)).all()
    for leg in legs:
        leg.is_internal = False
        leg.transfer_group = None
        leg.transfer_pending = False
        leg.transfer_manual = True
    db.commit()
    return len(legs)
