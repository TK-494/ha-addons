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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Category, Rule, Setting, Transaction

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


# ─── batch 2 ────────────────────────────────────────────────────────────────
#
# Added after seeing which counterparties actually stay uncategorised in real
# Dutch bank data. Every keyword here earns its place by matching something
# real; nothing is added on a hunch.
#
# `aliases` exist because a category may already be present under a name the
# user chose. Batch 1 shipped "Restaurant & Café"; renaming it must not cause
# batch 2 to create a duplicate alongside it.
#
# (names, color, icon, is_income, [keywords])
SEED_BATCH_2: list[tuple[tuple[str, ...], str, str, bool, list[str]]] = [
    (("Betaalverzoeken",), "#0ea5e9", "hand-coin", False, [
        "betaalverzoek", "tikkie", "via rabo betaalv"]),
    (("Bankkosten",), "#475569", "bank", False, [
        "debetrente", "koersopslag", "kosten gebruik betaalrekening",
        "kosten rabo", "rabo basispakket", "rabo standaardpakket"]),
    (("Belasting",), "#78350f", "gavel", False, [
        "gblt", "tribuut", "belastingsamenwerking"]),
    (("Leningen",), "#7f1d1d", "bank-transfer-out", False, [
        "duo hoofdrekening", "dienst uitvoering onderwijs"]),
    (("Brandstof",), "#ea580c", "gas-station", False, [
        "fieten olie", "snel tank", "tankstation"]),
    (("Auto",), "#57534e", "car-wrench", False, [
        "carwash", "car wash", "wasstraat"]),
    (("Sport & Fitness",), "#65a30d", "dumbbell", False, [
        "profit gym", "smart fit", " gym ", "crossfit"]),
    (("Zorg & Apotheek",), "#14b8a6", "medical-bag", False, [
        "infomedics", "chiropract", "umc ", "tandartspraktijk", "mondzorg"]),
    (("Restaurant, Café en Uitjes", "Restaurant & Café"), "#e11d48",
     "silverware-fork-knife", False, [
        "sodexo", "mcdonald", "mc donald", "sitedish", "vendingwork",
        "cafetaria", "snackbar", "bakkerij"]),
    (("Abonnementen",), "#8b5cf6", "repeat", False, [
        "youtube premiu", "google *youtube", "trakt.tv", "patreon"]),
    (("Kleding",), "#9333ea", "tshirt-crew", False, [
        "on that ass", "sokken", "zeeman", "wibra"]),
    (("Beleggen Extern", "Sparen & Beleggen"), "#047857", "chart-line", False, [
        "holland gold", "eff.nota", "koop fondsen", "verkoop fondsen"]),
    (("Gaming",), "#7c3aed", "gamepad-variant", False, [
        "steampowered", "steam games", "playstation", "nintendo", "xbox",
        "epic games", "blizzard", "riot games", "gog.com", "ubisoft"]),
    (("ICT Hardware en Software",), "#0891b2", "laptop", False, [
        "jetbrains", "github", "digitalocean", "hetzner", "transip",
        "cloudflare", "namecheap", "backblaze", "1password", "synology",
        "ubiquiti", "azerty", "megekko", "alternate.nl", "informatique"]),
    (("Motor en benodigdheden",), "#b45309", "motorbike", False, [
        "lowlands biker", "adventure bike", "motoport", "mkc moto",
        "royal enfield", "motorkleding", "motorbanden"]),
    (("Bios/Uitjes",), "#d946ef", "movie-open", False, [
        # "bioscoop" is deliberately absent: it contains "coop", which batch 1
        # claims for Boodschappen at a higher priority, so the rule could never
        # fire. The named cinemas cover it.
        "pathe", "pathé", "kinepolis", "vue cinema", "efteling",
        "walibi", "burgers zoo", "artis", "ticketmaster", "eventim", "theater"]),
    (("Dating",), "#f43f5e", "heart", False, [
        "tinder", "bumble", "happn", "lexa", "parship", "relatieplanet"]),
]

