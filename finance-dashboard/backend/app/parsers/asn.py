"""ASN Bank CSV parser.

Column layout (20 fields):

    Datum, Je rekening, Van / naar, Naam, Adres, Postcode, Woonplaats,
    Valuta saldo, Saldo voor boeking, Valuta, Bedrag bij / af,
    Verwerkingsdatum, Valutadatum, Code, Type, Volgnummer,
    Betalingskenmerk, Omschrijving, Afschriftnummer, Categorie

ASN downloads usually arrive *without* a header row — every line is data.
We inject the canonical column names when that's the case, so the rest
of the code is identical between headered and headerless files.

'Bedrag bij / af' is the signed amount with comma decimal (-12,34 / 1500,00).
'Datum' is Dutch DD-MM-YYYY in newer exports; pandas with dayfirst=True
covers both that and YYYY-MM-DD / YYYYMMDD. The ASN-supplied 'Categorie'
column is intentionally ignored — we run our own keyword categorization
so categories are consistent across banks.
"""

import pandas as pd
from io import StringIO
from typing import Any, Dict, List

from ._common import auto_categorize, decode_csv_bytes, make_hash, s


ASN_COLUMNS = [
    "Datum", "Je rekening", "Van / naar", "Naam", "Adres", "Postcode",
    "Woonplaats", "Valuta saldo", "Saldo voor boeking", "Valuta",
    "Bedrag bij / af", "Verwerkingsdatum", "Valutadatum", "Code", "Type",
    "Volgnummer", "Betalingskenmerk", "Omschrijving", "Afschriftnummer",
    "Categorie",
]


def _looks_like_asn_header(line: str) -> bool:
    return "Je rekening" in line and "Bedrag bij / af" in line


def parse_asn_csv(content: bytes) -> List[Dict[str, Any]]:
    text = decode_csv_bytes(content)
    first_line = text.split("\n", 1)[0]

    # `sep=None, engine='python'` lets pandas sniff comma vs semicolon —
    # ASN exports are usually comma-separated but we've seen semicolon
    # variants. `quoting` handles the quoted IBANs and descriptions.
    common_kw = dict(dtype=str, sep=None, engine="python")
    if _looks_like_asn_header(first_line):
        df = pd.read_csv(StringIO(text), **common_kw)
    else:
        # Header-less file — name the columns ourselves so the rest of the
        # code can keep referencing them by name.
        df = pd.read_csv(StringIO(text), header=None, names=ASN_COLUMNS, **common_kw)
    df.columns = [c.strip() for c in df.columns]

    records = []
    for _, row in df.iterrows():
        try:
            raw_amount = s(row.get("Bedrag bij / af", "0")).replace(",", ".") or "0"
            amount = float(raw_amount)

            tx_date = pd.to_datetime(s(row.get("Datum", "")), dayfirst=True).date()
            description = s(row.get("Omschrijving", ""))
            counter_name = s(row.get("Naam", ""))
            counter_iban = s(row.get("Van / naar", ""))
            own_iban = s(row.get("Je rekening", ""))
            note = s(row.get("Betalingskenmerk", ""))

            # Cash withdrawals and similar can leave 'Van / naar' empty or
            # holding a non-IBAN string. We just store whatever is there;
            # transfer detection compares against the user's own IBAN set,
            # so non-matching values are harmlessly ignored downstream.

            # Skip filler rows: zero amount with no description and no
            # counterparty — same defensive guard as the Rabobank parser.
            if amount == 0 and not description and not counter_name and not counter_iban:
                continue

            record = {
                "date": tx_date,
                "amount": round(amount, 2),
                "description": description,
                "counter_name": counter_name,
                "counter_iban": counter_iban,
                "own_iban": own_iban,
                "note": note,
                "is_income": amount > 0,
                "suggested_category": auto_categorize(description, counter_name),
            }
            record["import_hash"] = make_hash(record)
            records.append(record)
        except Exception:
            continue

    return records
