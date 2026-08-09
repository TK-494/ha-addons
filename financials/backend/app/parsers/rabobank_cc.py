"""Rabobank creditcard CSV (the "RA_CC_*" export).

13 columns. This is the layout the predecessor add-on got wrong: it has no
`Omschrijving-1` and no `Tegenrekening IBAN/BBAN`, so the shared Rabobank
parser fell through to its oldest branch, looked for a `Bedrag (EUR)` column
that does not exist, and imported every row at €0.00 — no exception, no
warning. Hence `require_columns` here, and hence the pre-import preview in the
UI.

Two fields matter beyond the obvious:

* `Tegenrekening IBAN` is the current account the card settles to. That is the
  link used to net the monthly collection against the individual card
  purchases, so card spend is counted once rather than twice.
* `Oorspr bedrag` / `Oorspr munt` / `Koers` carry foreign-currency purchases
  (25 rows in the sample export). Dropping them loses the real cost of a
  holiday.

`Creditcard Regel1` holds the cardholder's name. It is read to detect the
column's presence and then deliberately discarded — it has no analytical value
and every stored copy is a copy that can leak.
"""

from __future__ import annotations

from typing import Optional

from .base import (
    ParsedAccount,
    ParsedRow,
    RowError,
    clean,
    is_filler,
    parse_amount_cents,
    parse_date,
    read_rows,
    require_columns,
)

LABEL = "Rabobank creditcard"
FORMAT_KEY = "rabobank_creditcard"

REQUIRED = {"Creditcard Nummer", "Datum", "Bedrag", "Omschrijving"}
SIGNATURE = {"Creditcard Nummer", "Productnaam"}


def matches(fieldnames: list[str]) -> bool:
    return SIGNATURE.issubset(set(fieldnames))


def parse(text: str) -> tuple[dict[str, ParsedAccount], list[ParsedRow], list[RowError]]:
    fieldnames, rows = read_rows(text)
    require_columns(fieldnames, REQUIRED, LABEL)

    accounts: dict[str, ParsedAccount] = {}
    parsed: list[ParsedRow] = []
    errors: list[RowError] = []

    for line_no, raw in rows:
        try:
            last4 = clean(raw.get("Creditcard Nummer"))
            if not last4:
                raise ValueError("geen creditcardnummer in de regel")

            key = f"CC-{last4}"
            currency = clean(raw.get("Munt")) or "EUR"
            if key not in accounts:
                accounts[key] = ParsedAccount(
                    key=key,
                    kind="credit_card",
                    card_last4=last4,
                    product_name=clean(raw.get("Productnaam")) or None,
                    settlement_iban=clean(raw.get("Tegenrekening IBAN")) or None,
                    currency=currency,
                )

            row = ParsedRow(
                account_key=key,
                currency=currency,
                booked_on=parse_date(raw.get("Datum")),
                amount_cents=parse_amount_cents(raw.get("Bedrag"), decimal_sep=","),
                # The merchant string carries city and country baked in
                # ("APPLE.COM/BILL  ITUNES.COM  IRL  Apple Pay"); collapse the
                # runs of padding spaces so search and grouping behave.
                description=" ".join(clean(raw.get("Omschrijving")).split()),
                bank_ref=clean(raw.get("Transactiereferentie")),
                fx_amount_cents=_opt_amount(raw.get("Oorspr bedrag")),
                fx_currency=clean(raw.get("Oorspr munt")),
                fx_rate=clean(raw.get("Koers")) or None,
            )
            if is_filler(row):
                continue
            parsed.append(row.finalise())
        except Exception as exc:  # noqa: BLE001
            errors.append(RowError(line_no, str(exc), _preview(raw)))

    return accounts, parsed, errors


def _opt_amount(value: Optional[str]) -> Optional[int]:
    if not clean(value):
        return None
    try:
        return parse_amount_cents(value, decimal_sep=",")
    except ValueError:
        return None


def _preview(raw: dict) -> str:
    # Skip the name columns when echoing a failed row back to the UI.
    skip = {"Creditcard Regel1", "Creditcard Regel2"}
    return ",".join(clean(v) for k, v in list(raw.items())[:8] if k not in skip)
