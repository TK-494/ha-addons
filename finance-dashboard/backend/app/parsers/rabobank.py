"""Rabobank CSV parser. Three layouts have been seen in the wild:
- 'current'  (≈2018+): Datum, signed Bedrag, Tegenrekening IBAN/BBAN,
                       Naam tegenpartij, Omschrijving-1/2/3, …
- 'valuta'   (post-2022 variant): Valutadatum, Bedrag, Omschrijving, Notitie
- 'legacy'   (pre-IBAN-rename): Datum, Bedrag (EUR), Af Bij, Naam/Omschrijving
"""

import pandas as pd
from io import StringIO
from typing import Any, Dict, List

from ._common import auto_categorize, decode_csv_bytes, make_hash, s


def parse_rabobank_csv(content: bytes) -> List[Dict[str, Any]]:
    text = decode_csv_bytes(content)
    df = pd.read_csv(StringIO(text), dtype=str)
    df.columns = [c.strip() for c in df.columns]

    cols = set(df.columns)
    if "Valutadatum" in cols:
        fmt = "valuta"
    elif "Omschrijving-1" in cols or "Tegenrekening IBAN/BBAN" in cols:
        fmt = "current"
    else:
        fmt = "legacy"

    records = []
    for _, row in df.iterrows():
        try:
            if fmt == "valuta":
                raw_amount = s(row.get("Bedrag", "0")).replace(",", ".") or "0"
                amount = float(raw_amount)
                tx_date = pd.to_datetime(s(row.get("Valutadatum", ""))).date()
                description = s(row.get("Omschrijving", ""))
                counter_name = s(row.get("Naam tegenpartij", ""))
                counter_iban = s(row.get("Tegenrekening IBAN/BBAN", ""))
                own_iban = s(row.get("IBAN/BBAN", ""))
                note = s(row.get("Notitie", ""))
            elif fmt == "current":
                # Bedrag is signed with comma decimal: "-12,34" or "1500,00".
                raw_amount = s(row.get("Bedrag", "0")).replace(",", ".") or "0"
                amount = float(raw_amount)
                # Datum is typically YYYYMMDD or YYYY-MM-DD — let pandas guess.
                tx_date = pd.to_datetime(s(row.get("Datum", ""))).date()
                # Description is split across three columns; join non-empty parts.
                parts = [s(row.get(f"Omschrijving-{i}", "")) for i in (1, 2, 3)]
                description = " ".join(p for p in parts if p)
                counter_name = s(row.get("Naam tegenpartij", ""))
                counter_iban = s(row.get("Tegenrekening IBAN/BBAN", ""))
                own_iban = s(row.get("IBAN/BBAN", ""))
                note = s(row.get("Betalingskenmerk", ""))
            else:  # legacy
                raw_amount = s(row.get("Bedrag (EUR)", "0")).replace(".", "").replace(",", ".") or "0"
                amount = float(raw_amount)
                if s(row.get("Af Bij", "")).lower() == "af":
                    amount = -amount
                tx_date = pd.to_datetime(s(row.get("Datum", "")), dayfirst=True).date()
                description = s(row.get("Omschrijving", ""))
                counter_name = s(row.get("Naam/Omschrijving", ""))
                counter_iban = s(row.get("Tegenrekening", ""))
                own_iban = s(row.get("Rekening", ""))
                note = ""

            # Skip filler rows: zero amount with no description and no
            # counterparty — these are not real transactions and collide on
            # import_hash, which used to crash the whole upload.
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
