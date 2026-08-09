"""Categories and the rules that assign them."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Rule, Setting, Transaction
from ..services import categorize
from ..services import importer

router = APIRouter(tags=["categories"])


# ─── categories ─────────────────────────────────────────────────────────────

class CategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    color: str = Field("#64748b", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: Optional[str] = Field(None, max_length=40)
    parent_id: Optional[int] = None
    is_income: bool = False
    excluded_from_budget: bool = False
    sort_order: int = 100


@router.get("/categories/")
def list_categories(db: Session = Depends(get_db)):
    counts = dict(db.execute(
        select(Transaction.category_id, func.count()).group_by(Transaction.category_id)
    ).all())
    categories = db.scalars(select(Category).order_by(Category.sort_order, Category.name)).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "color": c.color,
            "icon": c.icon,
            "is_income": c.is_income,
            "excluded_from_budget": c.excluded_from_budget,
            "sort_order": c.sort_order,
            "transaction_count": counts.get(c.id, 0),
        }
        for c in categories
    ]


@router.post("/categories/")
def create_category(payload: CategoryIn, db: Session = Depends(get_db)):
    if payload.parent_id is not None and db.get(Category, payload.parent_id) is None:
        raise HTTPException(422, "Bovenliggende categorie bestaat niet.")
    exists = db.scalar(select(Category).where(
        Category.name == payload.name, Category.parent_id == payload.parent_id
    ))
    if exists is not None:
        raise HTTPException(409, "Er bestaat al een categorie met deze naam.")

    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    return {"id": category.id}


@router.put("/categories/{category_id}")
def update_category(category_id: int, payload: CategoryIn, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Categorie niet gevonden.")
    if payload.parent_id == category_id:
        raise HTTPException(422, "Een categorie kan niet haar eigen bovenliggende zijn.")
    for key, value in payload.model_dump().items():
        setattr(category, key, value)
    db.commit()
    return {"id": category.id}


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Deleting a category un-categorises its transactions; it never deletes
    them. The FK is ON DELETE SET NULL, so this is the database's behaviour
    rather than something the route has to remember."""
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(404, "Categorie niet gevonden.")
    affected = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.category_id == category_id)
    )
    db.delete(category)
    db.commit()
    return {"uncategorised": affected or 0}


# ─── rules ──────────────────────────────────────────────────────────────────

RuleField = Literal["any", "description", "counter_name", "counter_iban", "creditor_id", "bank_code"]
RuleOperator = Literal["contains", "equals", "startswith"]


class RuleIn(BaseModel):
    category_id: int
    value: str = Field(..., min_length=1, max_length=200)
    field: RuleField = "any"
    operator: RuleOperator = "contains"
    priority: int = Field(50, ge=1, le=10_000)
    active: bool = True
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    account_id: Optional[int] = None


# Rule values are stored verbatim, never stripped. A trailing space is part of
# the pattern: "ns " matches the Dutch Railways prefix without also matching
# "jetbrains", "transip" or "dienst uitvoering onderwijs". Trimming it turns a
# precise rule into a broad one, silently and after the fact — which is exactly
# what an import round-trip did before this was fixed.


def _cents(value: Optional[float]) -> Optional[int]:
    return None if value is None else int(round(value * 100))


@router.get("/rules/")
def list_rules(
    db: Session = Depends(get_db),
    category_id: Optional[int] = None,
    search: Optional[str] = Query(None, max_length=100),
):
    stmt = select(Rule).order_by(Rule.priority, Rule.id)
    if category_id:
        stmt = stmt.where(Rule.category_id == category_id)
    if search:
        stmt = stmt.where(Rule.value.ilike(f"%{search.strip()}%"))

    names = dict(db.execute(select(Category.id, Category.name)).all())
    return [
        {
            "id": r.id,
            "priority": r.priority,
            "active": r.active,
            "field": r.field,
            "operator": r.operator,
            "value": r.value,
            "amount_min": None if r.amount_min_cents is None else r.amount_min_cents / 100,
            "amount_max": None if r.amount_max_cents is None else r.amount_max_cents / 100,
            "account_id": r.account_id,
            "category_id": r.category_id,
            "category_name": names.get(r.category_id),
            "is_seed": r.is_seed,
            "origin": r.origin,
            "seed_batch": r.seed_batch,
            "note": r.note,
        }
        for r in db.scalars(stmt).all()
    ]


