import hashlib
import pandas as pd
from datetime import date
from io import StringIO
from typing import List, Dict, Any

# Keyword-based auto-categorization (Dutch)
CATEGORY_RULES: Dict[str, List[str]] = {
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
        "dsw", "anderzorg", "ditzo", "eno zorgverzekering"
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
        "harvey norman", "paypal", "klarna"
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
        "interpolis", "centraal beheer", "nationale nederlanden", "nn "
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
    text = content.decode("utf-8-sig")
    df = pd.read_csv(StringIO(text), dtype=str)
    df.columns = [c.strip() for c in df.columns]

    # Detect column layout
    # New format (post-2022): IBAN/BBAN, Naam, Tegenrekening IBAN/BBAN, Naam tegenpartij,
    #                          Notitie, Omschrijving, Valutadatum, Bedrag, Label
    col_map_new = {
        "own_iban": "IBAN/BBAN",
        "own_name": "Naam",
        "counter_iban": "Tegenrekening IBAN/BBAN",
        "counter_name": "Naam tegenpartij",
        "note": "Notitie",
        "description": "Omschrijving",
        "date": "Valutadatum",
        "amount": "Bedrag",
    }

    # Old format: Datum, Naam/Omschrijving, Rekening, Tegenrekening, Code, Af Bij, Bedrag (EUR), Soort, Omschrijving
    col_map_old = {
        "date": "Datum",
        "counter_name": "Naam/Omschrijving",
        "own_iban": "Rekening",
        "counter_iban": "Tegenrekening",
        "debit_credit": "Af Bij",
        "amount": "Bedrag (EUR)",
        "description": "Omschrijving",
    }

    is_new_format = "Valutadatum" in df.columns

    records = []
    for _, row in df.iterrows():
        try:
            if is_new_format:
                raw_amount = str(row.get("Bedrag", "0")).replace(",", ".").strip()
                amount = float(raw_amount)
                tx_date = pd.to_datetime(row.get("Valutadatum", "")).date()
                description = str(row.get("Omschrijving", "")).strip()
                counter_name = str(row.get("Naam tegenpartij", "")).strip()
                counter_iban = str(row.get("Tegenrekening IBAN/BBAN", "")).strip()
                own_iban = str(row.get("IBAN/BBAN", "")).strip()
                note = str(row.get("Notitie", "")).strip()
            else:
                raw_amount = str(row.get("Bedrag (EUR)", "0")).replace(".", "").replace(",", ".").strip()
                amount = float(raw_amount)
                if str(row.get("Af Bij", "")).lower() == "af":
                    amount = -amount
                tx_date = pd.to_datetime(row.get("Datum", ""), dayfirst=True).date()
                description = str(row.get("Omschrijving", "")).strip()
                counter_name = str(row.get("Naam/Omschrijving", "")).strip()
                counter_iban = str(row.get("Tegenrekening", "")).strip()
                own_iban = str(row.get("Rekening", "")).strip()
                note = ""

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
