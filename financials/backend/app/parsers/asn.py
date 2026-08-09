"""ASN Bank transactiehistorie CSV.

20 columns. Modern exports carry a header row; older ones arrive header-less,
so the canonical column names are injected when the first line looks like
data. Everything downstream then reads by name either way.

Layout specifics that bite:

* Dates are Dutch `DD-MM-YYYY`. Read ISO-first and 03-04-2025 becomes 4 March
  — parses cleanly, lands in the wrong month, never raises.
* The balance column is `Saldo voor boeking` — the balance *before* the
  transaction, where Rabobank gives the balance after. It is converted on the
  way in so both banks store the same thing.
* `Adres` / `Postcode` / `Woonplaats` hold the counterparty's home address.
  Read and discarded: no analytical value, real privacy cost.
* `Categorie` is ASN's own guess. Ignored, so categories stay consistent
  across banks and follow your own rules.
"""

from __future__ import annotations

from typing import Optional

from .base import (
    ParsedAccount,
    ParsedRow,
    RowError,
    clean,
    detect_decimal_sep,
    is_filler,
    parse_amount_cents,
    parse_date,
    read_rows,
    require_columns,
)

LABEL = "ASN Bank"
FORMAT_KEY = "asn"

COLUMNS = [
    "Datum", "Je rekening", "Van / naar", "Naam", "Adres", "Postcode",
    "Woonplaats", "Valuta saldo", "Saldo voor boeking", "Valuta",
    "Bedrag bij / af", "Verwerkingsdatum", "Valutadatum", "Code", "Type",
    "Volgnummer", "Betalingskenmerk", "Omschrijving", "Afschriftnummer",
    "Categorie",
]

REQUIRED = {"Datum", "Je rekening", "Bedrag bij / af"}
SIGNATURE = {"Je rekening", "Bedrag bij / af"}


def matches(fieldnames: list[str]) -> bool:
    return SIGNATURE.issubset(set(fieldnames))


def looks_headerless(first_line: str) -> bool:
    """A header-less ASN file has 20 fields and an IBAN in the second one."""
    if "Je rekening" in first_line:
        return False
    fields = [f.strip().strip('"').strip("'") for f in first_line.split(",")]
    if len(fields) != len(COLUMNS):
        return False
    second = fields[1].replace(" ", "")
    return len(second) >= 15 and second[:2].isalpha() and second[2:4].isdigit()


def parse(text: str) -> tuple[dict[str, ParsedAccount], list[ParsedRow], list[RowError]]:
    if looks_headerless(text.split("\n", 1)[0]):
        text = ",".join(COLUMNS) + "\n" + text

    fieldnames, rows = read_rows(text)
    require_columns(fieldnames, REQUIRED, LABEL)

    # Materialise once: the decimal convention is decided from real values
    # before any row is converted.
    all_rows = list(rows)
    decimal_sep = detect_decimal_sep(
        [clean(r.get("Bedrag bij / af")) for _, r in all_rows], default="."
    )

    accounts: dict[str, ParsedAccount] = {}
    parsed: list[ParsedRow] = []
    errors: list[RowError] = []

    for line_no, raw in all_rows:
        try:
            iban = clean(raw.get("Je rekening"))
            if not iban:
                raise ValueError("geen rekeningnummer in de regel")

            currency = clean(raw.get("Valuta")) or "EUR"
            if iban not in accounts:
                accounts[iban] = ParsedAccount(
                    key=iban, kind="checking", iban=iban, currency=currency
                )

            amount_cents = parse_amount_cents(raw.get("Bedrag bij / af"), decimal_sep)

            # ASN reports the balance *before* the booking; store the balance
            # after, so both banks mean the same thing.
            balance_before = _opt_amount(raw.get("Saldo voor boeking"), decimal_sep)
            balance_after = None if balance_before is None else balance_before + amount_cents

            row = ParsedRow(
                account_key=iban,
                currency=currency,
                booked_on=parse_date(raw.get("Datum"), dayfirst=True),
                value_date=_opt_date(raw.get("Valutadatum")),
                processed_on=_opt_date(raw.get("Verwerkingsdatum")),
                amount_cents=amount_cents,
                balance_after_cents=balance_after,
                description=clean(raw.get("Omschrijving")),
                counter_iban=clean(raw.get("Van / naar")),
                counter_name=clean(raw.get("Naam")),
                bank_code=clean(raw.get("Type")).lower(),
                payment_ref=clean(raw.get("Betalingskenmerk")),
                bank_ref=clean(raw.get("Volgnummer")),
            )
            if is_filler(row):
                continue
            parsed.append(row.finalise())
        except Exception as exc:  # noqa: BLE001
            errors.append(RowError(line_no, str(exc), _preview(raw)))

    return accounts, parsed, errors


def _opt_amount(value: Optional[str], decimal_sep: str) -> Optional[int]:
    if not clean(value):
        return None
    try:
        return parse_amount_cents(value, decimal_sep)
    except ValueError:
        return None


def _opt_date(value: Optional[str]):
    if not clean(value):
        return None
    try:
        return parse_date(value, dayfirst=True)
    except ValueError:
        return None


def _preview(raw: dict) -> str:
    # Never echo the counterparty's home address back to the UI.
    skip = {"Adres", "Postcode", "Woonplaats"}
    return ",".join(clean(v) for k, v in list(raw.items())[:8] if k not in skip)