# Batch 1 uses priorities 10–270 and hand-made rules use 1, so batch 2 sits
# below both. That is the whole conflict story: a new keyword can only claim a
# transaction that nothing already claims. Raise a rule's priority by hand if
# you do want it to take precedence.
BATCH_2_BASE_PRIORITY = 500

SEED_BATCHES = {1: SEED, 2: SEED_BATCH_2}
LATEST_SEED_BATCH = max(SEED_BATCHES)
SETTING_SEED_BATCH = "seed_batch_applied"


def _find_or_create_category(
    db: Session, names: tuple[str, ...], color: str, icon: str,
    is_income: bool, sort_order: int,
) -> Category:
    """Reuse a category the user already has, under whichever of its known
    names, before creating a new one."""
    for name in names:
        existing = db.scalar(select(Category).where(func.lower(Category.name) == name.lower()))
        if existing is not None:
            return existing

    category = Category(
        name=names[0], color=color, icon=icon, is_income=is_income, sort_order=sort_order
    )
    db.add(category)
    db.flush()
    return category


def _rule_exists(db: Session, field: str, operator: str, value: str) -> bool:
    """Never add a keyword that is already present in any rule, whatever it
    points at — that is how you end up with two rules fighting over the same
    transactions."""
    return db.scalar(
        select(Rule.id).where(
            Rule.field == field,
            Rule.operator == operator,
            func.lower(Rule.value) == value.lower(),
        ).limit(1)
    ) is not None


def seed_defaults(db: Session) -> dict:
    """Apply any seed batch this database has not seen yet.

    Batches are numbered and applied once, so an add-on update can ship new
    keywords without touching what is already there and without re-adding what
    the user deleted on purpose.
    """
    applied_raw = db.get(Setting, SETTING_SEED_BATCH)
    applied = int(applied_raw.value) if applied_raw and applied_raw.value.isdigit() else 0

    # A database that predates batch numbering but already has rules has, by
    # definition, had batch 1.
    if applied == 0 and db.scalar(select(Rule.id).limit(1)) is not None:
        applied = 1

    added_categories = 0
    added_rules = 0

    if applied < 1:
        priority = 10
        for name, color, icon, is_income, keywords in SEED:
            category = _find_or_create_category(db, (name,), color, icon, is_income, priority)
            added_categories += 1
            for keyword in keywords:
                if _rule_exists(db, "any", "contains", keyword):
                    continue
                db.add(Rule(
                    priority=priority, field="any", operator="contains", value=keyword,
                    category_id=category.id, is_seed=True, origin="seed", seed_batch=1,
                ))
                added_rules += 1
            priority += 10

        if db.scalar(select(Category).where(Category.name == SETTLEMENT_CATEGORY)) is None:
            db.add(Category(
                name=SETTLEMENT_CATEGORY, color="#334155", icon="credit-card-sync",
                excluded_from_budget=True, sort_order=999,
            ))

    if applied < 2:
        priority = BATCH_2_BASE_PRIORITY
        for names, color, icon, is_income, keywords in SEED_BATCH_2:
            category = _find_or_create_category(db, names, color, icon, is_income, priority)
            for keyword in keywords:
                if _rule_exists(db, "any", "contains", keyword):
                    continue
                db.add(Rule(
                    priority=priority, field="any", operator="contains", value=keyword,
                    category_id=category.id, is_seed=True, origin="seed", seed_batch=2,
                ))
                added_rules += 1
            priority += 10

    if applied_raw is None:
        db.add(Setting(key=SETTING_SEED_BATCH, value=str(LATEST_SEED_BATCH)))
    else:
        applied_raw.value = str(LATEST_SEED_BATCH)

    db.commit()
    return {"from_batch": applied + 1, "to_batch": LATEST_SEED_BATCH, "rules_added": added_rules}


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
