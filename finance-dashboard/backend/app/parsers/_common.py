"""Shared helpers used by every bank-specific CSV parser.

Each per-bank parser turns its native CSV into a list of records with the
same shape, so the upload pipeline (transfer detection, auto-categorize,
dedupe) is bank-agnostic.
"""

import hashlib
from typing import Any, Dict, List


# Keyword-based auto-categorization (Dutch). Rules are evaluated in dict
# order and the first match wins, so place specific buckets first —
# otherwise generic ones (e.g. "Online Shopping" with "klarna") swallow
# rows that should land in a more specific bucket (e.g. "Afbetaling").
CATEGORY_RULES: Dict[str, List[str]] = {
    # Specific buckets first.
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

    # General buckets.
    "Boodschappen": [
        "albert heijn", "ah ", "jumbo", "lidl", "aldi", "plus supermarkt",
        "dirk", "spar", "coop", "deka", "boni", "poiesz", "vomar", "hoogvliet",
    ],
    "Inkomen": [
        "salaris", "loon ", "uitkering", "vakantiegeld", "toeslagen",
        "belastingdienst toeslag", "zorgtoeslag", "kinderbijslag",
    ],
    "Wonen": [
        "hypotheek", "huur", "woningcorp", "eigen haard", "ymere",
        "portaal", "vestia", "de alliantie", "stadswonen",
    ],
    "Energie": [
        "vattenfall", "eneco", "essent", "nuon", "greenchoice",
        "budget energie", "energie", "electra", "delta energie",
    ],
    "Zorgverzekering": [
        "zilveren kruis", "vgz", "cz ", "menzis", "achmea",
        "dsw", "anderzorg", "eno zorgverzekering",
    ],
    "Telefoon/Internet": [
        "kpn", "t-mobile", "vodafone", "ziggo", "odido",
        "tele2", "simyo", "lebara", "bliep",
    ],
    "Transport": [
        "ns ", "ov-chipkaart", "htm", "gvb", "ret", "connexxion",
        "arriva", "qbuzz", "parking", "p+r ", "anwb", "rdw",
    ],
    "Restaurant & Café": [
        "mcdonalds", "burger king", "kfc", "subway", "dominos",
        "pizza", "restaurant", "cafe ", "eetcafe", "lunchroom",
        "thuisbezorgd", "uber eats",
    ],
    "Sport & Fitness": [
        "basic-fit", "fitness", "sportschool", "sport", "gym", "zwembad",
    ],
    "Kleding": [
        "h&m", "zara", "primark", "c&a", "van haren", "wehkamp",
        "zalando", "about you", "vinted", "only", "jack & jones",
    ],
    "Online Shopping": [
        "bol.com", "amazon", "coolblue", "mediamarkt", "fnac",
        "harvey norman", "paypal",
    ],
    "Zorg & Apotheek": [
        "apotheek", "huisarts", "tandarts", "ziekenhuis", "fysiotherap",
        "boots", "da drogist", "kruidvat", "etos",
    ],
    "Abonnementen": [
        "spotify", "netflix", "disney", "videoland", "prime video",
        "adobe", "microsoft", "apple", "google storage",
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
    """Deterministic per-transaction hash used for idempotent imports.
    Bank-agnostic: only the user-visible fields go in, so re-importing the
    same period of the same statement collapses cleanly."""
    key = f"{row.get('date')}{row.get('amount')}{row.get('description')}{row.get('counter_iban')}"
    return hashlib.sha256(key.encode()).hexdigest()


def s(v: Any) -> str:
    """Normalise a pandas cell to a clean string. pandas with dtype=str
    turns missing values into the literal 'nan', which truthy-checks would
    otherwise let through."""
    out = str(v).strip()
    return "" if out.lower() == "nan" else out


def decode_csv_bytes(content: bytes) -> str:
    """Decode a bank CSV. Modern exports are UTF-8 (often with BOM),
    older ones (especially Rabobank pre-2022) are Windows-1252. The
    cp1252 fallback is what unblocked the 'byte 0xeb' crash on Dutch ë."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")
