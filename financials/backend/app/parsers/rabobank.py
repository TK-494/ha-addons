"""Rabobank betaal-/spaarrekening CSV (the "CSV_A_accounts_*" export).

26 columns, comma-separated, quoted, Windows-1252. One file routinely holds
several accounts — the sample export carries three IBANs — so the parser keys
every row to the account named in its own `IBAN/BBAN` cell rather than
assuming a single account per file.

Two columns here are worth more than they look:

* `Saldo na trn` gives the running balance per transaction, so balance history
  needs no reconstruction from a starting point.
* `Incassant ID` / `Machtigingskenmerk` identify the creditor behind a direct
  debit. That is subscription identity handed over for free — no fuzzy
  description matching needed to spot recurring payments.
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

LABEL = "Rabobank betaal/spaar"
FORMAT_KEY = "rabobank_current"

REQUIRED = {"IBAN/BBAN", "Datum", "Bedrag"}
SIGNATURE = {"IBAN/BBAN", "Saldo na trn", "Omschrijving-1"}


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
            iban = clean(raw.get("IBAN/BBAN"))
            if not iban:
                raise ValueError("geen rekeningnummer in de regel")

            currency = clean(raw.get("Munt")) or "EUR"
            if iban not in accounts:
                accounts[iban] = ParsedAccount(
                    key=iban,
                    kind="checking",  # savings is a user choice; the CSV can't tell us
                    iban=iban,
                    currency=currency,
                )

            # Description is split across three columns; Omschrijving-2 is
            # frequently a single space rather than empty.
            description = " ".join(
                p for p in (clean(raw.get(f"Omschrijving-{i}")) for i in (1, 2, 3)) if p
            )

            row = ParsedRow(
                account_key=iban,
                currency=currency,
                booked_on=parse_date(raw.get("Datum")),
                value_date=_opt_date(raw.get("Rentedatum")),
                amount_cents=parse_amount_cents(raw.get("Bedrag"), decimal_sep=","),
                balance_after_cents=_opt_amount(raw.get("Saldo na trn")),
                description=description,
                counter_iban=clean(raw.get("Tegenrekening IBAN/BBAN")),
                counter_name=clean(raw.get("Naam tegenpartij")),
                ultimate_party=clean(raw.get("Naam uiteindelijke partij")),
                bank_code=clean(raw.get("Code")).lower(),
                mandate_ref=clean(raw.get("Machtigingskenmerk")),
                creditor_id=clean(raw.get("Incassant ID")),
                payment_ref=clean(raw.get("Betalingskenmerk")),
                bank_ref=clean(raw.get("Transactiereferentie")) or clean(raw.get("Volgnr")),
                fx_amount_cents=_opt_amount(raw.get("Oorspr bedrag")),
                fx_currency=clean(raw.get("Oorspr munt")),
                fx_rate=clean(raw.get("Koers")) or None,
            )
            if is_filler(row):
                continue
            parsed.append(row.finalise())
        except Exception as exc:  # noqa: BLE001 — one bad row must not sink the file
            errors.append(RowError(line_no, str(exc), _preview(raw)))

    return accounts, parsed, errors


def _opt_amount(value: Optional[str]) -> Optional[int]:
    if not clean(value):
        return None
    try:
        return parse_amount_cents(value, decimal_sep=",")
    except ValueError:
        return None


def _opt_date(value: Optional[str]):
    if not clean(value):
        return None
    try:
        return parse_date(value)
    except ValueError:
        return None


def _preview(raw: dict) -> str:
    return ",".join(clean(v) for v in list(raw.values())[:6])