@router.get("/rules/preview")
def preview_rule(
    db: Session = Depends(get_db),
    field: RuleField = "any",
    operator: RuleOperator = "contains",
    value: str = Query(..., min_length=1, max_length=200),
    category_id: Optional[int] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    account_id: Optional[int] = None,
):
    """How many transactions a pattern touches, before you commit to it.

    Editing a rule is otherwise a blind action: you cannot see whether widening
    `esso` to `es` is harmless or catastrophic until after you saved it and
    re-ran everything.
    """
    haystacks = {
        "description": [Transaction.description],
        "counter_name": [Transaction.counter_name, Transaction.ultimate_party],
        "counter_iban": [Transaction.counter_iban],
        "creditor_id": [Transaction.creditor_id],
        "bank_code": [Transaction.bank_code],
    }.get(field, [Transaction.description, Transaction.counter_name, Transaction.ultimate_party])

    needle = value.lower()
    if operator == "equals":
        pattern = needle
        conditions = [func.lower(column) == pattern for column in haystacks]
    elif operator == "startswith":
        conditions = [func.lower(column).like(f"{needle}%") for column in haystacks]
    else:
        conditions = [func.lower(column).like(f"%{needle}%") for column in haystacks]

    condition = or_(*conditions)
    filters = [condition, Transaction.is_internal.is_(False)]
    if amount_min is not None:
        filters.append(Transaction.amount_cents >= int(round(amount_min * 100)))
    if amount_max is not None:
        filters.append(Transaction.amount_cents <= int(round(amount_max * 100)))
    if account_id:
        filters.append(Transaction.account_id == account_id)

    total = db.scalar(select(func.count()).select_from(Transaction).where(*filters)) or 0
    locked = db.scalar(
        select(func.count()).select_from(Transaction)
        .where(*filters, Transaction.category_locked.is_(True))
    ) or 0
    already = 0
    if category_id:
        already = db.scalar(
            select(func.count()).select_from(Transaction)
            .where(*filters, Transaction.category_id == category_id)
        ) or 0

    samples = db.scalars(
        select(Transaction).where(*filters).order_by(func.abs(Transaction.amount_cents).desc()).limit(5)
    ).all()

    return {
        "matches": total,
        "locked": locked,
        "already_in_category": already,
        "would_change": max(0, total - already - locked),
        "samples": [
            {
                "booked_on": s.booked_on.isoformat(),
                "amount": s.amount_cents / 100,
                "description": s.description[:60],
                "counter_name": s.counter_name[:40],
                "category": s.category.name if s.category else None,
            }
            for s in samples
        ],
    }


@router.post("/rules/")
def create_rule(payload: RuleIn, db: Session = Depends(get_db)):
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(422, "Categorie bestaat niet.")
    rule = Rule(
        category_id=payload.category_id, value=payload.value, field=payload.field,
        operator=payload.operator, priority=payload.priority, active=payload.active,
        amount_min_cents=_cents(payload.amount_min), amount_max_cents=_cents(payload.amount_max),
        account_id=payload.account_id,
    )
    db.add(rule)
    db.commit()
    return {"id": rule.id}


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, payload: RuleIn, db: Session = Depends(get_db)):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(404, "Regel niet gevonden.")
    rule.category_id = payload.category_id
    rule.value = payload.value
    rule.field = payload.field
    rule.operator = payload.operator
    rule.priority = payload.priority
    rule.active = payload.active
    rule.amount_min_cents = _cents(payload.amount_min)
    rule.amount_max_cents = _cents(payload.amount_max)
    rule.account_id = payload.account_id
    db.commit()
    return {"id": rule.id}


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(404, "Regel niet gevonden.")
    db.delete(rule)
    db.commit()
    return {"deleted": rule_id}


