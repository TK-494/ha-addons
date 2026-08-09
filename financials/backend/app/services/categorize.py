"""Categorisation rules engine.

Rules live in the `rules` table, not in this file. What lives here is the
*seed*: a starting set of Dutch categories and merchant keywords, inserted
once on first boot. After that the user owns them — editing a rule is a form
submission, not an add-on rebuild.

Evaluation is first-match-wins in `priority` order, so specific buckets are
seeded ahead of generic ones. "Brandstof" must beat "Transport", and
"Afbetaling" must beat "Online Shopping" or every Klarna payment lands in the
wrong place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, Rule, Transaction

# (name, color, icon, is_income, [keywords])
# Keywords with a trailing space are deliberate: "gea " matches Rabobank's
# `GEA <city>` ATM line without also matching every word containing "gea".
SEED: list[tuple[str, str, str, bool, list[str]]] = [
    ("Afbetaling", "#b91c1c", "credit-card-clock", False, [
        "klarna", "afterpay", "riverty", "in3 ", "billink", "achteraf betalen"]),
    ("Verzekeringen", "#0369a1", "shield-check", False, [
        "aegon", "a.s.r", " asr ", "allianz", "klaverblad", "univé", "unive",
        "dela", "monuta", "reaal", "ohra", "inshared", "ditzo", "interpolis",
        "centraal beheer", "nationale nederlanden", "verzekering"]),
    ("Leningen", "#7f1d1d", "bank-transfer-out", False, [
        "santander consumer", "defam", "qander", "alfam", "financial lease",
        "lening", "consumptief krediet", "persoonlijke lening"]),
    ("Sparen & Beleggen", "#047857", "piggy-bank", False, [
        "degiro", "bitvavo", "coinbase", "bux b.v.", "binck", "ishares",
        "vanguard", "blackrock", "scalable capital", "trading 212", "peaks ",
        "meesman", "beleggen"]),
    ("Belasting", "#78350f", "gavel", False, [
        "belastingdienst aanslag", "aanslag inkomstenbelasting",
        "motorrijtuigenbelasting", "waterschapsbelasting", "gemeentebelasting",
        "ozb ", "afvalstoffenheffing"]),
    ("Brandstof", "#ea580c", "gas-station", False, [
        "shell", "bp ", "esso", "tango", "tinq", "texaco", "total energies",
        "gulf ", "avia ", "firezone", "brandstof", "tankstation", "fuelplaza"]),
    ("Auto", "#57534e", "car-wrench", False, [
        "apk ", "rdw ", "kwikfit", "profile tyrecenter", "bovag",
        "autobedrijf", "garagebedrijf", "anwb wegen", "anwb pechhulp"]),
    ("Goede Doelen", "#be123c", "hand-heart", False, [
        "unicef", "rode kruis", "greenpeace", "wnf", "artsen zonder grenzen",
        "kwf", "hartstichting", "amnesty", "cliniclowns", "warchild", "donatie"]),
    ("Vakantie", "#0891b2", "beach", False, [
        "booking.com", "airbnb", "expedia", "hotels.com", "klm", "transavia",
        "ryanair", "easyjet", "tui ", "corendon", "sunweb", "anwb reizen",
        "anwb camping", "schiphol", "eurostar", "hotel", "camping"]),
    ("Kinderen", "#db2777", "baby-carriage", False, [
        "kinderopvang", "kdv ", "bso ", "kinderdagverblijf", "ouderbijdrage",
        "schoolgeld", "intertoys", "lobbes", "speelgoed", "prenatal"]),
    ("Huisdieren", "#a16207", "paw", False, [
        "dierenarts", "dierenkliniek", "pets place", "discus dier", "brekz",
        "dierenspeciaalzaak", "hondenvoer", "kattenvoer"]),
    ("Persoonlijke Verzorging", "#c026d3", "face-woman-shimmer", False, [
        "kapper", "kapsalon", "barbier", "schoonheidssalon", "nagelstudio",
        "parfumerie", "douglas ", "ici paris"]),
    ("Geldopname", "#6b7280", "cash", False, [
        "geldautomaat", "geldopname", "atm withdrawal", "gea "]),
    ("Boodschappen", "#16a34a", "cart", False, [
        "albert heijn", "ah to go", "ah ", "jumbo", "lidl", "aldi",
        "plus supermarkt", "dirk", "spar ", "coop", "deka", "boni", "poiesz",
        "vomar", "hoogvliet", "picnic", "crisp"]),
    ("Inkomen", "#15803d", "cash-plus", True, [
        "salaris", "loon ", "uitkering", "vakantiegeld", "toeslagen",
        "belastingdienst toeslag", "zorgtoeslag", "kinderbijslag",
        "huurtoeslag", "declaratie"]),
    ("Wonen", "#1d4ed8", "home", False, [
        "hypotheek", "huur ", "woningcorp", "eigen haard", "ymere", "portaal",
        "vestia", "de alliantie", "vve ", "servicekosten"]),
    ("Energie", "#f59e0b", "lightning-bolt", False, [
        "vattenfall", "eneco", "essent", "nuon", "greenchoice",
        "budget energie", "energie", "delta energie", "vitens", "waterbedrijf"]),
    ("Zorgverzekering", "#0d9488", "hospital-box", False, [
        "zilveren kruis", "vgz", "cz ", "menzis", "achmea", "dsw",
        "anderzorg", "eno zorgverzekering"]),
    ("Telefoon/Internet", "#4f46e5", "wifi", False, [
        "kpn", "t-mobile", "vodafone", "ziggo", "odido", "tele2", "simyo",
        "lebara", "bliep", "youfone"]),
    ("Transport", "#0284c7", "train-car", False, [
        "ns ", "ov-chipkaart", "htm", "gvb", "ret ", "connexxion", "arriva",
        "qbuzz", "parking", "p+r ", "q-park", "greenwheels", "swapfiets"]),
    ("Restaurant & Café", "#e11d48", "silverware-fork-knife", False, [
        "mcdonalds", "burger king", "kfc", "subway", "dominos", "pizza",
        "restaurant", "cafe ", "eetcafe", "lunchroom", "thuisbezorgd",
        "uber eats", "deliveroo", "starbucks"]),
    ("Sport & Fitness", "#65a30d", "dumbbell", False, [
        "basic-fit", "fitness", "sportschool", "sportvereniging", "zwembad"]),
    ("Kleding", "#9333ea", "tshirt-crew", False, [
        "h&m", "zara", "primark", "c&a", "van haren", "wehkamp", "zalando",
        "about you", "vinted", "only ", "jack & jones", "decathlon"]),
    ("Online Shopping", "#7c3aed", "package-variant", False, [
        "bol.com", "amazon", "coolblue", "mediamarkt", "action ", "hema",
        "ikea", "praxis", "gamma", "karwei", "paypal"]),
    ("Zorg & Apotheek", "#14b8a6", "medical-bag", False, [
        "apotheek", "huisarts", "tandarts", "ziekenhuis", "fysiotherap",
        "da drogist", "kruidvat", "etos"]),
    ("Abonnementen", "#8b5cf6", "repeat", False, [
        "spotify", "netflix", "disney", "videoland", "prime video", "adobe",
        "microsoft", "apple.com/bill", "itunes", "google storage", "hbo max",
        "youtube premium", "storytel", "nrc", "de volkskrant"]),
    ("Bankkosten", "#475569", "bank", False, [
        "kosten rekening", "abonnement rabobank", "betaalpakket",
        "creditcard bijdrage", "rentenota"]),
]

# Cards settle as one lump sum on the current account. That collection is not
# spend — the individual card rows are. Kept out of the seed above so it can
# be given its own colour and excluded from budgets.
SETTLEMENT_CATEGORY = "Creditcard afrekening"


def seed_defaults(db: Session) -> None:
    """Insert seed categories and rules once. Idempotent: an existing category
    of the same name is left exactly as the user edited it."""
    existing = {c.name: c for c in db.scalars(select(Category)).all()}
    has_rules = db.scalar(select(Rule.id).limit(1)) is not None
    priority = 10

    for name, color, icon, is_income, keywords in SEED:
        category = existing.get(name)
        if category is None:
            category = Category(
                name=name, color=color, icon=icon, is_income=is_income,
                sort_order=priority,
            )
            db.add(category)
            db.flush()
            existing[name] = category

        if not has_rules:
            for keyword in keywords:
                db.add(Rule(
                    priority=priority, field="any", operator="contains",
                    value=keyword, category_id=category.id, is_seed=True,
                ))
        priority += 10

    if SETTLEMENT_CATEGORY not in existing:
        db.add(Category(
            name=SETTLEMENT_CATEGORY, color="#334155", icon="credit-card-sync",
            excluded_from_budget=True, sort_order=999,
        ))
    db.commit()


@dataclass(frozen=True)
class CompiledRule:
    field: str
    operator: str
    needle: str
    amount_min: Optional[int]
    amount_max: Optional[int]
    account_id: Optional[int]
    category_id: int


def compile_rules(db: Session) -> list[CompiledRule]:
    """Load active rules once per import instead of per row — 9k rows against
    a few hundred rules is the difference between instant and a minute."""
    stmt = select(Rule).where(Rule.active.is_(True)).order_by(Rule.priority, Rule.id)
    return [
        CompiledRule(
            field=r.field,
            operator=r.operator,
            needle=r.value.lower().strip(),
            amount_min=r.amount_min_cents,
            amount_max=r.amount_max_cents,
            account_id=r.account_id,
            category_id=r.category_id,
        )
        for r in db.scalars(stmt).all()
        if r.value and r.value.strip()
    ]


def _haystack(tx: Transaction, field: str) -> str:
    if field == "description":
        return tx.description.lower()
    if field == "counter_name":
        return f"{tx.counter_name} {tx.ultimate_party}".lower()
    if field == "counter_iban":
        return tx.counter_iban.lower()
    if field == "creditor_id":
        return tx.creditor_id.lower()
    if field == "bank_code":
        return tx.bank_code.lower()
    return f"{tx.description} {tx.counter_name} {tx.ultimate_party}".lower()


def match_rule(tx: Transaction, rules: Iterable[CompiledRule]) -> Optional[int]:
    """Return the category id of the first matching rule, or None."""
    for rule in rules:
        if rule.account_id is not None and rule.account_id != tx.account_id:
            continue
        if rule.amount_min is not None and tx.amount_cents < rule.amount_min:
            continue
        if rule.amount_max is not None and tx.amount_cents > rule.amount_max:
            continue

        hay = _haystack(tx, rule.field)
        if rule.operator == "equals":
            hit = hay.strip() == rule.needle
        elif rule.operator == "startswith":
            hit = hay.lstrip().startswith(rule.needle)
        else:
            hit = rule.needle in hay
        if hit:
            return rule.category_id
    return None


def apply_rules(
    db: Session,
    transactions: Iterable[Transaction],
    rules: Optional[list[CompiledRule]] = None,
    overwrite_locked: bool = False,
) -> int:
    """Categorise transactions in place. Returns the number changed.

    A transaction whose category was set by hand (`category_locked`) is left
    alone unless explicitly overridden — an automated re-run must never undo
    a human decision.
    """
    rules = compile_rules(db) if rules is None else rules
    changed = 0
    for tx in transactions:
        if tx.category_locked and not overwrite_locked:
            continue
        # Internal transfers are not spend and must not pick up a spend
        # category from a description that happens to contain a merchant word.
        if tx.is_internal:
            continue
        category_id = match_rule(tx, rules)
        if category_id is not None and category_id != tx.category_id:
            tx.category_id = category_id
            changed += 1
    return changed
