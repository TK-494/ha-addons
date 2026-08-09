"""Shared parsing primitives.

Every bank parser turns its native CSV into a list of `ParsedRow`, so the
import pipeline downstream (dedupe, categorisation, transfer matching) never
needs to know which bank a row came from.

Money is carried as **integer cents** end to end. Floats accumulate error over
10k rows of summing and comparison, and transfer matching compares amounts for
exact equality — `-200.0 == 200.0` must be reliable, not approximately true.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator, Optional


class ParseError(Exception):
    """Raised when a file cannot be parsed as the requested format at all —
    wrong bank, missing required columns, unreadable encoding. Distinct from a
    single bad row, which is collected and reported instead of raised."""


@dataclass
class RowError:
    line_no: int
    reason: str
    raw: str

    def as_dict(self) -> dict:
        # Truncate: a raw line can hold personal data and this travels to the
        # UI and the logs. Enough to recognise the row, not enough to leak it.
        return {"line_no": self.line_no, "reason": self.reason, "raw": self.raw[:120]}


@dataclass
class ParsedAccount:
    """Account identity as it appears in the file itself."""

    key: str  # IBAN, or "CC-<last4>" for a card
    kind: str  # checking | savings | credit_card
    iban: Optional[str] = None
    card_last4: Optional[str] = None
    product_name: Optional[str] = None
    settlement_iban: Optional[str] = None
    currency: str = "EUR"


@dataclass
class ParsedRow:
    account_key: str
    booked_on: date
    amount_cents: int
    description: str = ""
    currency: str = "EUR"
    value_date: Optional[date] = None
    processed_on: Optional[date] = None
    balance_after_cents: Optional[int] = None
    counter_iban: str = ""
    counter_name: str = ""
    ultimate_party: str = ""
    bank_code: str = ""
    mandate_ref: str = ""
    creditor_id: str = ""
    payment_ref: str = ""
    bank_ref: str = ""
    fx_amount_cents: Optional[int] = None
    fx_currency: str = ""
    fx_rate: Optional[str] = None
    import_hash: str = field(default="", init=False)

    def finalise(self) -> "ParsedRow":
        """Compute the dedupe key. Re-importing an overlapping export must
        produce zero duplicates, while genuinely distinct same-day, same-amount
        transactions (two €2.99 Apple charges) must stay separate — which is
        why the bank's own reference/sequence number is part of the key."""
        parts = [
            self.account_key,
            self.booked_on.isoformat(),
            str(self.amount_cents),
            self.description,
            self.counter_iban,
            self.bank_ref,
        ]
        self.import_hash = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
        return self


# ─── primitives ─────────────────────────────────────────────────────────────

_BOM = "﻿"


def decode_csv_bytes(content: bytes) -> str:
    """Decode a bank CSV.

    ASN exports UTF-8; Rabobank exports Windows-1252 (its header literally
    contains `Naam initi<0xeb>rende partij`). Try UTF-8 strictly first, then
    CP1252. Never fall back to errors="replace" — a mangled counterparty name
    is silent data corruption that only surfaces months later, so an
    undecodable file is a hard error instead.
    """
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding).lstrip(_BOM)
        except UnicodeDecodeError:
            continue
    raise ParseError(
        "Bestand is geen geldige UTF-8 of Windows-1252 tekst — is dit wel een CSV-export?"
    )


def sniff_delimiter(line: str) -> str:
    """Comma or semicolon, whichever splits the header into more fields.
    Dutch banks ship both depending on the export locale."""
    return ";" if line.count(";") > line.count(",") else ","


def read_rows(text: str, delimiter: Optional[str] = None) -> tuple[list[str], Iterator[tuple[int, dict]]]:
    """Return (fieldnames, iterator of (line_no, row-dict)).

    Line numbers are 1-based and count the header, so they match what the user
    sees when they open the file — important for the import error list.
    """
    first_line = text.split("\n", 1)[0]
    delimiter = delimiter or sniff_delimiter(first_line)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    fieldnames = [(f or "").strip() for f in (reader.fieldnames or [])]
    reader.fieldnames = fieldnames

    def _iter() -> Iterator[tuple[int, dict]]:
        for i, row in enumerate(reader, start=2):
            yield i, row

    return fieldnames, _iter()


