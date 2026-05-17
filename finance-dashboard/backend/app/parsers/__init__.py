"""Bank CSV parsers.

`parse_bank_csv(bytes)` is the single entry point used by the upload
endpoint. It peeks at the header to decide which bank-specific parser to
call; each parser returns the same record shape, so transfer detection,
auto-categorization, and dedupe downstream are bank-agnostic.
"""

from typing import Any, Dict, List

from .asn import parse_asn_csv
from .rabobank import parse_rabobank_csv


__all__ = ["parse_bank_csv", "parse_asn_csv", "parse_rabobank_csv", "detect_bank"]


def detect_bank(content: bytes) -> str:
    """Return 'asn' or 'rabobank' based on the CSV header. The header is
    ASCII-safe so we don't need full encoding detection — first line is
    enough."""
    head = content.split(b"\n", 1)[0]
    try:
        header = head.decode("utf-8", errors="replace")
    except Exception:
        header = head.decode("cp1252", errors="replace")

    # ASN's "Je rekening" + "Bedrag bij / af" combination is unambiguous;
    # neither column name appears in any Rabobank layout.
    if "Je rekening" in header and "Bedrag bij / af" in header:
        return "asn"
    return "rabobank"


def parse_bank_csv(content: bytes) -> List[Dict[str, Any]]:
    if detect_bank(content) == "asn":
        return parse_asn_csv(content)
    return parse_rabobank_csv(content)
