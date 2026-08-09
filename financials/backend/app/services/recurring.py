"""Recurring-payment detection.

Rabobank hands over the creditor behind every direct debit (`Incassant ID`),
which makes subscription identity a `GROUP BY` rather than fuzzy matching on
merchant names. Where that field is missing — card payments, ASN rows — the
fallback is a normalised counterparty name.

A group counts as recurring when it appears in at least three distinct months
and those months span at least three months of calendar time. Three occurrences
inside one month is a shopping habit, not a subscription.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from statistics import median
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, Transaction
from .periods import PeriodConfig, period_of

MIN_OCCURRENCES = 3
MIN_SPAN_MONTHS = 3

# A payment is "still active" if it has been seen in the last 90 days. Annual
# subscriptions are handled separately by their own cadence.
ACTIVE_WINDOW_DAYS = 100


@dataclass
class RecurringGroup:
    key: str
    label: str
    creditor_id: str = ""
    occurrences: int = 0
    months: set[tuple[int, int]] = field(default_factory=set)
    amounts: list[int] = field(default_factory=list)
    dates: list[date] = field(default_factory=list)
    category_name: Optional[str] = None
    transaction_ids: list[int] = field(default_factory=list)

    @property
    def first_seen(self) -> date:
        return min(self.dates)

    @property
    def last_seen(self) -> date:
        return max(self.dates)

    @property
    def typical_amount_cents(self) -> int:
        return int(median(sorted(self.amounts)))

    @property
    def cadence_days(self) -> Optional[float]:
        if len(self.dates) < 2:
            return None
        ordered = sorted(self.dates)
        gaps = [(b - a).days for a, b in zip(ordered, ordered[1:])]
        return median(gaps) if gaps else None

    @property
    def interval(self) -> str:
        cadence = self.cadence_days
        if cadence is None:
            return "onbekend"
        if cadence <= 10:
            return "wekelijks"
        if cadence <= 45:
            return "maandelijks"
        if cadence <= 100:
            return "per kwartaal"
        if cadence <= 200:
            return "half jaarlijks"
        return "jaarlijks"

    @property
    def monthly_equivalent_cents(self) -> int:
        """Normalise every cadence to a monthly figure so a €120 annual
        insurance and a €10 monthly one are comparable."""
        cadence = self.cadence_days or 30.0
        return int(round(self.typical_amount_cents * (30.44 / max(cadence, 1))))

    @property
    def is_active(self) -> bool:
        return (date.today() - self.last_seen).days <= max(
            ACTIVE_WINDOW_DAYS, (self.cadence_days or 30) * 1.5
        )

    @property
    def amount_changed(self) -> bool:
        """Flag a price change: the most recent amount differs from the
        historical median by more than 5% and at least 50 cents."""
        if len(self.amounts) < 3:
            return False
        latest = self.amounts[-1]
        baseline = self.typical_amount_cents
        delta = abs(latest - baseline)
        return delta >= 50 and delta / max(abs(baseline), 1) > 0.05


_NAME_NOISE = re.compile(r"\b(bv|b\.v\.|nv|n\.v\.|inc|ltd|gmbh|nederland|netherlands)\b", re.I)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalise_name(name: str) -> str:
    """Collapse a counterparty name to a grouping key.

    Card descriptions carry the city and a payment method ("APPLE.COM/BILL
    ITUNES.COM IRL Apple Pay"), so only the leading token block is meaningful.
    """
    lowered = _NAME_NOISE.sub(" ", (name or "").lower())
    cleaned = _NON_ALNUM.sub(" ", lowered).strip()
    return " ".join(cleaned.split()[:3])


def detect(
    db: Session,
    config: PeriodConfig,
    include_income: bool = False,
) -> list[RecurringGroup]:
    """Group the ledger into recurring payment streams."""
    stmt = (
        select(Transaction)
        .where(Transaction.is_internal.is_(False))
        .order_by(Transaction.booked_on)
    )
    if not include_income:
        stmt = stmt.where(Transaction.amount_cents < 0)

    groups: dict[str, RecurringGroup] = {}
    for tx in db.scalars(stmt).yield_per(1000):
        if tx.creditor_id:
            key = f"creditor:{tx.creditor_id.lower()}"
            label = tx.counter_name or tx.description or tx.creditor_id
        else:
            name = normalise_name(tx.counter_name or tx.description)
            if len(name) < 3:
                continue
            key = f"name:{name}"
            label = tx.counter_name or tx.description[:60]

        group = groups.get(key)
        if group is None:
            group = RecurringGroup(key=key, label=label, creditor_id=tx.creditor_id)
            groups[key] = group

        group.occurrences += 1
        group.months.add(period_of(tx.booked_on, config))
        group.amounts.append(tx.amount_cents)
        group.dates.append(tx.booked_on)
        group.transaction_ids.append(tx.id)
        if tx.category is not None and group.category_name is None:
            group.category_name = tx.category.name

    return [g for g in groups.values() if _qualifies(g)]


def _qualifies(group: RecurringGroup) -> bool:
    if len(group.months) < MIN_OCCURRENCES:
        return False
    span_months = (group.last_seen.year - group.first_seen.year) * 12 + (
        group.last_seen.month - group.first_seen.month
    )
    if span_months < MIN_SPAN_MONTHS:
        return False
    # Wildly varying amounts are a supermarket, not a subscription.
    typical = abs(group.typical_amount_cents) or 1
    spread = max(abs(a) for a in group.amounts) - min(abs(a) for a in group.amounts)
    return spread / typical <= 2.0


def recurring_transaction_ids(groups: Iterable[RecurringGroup]) -> set[int]:
    ids: set[int] = set()
    for group in groups:
        ids.update(group.transaction_ids)
    return ids


def serialise(group: RecurringGroup) -> dict:
    return {
        "key": group.key,
        "label": group.label,
        "category": group.category_name,
        "occurrences": group.occurrences,
        "interval": group.interval,
        "typical_amount": group.typical_amount_cents / 100,
        "monthly_equivalent": group.monthly_equivalent_cents / 100,
        "first_seen": group.first_seen.isoformat(),
        "last_seen": group.last_seen.isoformat(),
        "active": group.is_active,
        "amount_changed": group.amount_changed,
        "from_creditor_id": bool(group.creditor_id),
    }