def clean(value: Optional[str]) -> str:
    """Trim whitespace and the single quotes ASN wraps some fields in
    (`'Start'`, `'Eigen rekening'`)."""
    if value is None:
        return ""
    out = value.strip()
    if len(out) >= 2 and out[0] == "'" and out[-1] == "'":
        out = out[1:-1].strip()
    return out


_AMOUNT_CLEAN_RE = re.compile(r"[^\d,.\-+]")


def parse_amount_cents(value: Optional[str], decimal_sep: str) -> int:
    """Parse a monetary string into integer cents.

    `decimal_sep` is declared per bank layout rather than guessed per row:
    Rabobank writes `-6,20`, ASN writes `200.00`, and a guess based on the
    last separator gets `1.234` wrong exactly when it matters most.
    """
    raw = _AMOUNT_CLEAN_RE.sub("", clean(value))
    if not raw:
        raise ValueError("leeg bedrag")

    thousands_sep = "." if decimal_sep == "," else ","
    raw = raw.replace(thousands_sep, "")
    if decimal_sep != ".":
        raw = raw.replace(decimal_sep, ".")
    raw = raw.lstrip("+")

    try:
        # Quantise via Decimal, not float: Decimal("0.145") * 100 is exact,
        # float("0.145") * 100 is 14.499999999999998 and rounds down.
        return int((Decimal(raw) * 100).to_integral_value(rounding="ROUND_HALF_UP"))
    except (InvalidOperation, ArithmeticError) as exc:
        raise ValueError(f"onleesbaar bedrag {value!r}") from exc


_DEC_COMMA_RE = re.compile(r"[-+]?[\d.]*,\d{1,2}$")
_DEC_DOT_RE = re.compile(r"[-+]?[\d,]*\.\d{1,2}$")


def detect_decimal_sep(samples: list[str], default: str = ".") -> str:
    """Decide comma-vs-dot **once per file**, from a sample of amount cells.

    ASN has shipped both conventions over the years. Deciding per row from the
    last separator seen is what turns `1.234` into €1.23; deciding once from a
    majority vote over real values is stable across the whole file.
    """
    comma = dot = 0
    for value in samples[:200]:
        raw = clean(value)
        if not raw:
            continue
        if _DEC_COMMA_RE.search(raw):
            comma += 1
        elif _DEC_DOT_RE.search(raw):
            dot += 1
    if comma == dot == 0:
        return default
    return "," if comma > dot else "."


_DATE_FORMATS_DAYFIRST = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%Y%m%d")
_DATE_FORMATS_ISOFIRST = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%d-%m-%Y", "%d/%m/%Y")


def parse_date(value: Optional[str], dayfirst: bool = False) -> date:
    """Parse a date, trying the layout's own convention first.

    `dayfirst` is not cosmetic: ASN writes `03-04-2025` for 3 April, and
    reading that as 4 March moves a transaction into the wrong month, the
    wrong quarter and the wrong budget — silently, because both parse fine.
    """
    raw = clean(value)
    if not raw:
        raise ValueError("lege datum")
    raw = raw.split(" ")[0].split("T")[0]
    for fmt in (_DATE_FORMATS_DAYFIRST if dayfirst else _DATE_FORMATS_ISOFIRST):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"onleesbare datum {value!r}")


def require_columns(fieldnames: list[str], required: set[str], label: str) -> None:
    """Fail loudly on a format mismatch.

    This is the guard the predecessor lacked: given a credit-card CSV it fell
    through to a layout whose amount column simply wasn't there, and imported
    271 rows at €0.00 without raising anything.
    """
    missing = required - set(fieldnames)
    if missing:
        raise ParseError(
            f"Dit lijkt geen {label}-export: de kolommen "
            f"{', '.join(sorted(missing))} ontbreken."
        )


def is_filler(row: ParsedRow) -> bool:
    """Zero-amount rows with no description and no counterparty are export
    padding, not transactions."""
    return (
        row.amount_cents == 0
        and not row.description
        and not row.counter_name
        and not row.counter_iban
    )