@router.post("/rules/reapply")
def reapply(
    include_locked: bool = Query(False),
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Re-run all rules over the ledger.

    Hand-picked categories survive by default. `include_locked` overrides them
    and is only ever reached through an explicit confirmation in the UI, which
    first calls this with `dry_run` to show exactly how many manual choices
    would be replaced.
    """
    return importer.reapply_rules_to_all(
        db, include_locked=include_locked, dry_run=dry_run
    )


# ─── provenance, export, import, conflicts ──────────────────────────────────

@router.get("/rules/export")
def export_rules(db: Session = Depends(get_db), include_counts: bool = Query(True)):
    """Every rule with where it came from, as JSON.

    Categories are exported by *name* rather than id, so the file survives a
    rebuild, a restore, or being handed to someone else. `matches` says how
    many transactions each rule currently owns, which is what makes the file
    reviewable rather than just a dump.
    """
    names = dict(db.execute(select(Category.id, Category.name)).all())

    counts: dict[int, int] = {}
    if include_counts:
        rules = db.scalars(select(Rule).order_by(Rule.priority, Rule.id)).all()
        compiled = categorize.compile_rules(db)
        by_category: dict[int, int] = {}
        for row in db.execute(
            select(Transaction.category_id, func.count()).group_by(Transaction.category_id)
        ).all():
            if row[0] is not None:
                by_category[row[0]] = row[1]
        # Per-rule attribution needs the same first-match-wins evaluation the
        # engine uses; anything cheaper would report numbers that do not add up.
        for tx in db.scalars(select(Transaction).where(Transaction.is_internal.is_(False))).yield_per(1000):
            for index, rule in enumerate(compiled):
                if categorize.match_rule(tx, [rule]) is not None:
                    counts[index] = counts.get(index, 0) + 1
                    break
        rule_ids = [r.id for r in rules if r.active and r.value.strip()]
        counts = {rule_ids[i]: n for i, n in counts.items() if i < len(rule_ids)}

    rules = db.scalars(select(Rule).order_by(Rule.priority, Rule.id)).all()
    return {
        "format": "financials-rules",
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed_batch_applied": (
            db.get(Setting, categorize.SETTING_SEED_BATCH).value
            if db.get(Setting, categorize.SETTING_SEED_BATCH) else None
        ),
        "categories": [
            {
                "name": c.name, "color": c.color, "icon": c.icon,
                "is_income": c.is_income, "excluded_from_budget": c.excluded_from_budget,
                "sort_order": c.sort_order,
            }
            for c in db.scalars(select(Category).order_by(Category.sort_order, Category.name)).all()
        ],
        "rules": [
            {
                "category": names.get(r.category_id),
                "field": r.field,
                "operator": r.operator,
                "value": r.value,
                "priority": r.priority,
                "active": r.active,
                "amount_min": None if r.amount_min_cents is None else r.amount_min_cents / 100,
                "amount_max": None if r.amount_max_cents is None else r.amount_max_cents / 100,
                "origin": r.origin,
                "seed_batch": r.seed_batch,
                "note": r.note,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "matches": counts.get(r.id) if include_counts else None,
            }
            for r in rules
        ],
    }


class RuleImportItem(BaseModel):
    category: str = Field(..., min_length=1, max_length=80)
    value: str = Field(..., min_length=1, max_length=200)
    field: RuleField = "any"
    operator: RuleOperator = "contains"
    priority: int = Field(50, ge=1, le=10_000)
    active: bool = True
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    note: Optional[str] = Field(None, max_length=200)


class RuleImport(BaseModel):
    rules: list[RuleImportItem] = Field(..., max_length=5000)
    create_missing_categories: bool = True
    replace_existing: bool = False


@router.post("/rules/import")
def import_rules(
    payload: RuleImport,
    dry_run: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Load rules from an exported file.

    Default is a merge that skips anything already present, so re-importing the
    same file twice changes nothing. `replace_existing` wipes only the rules —
    never a category, and never a transaction's category — so the worst case is
    that you re-run the rules afterwards.
    """
    known = {c.name.lower(): c for c in db.scalars(select(Category)).all()}

    created_categories: list[str] = []
    added: list[dict] = []
    skipped: list[dict] = []

    for item in payload.rules:
        category = known.get(item.category.lower())
        if category is None:
            if not payload.create_missing_categories:
                skipped.append({"value": item.value, "reason": f"categorie '{item.category}' bestaat niet"})
                continue
            if not dry_run:
                category = Category(name=item.category)
                db.add(category)
                db.flush()
                known[item.category.lower()] = category
            created_categories.append(item.category)

        if not payload.replace_existing and categorize_rule_exists(db, item):
            skipped.append({"value": item.value, "reason": "regel bestaat al"})
            continue

        added.append({"value": item.value, "category": item.category, "priority": item.priority})
        if not dry_run and category is not None:
            db.add(Rule(
                category_id=category.id, value=item.value, field=item.field,
                operator=item.operator, priority=item.priority, active=item.active,
                amount_min_cents=_cents(item.amount_min), amount_max_cents=_cents(item.amount_max),
                origin="import", note=item.note,
            ))

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return {
        "dry_run": dry_run,
        "added": len(added),
        "skipped": len(skipped),
        "created_categories": sorted(set(created_categories)),
        "details": {"added": added[:50], "skipped": skipped[:50]},
    }


def categorize_rule_exists(db: Session, item: RuleImportItem) -> bool:
    return db.scalar(
        select(Rule.id).where(
            Rule.field == item.field,
            Rule.operator == item.operator,
            func.lower(Rule.value) == item.value.lower(),
        ).limit(1)
    ) is not None


@router.get("/rules/conflicts")
def rule_conflicts(db: Session = Depends(get_db)):
    """Rules that fight each other, so a growing rule set stays trustworthy.

    Two kinds are reported:

    * **duplicate** — the same pattern pointing at two different categories.
      Only the higher-priority one ever fires; the other is dead weight.
    * **shadowed** — an earlier, broader pattern always matches first, so this
      rule can never fire. `huur ` in Wonen shadowing a later Huur rule is the
      textbook case.
    """
    rules = [
        r for r in db.scalars(select(Rule).order_by(Rule.priority, Rule.id)).all()
        if r.active and r.value.strip()
    ]
    names = dict(db.execute(select(Category.id, Category.name)).all())

    duplicates = []
    shadowed = []
    seen: dict[tuple[str, str, str], Rule] = {}

    for rule in rules:
        key = (rule.field, rule.operator, rule.value.lower())
        first = seen.get(key)
        if first is not None:
            if first.category_id != rule.category_id:
                duplicates.append({
                    "value": rule.value,
                    "winner": names.get(first.category_id),
                    "loser": names.get(rule.category_id),
                    "winner_priority": first.priority,
                    "loser_priority": rule.priority,
                })
            continue
        seen[key] = rule

    for index, rule in enumerate(rules):
        # Deliberately not stripped: a trailing space is part of the pattern.
        # "avia " does not occur in "transavia", and treating it as if it did
        # reports conflicts that do not exist.
        needle = rule.value.lower()
        for earlier in rules[:index]:
            if earlier.category_id == rule.category_id:
                continue
            if earlier.operator != "contains" or rule.operator != "contains":
                continue
            if earlier.field not in ("any", rule.field):
                continue
            other = earlier.value.lower()
            if other and other in needle:
                shadowed.append({
                    "value": rule.value,
                    "category": names.get(rule.category_id),
                    "shadowed_by": earlier.value,
                    "shadowed_by_category": names.get(earlier.category_id),
                })
                break

    return {
        "duplicates": duplicates,
        "shadowed": shadowed,
        "total_active_rules": len(rules),
    }


@router.post("/rules/reseed")
def reseed(db: Session = Depends(get_db)):
    """Apply any seed batch this database has not had yet.

    Runs on every start too; exposed here so a new batch can be pulled in
    without restarting the add-on.
    """
    return categorize.seed_defaults(db)
