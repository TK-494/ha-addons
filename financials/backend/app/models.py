"""ORM models.

Money is stored as integer cents throughout. Categorisation rules are rows,
not Python constants, so changing one is an edit in the UI rather than a
rebuild and redeploy of the add-on.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Table, Text,
    UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Labels are a *second dimension*, deliberately not a second category.
#
# A €60 tank of fuel during a holiday is fully fuel and fully holiday — it is
# not two halves. Letting a transaction carry two categories would make the
# category totals sum to more than the money actually spent, and splitting the
# amount 50/50 would understate the fuel. So: exactly one category for the
# accounting, any number of labels for cross-cutting questions like "what did
# Vakantie 2019 cost me in total".
transaction_tags = Table(
    "transaction_tags",
    Base.metadata,
    Column("transaction_id", ForeignKey("transactions.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

# Account kinds. `savings` is excluded from spend analysis but counted towards
# net worth, so moving money there reads as saved rather than spent.
ACCOUNT_KINDS = ("checking", "savings", "credit_card")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="checking")
    iban: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    card_last4: Mapped[Optional[str]] = mapped_column(String(8))
    product_name: Mapped[Optional[str]] = mapped_column(String(120))
    # For a card: the current account its monthly collection is taken from.
    settlement_iban: Mapped[Optional[str]] = mapped_column(String(40))
    display_name: Mapped[Optional[str]] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    # True while `kind` is still the app's own guess. The moment the user picks
    # a kind by hand this flips, and automatic classification leaves the
    # account alone forever after.
    kind_auto: Mapped[bool] = mapped_column(Boolean, default=True)
    include_in_networth: Mapped[bool] = mapped_column(Boolean, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")

    @property
    def label(self) -> str:
        if self.display_name:
            return self.display_name
        if self.card_last4:
            return f"{self.product_name or 'Creditcard'} ••{self.card_last4}"
        return self.iban or self.key


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", "parent_id", name="uq_category_name_parent"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    color: Mapped[str] = mapped_column(String(9), default="#64748b")
    icon: Mapped[Optional[str]] = mapped_column(String(40))
    is_income: Mapped[bool] = mapped_column(Boolean, default=False)
    # Income you cannot count on: travel allowance, working-from-home
    # allowance, overtime. Kept apart from the base salary because "what can I
    # commit to every month" is a different number from "what came in".
    variable_income: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded_from_budget: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)

    parent: Mapped[Optional["Category"]] = relationship(remote_side=[id])


class Tag(Base):
    """A free-form label, orthogonal to categories: `vakantie-2019`,
    `verbouwing`, `zakelijk`."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    color: Mapped[str] = mapped_column(String(9), default="#0ea5e9")
    note: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(
        secondary=transaction_tags, back_populates="tags"
    )


class Rule(Base):
    """One categorisation rule. Evaluated in `priority` order, first match wins.

    `field` names the haystack, so a rule can target the merchant name without
    matching the same word inside a free-text description.
    """

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # any | description | counter_name | counter_iban | creditor_id | bank_code
    field: Mapped[str] = mapped_column(String(20), default="any")
    # contains | equals | startswith
    operator: Mapped[str] = mapped_column(String(12), default="contains")
    # One pattern per line. Keeping alternatives in a single rule is what stops
    # every manual correction from spawning another near-duplicate.
    value: Mapped[str] = mapped_column(Text)
    amount_min_cents: Mapped[Optional[int]] = mapped_column(Integer)
    amount_max_cents: Mapped[Optional[int]] = mapped_column(Integer)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    # How this rule came to exist. Kept because "why is this categorised like
    # that" is the question you actually ask six months later, and because an
    # export without provenance is hard to reason about.
    #   seed        — shipped with the add-on, from a numbered batch
    #   manual      — typed in on the rules page
    #   transaction — created via "Regel maken" on a specific transaction
    #   import      — restored from an exported file
    origin: Mapped[str] = mapped_column(String(20), default="manual")
    seed_batch: Mapped[Optional[int]] = mapped_column(Integer)
    source_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    note: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    category: Mapped["Category"] = relationship()


