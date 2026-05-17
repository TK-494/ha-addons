"""Bank CSV parsers.

`parse_bank_csv(bytes)` is the single entry point used by the upload
endpoint. It peeks at the header to decide which bank-specific parser to
call; each parser returns the same record shape, so transfer detection,
auto-categorization, and dedupe downstream are bank-agnostic.
"""

import re
from typing import Any, Dict, List

from .asn import ASN_COLUMNS, parse_asn_csv
from .rabobank import parse_rabobank_csv


__all__ = ["parse_bank_csv", "parse_asn_csv", "parse_rabobank_csv", "detect_bank"]


# Very loose IBAN-ish check — two letters, two digits, then bank/account
# chars. Enough to tell an IBAN cell apart from a date or a name.
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$")


def _smart_split(line: str) -> list[str]:
    """Split a CSV-ish line on either comma or semicolon (whichever yields
    more fields) and strip surrounding quotes/whitespace from each cell.
    Sufficient for first-line shape detection — we're not trying to parse
    quoted fields with embedded delimiters here."""
    by_comma = line.split(",")
    by_semi = line.split(";")
    fields = by_semi if len(by_semi) > len(by_comma) else by_comma
    return [f.strip().strip('"').strip("'") for f in fields]


def detect_bank(content: bytes) -> str:
    """Return 'asn' or 'rabobank' based on the first line of the CSV.

    ASN downloads typically arrive *without* a header row, so the obvious
    'look for "Je rekening" in the header' check isn't enough — we also
    match the structural shape (20 fields, IBAN in column 2) to catch
    header-less exports.
    """
    head = content.split(b"\n", 1)[0]
    try:
        first_line = head.decode("utf-8", errors="replace")
    except Exception:
        first_line = head.decode("cp1252", errors="replace")

    # Headered ASN — unambiguous column-name signature.
    if "Je rekening" in first_line and "Bedrag bij / af" in first_line:
        return "asn"

    # Header-less ASN — match by shape: 20 fields, second one is the
    # account's IBAN.
    fields = _smart_split(first_line)
    if len(fields) == len(ASN_COLUMNS) and _IBAN_RE.match(fields[1] if len(fields) > 1 else ""):
        return "asn"

    return "rabobank"


def parse_bank_csv(content: bytes) -> List[Dict[str, Any]]:
    if detect_bank(content) == "asn":
        return parse_asn_csv(content)
    return parse_rabobank_csv(content)
