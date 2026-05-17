import hashlib
import pandas as pd
from datetime import date
from io import StringIO
from typing import List, Dict, Any

# Keyword-based auto-categorization (Dutch). Rules are evaluated in dict order
# and the first match wins, so place specific/important categories first —
# otherwise generic ones (e.g. "Online Shopping" with "klarna") swallow rows
# that should land in a more specific bucket (e.g. "Afbetaling").
CATEGORY_RULES: Dict[str, List[str]] = {
    # New specific buckets — evaluated before existing generic ones.
    "Afbetaling": [
        "klarna", "afterpay", "riverty", "in3 ", "billink",
        "buy now pay later", "achteraf betalen",
    ],
    "Verzekeringen": [
        "aegon", "a.s.r", " asr ", "allianz", "klaverblad", "univé", "unive",
        "dela", "monuta", "reaal", "ohra", "inshared", "ditzo",
        "interpolis", "centraal beheer", "nationale nederlanden", " nn ",
        "verzekering",
    ],
    "Leningen": [
        "santander consumer", "defam", "qander", "alfam",
        "financial lease", "lening", "krediet", "consumptief krediet",
        "persoonlijke lening",
    ],

    # Existing buckets.
    "Boodschappen": [
        "albert heijn", "ah ", "jumbo", "lidl", "aldi", "plus supermarkt",
        "dirk", "spar", "coop", "deka", "boni", "poiesz", "vomar", "hoogvliet"
    ],
    "Inkomen": [
        "salaris", "loon ", "uitkering", "vakantiegeld", "toeslagen",
        "belastingdienst toeslag", "zorgtoeslag", "kinderbijslag"
    ],
    "Wonen": [
        "hypotheek", "huur", "woningcorp", "eigen haard", "ymere",
        "portaal", "vestia", "de alliantie", "stadswonen"
    ],
    "Energie": [
        "vattenfall", "eneco", "essent", "nuon", "greenchoice",
        "budget energie", "energie", "electra", "delta energie"
    ],
    "Zorgverzekering": [
        "zilveren kruis", "vgz", "cz ", "menzis", "achmea",
        "dsw", "anderzorg", "eno zorgverzekering"
    ],
    "Telefoon/Internet": [
        "kpn", "t-mobile", "vodafone", "ziggo", "odido",
        "tele2", "simyo", "lebara", "bliep"
    ],
    "Transport": [
        "ns ", "ov-chipkaart", "htm", "gvb", "ret", "connexxion",
        "arriva", "qbuzz", "parking", "p+r ", "anwb", "rdw"
    ],
    "Restaurant & Café": [
        "mcdonalds", "burger king", "kfc", "subway", "dominos",
        "pizza", "restaurant", "cafe ", "eetcafe", "lunchroom", "thuisbezorgd", "uber eats"
    ],
    "Sport & Fitness": [
        "basic-fit", "fitness", "sportschool", "sport", "gym", "zwembad"
    ],
    "Kleding": [
        "h&m", "zara", "primark", "c&a", "van haren", "wehkamp",
        "zalando", "about you", "vinted", "only", "jack & jones"
    ],
    "Online Shopping": [
        "bol.com", "amazon", "coolblue", "mediamarkt", "fnac",
        "harvey norman", "paypal",
    ],
    "Zorg & Apotheek": [
        "apotheek", "huisarts", "tandarts", "ziekenhuis", "fysiotherap",
        "boots", "da drogist", "kruidvat", "etos"
    ],
    "Abonnementen": [
        "spotify", "netflix", "disney", "videoland", "prime video",
        "adobe", "microsoft", "apple", "google storage"
    ],
    "Bank & Verzekering": [
        "rente", "kosten rekening", "abonnement rabobank",
    ],
}


def auto_categorize(description: str, counter_name: str) -> str | None:
    text = (description + " " + counter_name).lower()
    for category, keywords in CATEGORY_RULES.items():
        for kw in keywords:
            if kw in text:
                return category
    return None


def make_hash(row: Dict[str, Any]) -> str:
    key = f"{row.get('date')}{row.get('amount')}{row.get('description')}{row.get('counter_iban')}"
    return hashlib.sha256(key.encode()).hexdigest()


def parse_rabobank_csv(content: bytes) -> List[Dict[str, Any]]:
    # Rabobank exports vary: newer ones are UTF-8 (sometimes with BOM), older
    # ones are Windows-1252 (cp1252) — that's what produces the 0xeb-on-ë crash.
    # Try the modern encoding first, fall back to cp1252.
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("utf-8", errors="replace")
    df = pd.read_csv(StringIO(text), dtype=str)
    df.columns = [c.strip() for c in df.columns]

    # Rabobank has shipped at least three CSV layouts over the years:
    # - "current"  (≈2018+): Datum, Bedrag (signed), Tegenrekening IBAN/BBAN,
    #                         Naam tegenpartij, Omschrijving-1/2/3, …
    # - "valuta"   (post-2022 variant): Valutadatum, Bedrag, Omschrijving, Notitie
    # - "legacy"   (pre-IBAN-rename): Datum, Bedrag (EUR), Af Bij, Naam/Omschrijving
    cols = set(df.columns)
    if "Valutadatum" in cols:
        fmt = "valuta"
    elif "Omschrijving-1" in cols or "Tegenrekening IBAN/BBAN" in cols:
        fmt = "current"
    else:
        fmt = "legacy"

    def _s(v) -> str:
        # pandas with dtype=str turns missing cells into the literal "nan".
        s = str(v).strip()
        return "" if s.lower() == "nan" else s

    records = []
    for _, row in df.iterrows():
        try:
            if fmt == "valuta":
                raw_amount = _s(row.get("Bedrag", "0")).replace(",", ".") or "0"
                amount = float(raw_amount)
                tx_date = pd.to_datetime(_s(row.get("Valutadatum", ""))).date()
                description = _s(row.get("Omschrijving", ""))
                counter_name = _s(row.get("Naam tegenpartij", ""))
                counter_iban = _s(row.get("Tegenrekening IBAN/BBAN", ""))
                own_iban = _s(row.get("IBAN/BBAN", ""))
                note = _s(row.get("Notitie", ""))
            elif fmt == "current":
                # Bedrag is signed with comma decimal: "-12,34" or "1500,00".
                raw_amount = _s(row.get("Bedrag", "0")).replace(",", ".") or "0"
                amount = float(raw_amount)
                # Datum is typically YYYYMMDD or YYYY-MM-DD — let pandas guess.
                tx_date = pd.to_datetime(_s(row.get("Datum", ""))).date()
                # Description is split across three columns; join non-empty parts.
                parts = [_s(row.get(f"Omschrijving-{i}", "")) for i in (1, 2, 3)]
                description = " ".join(p for p in parts if p)
                counter_name = _s(row.get("Naam tegenpartij", ""))
                counter_iban = _s(row.get("Tegenrekening IBAN/BBAN", ""))
                own_iban = _s(row.get("IBAN/BBAN", ""))
                note = _s(row.get("Betalingskenmerk", ""))
            else:  # legacy
                raw_amount = _s(row.get("Bedrag (EUR)", "0")).replace(".", "").replace(",", ".") or "0"
                amount = float(raw_amount)
                if _s(row.get("Af Bij", "")).lower() == "af":
                    amount = -amount
                tx_date = pd.to_datetime(_s(row.get("Datum", "")), dayfirst=True).date()
                description = _s(row.get("Omschrijving", ""))
                counter_name = _s(row.get("Naam/Omschrijving", ""))
                counter_iban = _s(row.get("Tegenrekening", ""))
                own_iban = _s(row.get("Rekening", ""))
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