class ImportBatch(Base):
    """One uploaded file. The file itself stays on disk so the import can be
    replayed after a rule change, and can be deleted with or without the
    transactions it produced."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    # UUID filename on disk — the uploaded name never touches the filesystem.
    stored_name: Mapped[Optional[str]] = mapped_column(String(80))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    format_key: Mapped[str] = mapped_column(String(40))
    format_label: Mapped[str] = mapped_column(String(80))
    rows_parsed: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, default=0)
    date_from: Mapped[Optional[date]] = mapped_column(Date)
    date_to: Mapped[Optional[date]] = mapped_column(Date)
    errors_json: Mapped[Optional[str]] = mapped_column(Text)
    # An upload is stored and previewed first, and only written to the ledger
    # once the user confirms. An abandoned preview stays uncommitted.
    committed: Mapped[bool] = mapped_column(Boolean, default=False)
    file_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_account_date", "account_id", "booked_on"),
        Index("ix_tx_date_amount", "booked_on", "amount_cents"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    import_batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )
    import_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    booked_on: Mapped[date] = mapped_column(Date, index=True)
    value_date: Mapped[Optional[date]] = mapped_column(Date)
    processed_on: Mapped[Optional[date]] = mapped_column(Date)

    amount_cents: Mapped[int] = mapped_column(Integer)
    balance_after_cents: Mapped[Optional[int]] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    description: Mapped[str] = mapped_column(String(500), default="")
    counter_iban: Mapped[str] = mapped_column(String(40), default="", index=True)
    counter_name: Mapped[str] = mapped_column(String(200), default="")
    ultimate_party: Mapped[str] = mapped_column(String(200), default="")
    bank_code: Mapped[str] = mapped_column(String(10), default="")
    mandate_ref: Mapped[str] = mapped_column(String(80), default="")
    creditor_id: Mapped[str] = mapped_column(String(60), default="", index=True)
    payment_ref: Mapped[str] = mapped_column(String(120), default="")
    bank_ref: Mapped[str] = mapped_column(String(80), default="")

    fx_amount_cents: Mapped[Optional[int]] = mapped_column(Integer)
    fx_currency: Mapped[str] = mapped_column(String(3), default="")
    fx_rate: Mapped[Optional[str]] = mapped_column(String(20))

    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    # Set when a human picked the category: rule re-runs must never overwrite
    # a decision the user made by hand.
    category_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── internal transfers (see PLAN §11) ──────────────────────────────────
    # Both legs of a transfer keep existing and keep moving their own account's
    # balance; only household-level income/expense figures skip them.
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    transfer_group: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    # Counterparty is one of your own accounts, but the matching leg has not
    # been imported yet — flagged rather than silently counted as spend.
    transfer_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    transfer_manual: Mapped[bool] = mapped_column(Boolean, default=False)

    note: Mapped[Optional[str]] = mapped_column(Text)

    account: Mapped["Account"] = relationship(back_populates="transactions")
    category: Mapped[Optional["Category"]] = relationship()
    tags: Mapped[list["Tag"]] = relationship(
        secondary=transaction_tags, back_populates="transactions", lazy="selectin"
    )
    splits: Mapped[list["TransactionSplit"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan", lazy="selectin"
    )


class TransactionSplit(Base):
    """One transaction divided across categories.

    A salary is one bank line but several things at once: base pay plus travel
    and working-from-home allowances. The bank cannot tell them apart, so the
    split is recorded here — and the parts, not the lump sum, are what the
    category reporting uses.

    Splits must add up to the transaction exactly. A split that does not
    reconcile is worse than no split at all, because every total built on it
    would be quietly wrong.
    """

    __tablename__ = "transaction_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    amount_cents: Mapped[int] = mapped_column(Integer)
    note: Mapped[Optional[str]] = mapped_column(String(200))

    transaction: Mapped["Transaction"] = relationship(back_populates="splits")
    category: Mapped[Optional["Category"]] = relationship()


class Setting(Base):
    """Key/value app settings. Month-boundary mode lives here: it is a display
    choice, so switching it re-buckets the whole history instantly instead of
    needing a re-import."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class PeriodOverride(Base):
    """A hand-corrected month boundary.

    Salary dates can be inferred for most months, but not all: a one-off
    advance, a corrected payroll run, a month where the employer changed. This
    is the escape hatch, and it wins over everything automatic.
    """

    __tablename__ = "period_overrides"
    __table_args__ = (UniqueConstraint("year", "month", name="uq_period_override"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    note: Mapped[Optional[str]] = mapped_column(String(200))


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("category_id", "year", "month", name="uq_budget_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer)
    rollover: Mapped[bool] = mapped_column(Boolean, default=False)

    category: Mapped["Category"] = relationship()
