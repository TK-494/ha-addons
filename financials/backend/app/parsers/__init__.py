"""Parser registry.

Detection proposes, the user disposes. `detect()` reads the header and
suggests a format; the upload flow shows that suggestion together with a
preview of the first parsed rows, and the user confirms or overrides before
anything is written. Adding a bank means adding a module here and one entry to
`REGISTRY` — the dropdown and the API pick it up automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from . import asn, rabobank, rabobank_cc
from .base import (
    ParseError,
    ParsedAccount,
    ParsedRow,
    RowError,
    decode_csv_bytes,
    read_rows,
)

__all__ = [
    "AUTO",
    "FORMATS",
    "ParseError",
    "ParsedAccount",
    "ParsedRow",
    "RowError",
    "ParseResult",
    "decode_csv_bytes",
    "detect",
    "format_choices",
    "parse_csv",
]

AUTO = "auto"


@dataclass(frozen=True)
class Format:
    key: str
    label: str
    matches: Callable[[list[str]], bool]
    parse: Callable[[str], tuple[dict[str, ParsedAccount], list[ParsedRow], list[RowError]]]


# Order matters: the credit-card layout is checked before the current-account
# one so a file carrying both signatures can never be mistaken for the other.
FORMATS: tuple[Format, ...] = (
    Format(rabobank_cc.FORMAT_KEY, rabobank_cc.LABEL, rabobank_cc.matches, rabobank_cc.parse),
    Format(rabobank.FORMAT_KEY, rabobank.LABEL, rabobank.matches, rabobank.parse),
    Format(asn.FORMAT_KEY, asn.LABEL, asn.matches, asn.parse),
)

_BY_KEY = {f.key: f for f in FORMATS}


@dataclass
class ParseResult:
    format_key: str
    format_label: str
    accounts: dict[str, ParsedAccount]
    rows: list[ParsedRow]
    errors: list[RowError]


def format_choices() -> list[dict]:
    """Dropdown contents for the upload form."""
    return [{"key": AUTO, "label": "Automatisch herkennen"}] + [
        {"key": f.key, "label": f.label} for f in FORMATS
    ]


def detect(text: str) -> Optional[str]:
    """Return the format key the header points at, or None when nothing
    matches. None is a refusal to guess, not a default — the caller reports it
    and asks the user, rather than falling back to a parser that will quietly
    produce nonsense."""
    if asn.looks_headerless(text.split("\n", 1)[0]):
        return asn.FORMAT_KEY
    try:
        fieldnames, _ = read_rows(text)
    except Exception:  # noqa: BLE001 — unreadable header is simply "no match"
        return None
    for fmt in FORMATS:
        if fmt.matches(fieldnames):
            return fmt.key
    return None


def parse_csv(text: str, format_key: str = AUTO) -> ParseResult:
    """Parse `text` as `format_key`, or as whatever detection suggests.

    An explicit `format_key` always wins over detection — including when
    detection is confident and wrong.
    """
    if format_key == AUTO:
        detected = detect(text)
        if detected is None:
            raise ParseError(
                "Formaat niet herkend. Kies handmatig de bank waarvan dit bestand komt."
            )
        format_key = detected

    fmt = _BY_KEY.get(format_key)
    if fmt is None:
        raise ParseError(f"Onbekend formaat {format_key!r}.")

    accounts, rows, errors = fmt.parse(text)
    return ParseResult(fmt.key, fmt.label, accounts, rows, errors)
