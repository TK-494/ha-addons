"""Import pipeline: store → preview → commit, and the deletion side of it.

The upload is written to disk and previewed *before* anything reaches the
ledger. The user sees which format was detected, which account it belongs to,
how many rows were found and what the first rows look like as the app
understood them — and only then confirms. That preview is the guard that would
have caught the predecessor's 271 credit-card rows landing at €0.00.

Stored files are kept so an import can be replayed after a rule change, and
can be deleted either on their own or together with the transactions they
produced.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import BinaryIO, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import config
from ..models import Account, ImportBatch, Transaction
from ..parsers import ParsedAccount, ParseError, ParseResult, decode_csv_bytes, parse_csv
from ..security import mask_iban
from . import categorize, transfers

log = logging.getLogger("financials.import")

PREVIEW_ROWS = 5


class ImportRejected(Exception):
    """Upload refused before any parsing — size, extension, emptiness."""


@dataclass
class StoredUpload:
    stored_name: str
    path: Path
    sha256: str
    size_bytes: int


def store_upload(fileobj: BinaryIO, original_filename: str) -> StoredUpload:
    """Stream an upload to disk under a generated name.

    Streaming in chunks rather than `read()` keeps a multi-GB body from being
    materialised in memory. The name on disk is a UUID: the client-supplied
    filename is metadata only and never touches the filesystem, so it cannot
    contain a path, a traversal sequence, or a surprising extension.
    """
    suffix = Path(original_filename).suffix.lower()
    if suffix not in config.ALLOWED_EXTENSIONS:
        raise ImportRejected(
            f"Alleen {', '.join(sorted(config.ALLOWED_EXTENSIONS))}-bestanden worden geaccepteerd."
        )

    config.ensure_dirs()
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    path = config.UPLOAD_DIR / stored_name

    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("wb") as out:
            while chunk := fileobj.read(config.UPLOAD_CHUNK_BYTES):
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise ImportRejected(
                        f"Bestand is groter dan {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                    )
                digest.update(chunk)
                out.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise

    if size == 0:
        path.unlink(missing_ok=True)
        raise ImportRejected("Het bestand is leeg.")

    return StoredUpload(stored_name, path, digest.hexdigest(), size)


def read_stored(batch: ImportBatch) -> str:
    if not batch.stored_name or batch.file_removed:
        raise ImportRejected(
            "Het oorspronkelijke bestand is verwijderd; upload het opnieuw om te herimporteren."
        )
    path = config.UPLOAD_DIR / batch.stored_name
    if not path.is_file():
        raise ImportRejected("Het oorspronkelijke bestand is niet meer op schijf gevonden.")
    return decode_csv_bytes(path.read_bytes())


def build_preview(result: ParseResult, db: Session) -> dict:
    """What the confirmation screen shows before anything is written."""
    rows = result.rows
    dates = [r.booked_on for r in rows]
    known_hashes = _existing_hashes(db, [r.import_hash for r in rows])
    duplicates = sum(1 for r in rows if r.import_hash in known_hashes)

    return {
        "format_key": result.format_key,
        "format_label": result.format_label,
        "accounts": [
            {
                "key": a.key,
                "kind": a.kind,
                "iban": a.iban,
                "card_last4": a.card_last4,
                "product_name": a.product_name,
                "known": db.scalar(select(Account.id).where(Account.key == a.key)) is not None,
            }
            for a in result.accounts.values()
        ],
        "rows_parsed": len(rows),
        "rows_failed": len(result.errors),
        "rows_duplicate": duplicates,
        "rows_new": len(rows) - duplicates,
        "date_from": min(dates).isoformat() if dates else None,
        "date_to": max(dates).isoformat() if dates else None,
        # The point of the preview: the first rows exactly as parsed. If the
        # amounts read 0.00 or the dates land in 1970, it is visible here.
        "sample": [
            {
                "booked_on": r.booked_on.isoformat(),
                "amount": r.amount_cents / 100,
                "description": r.description[:80],
                "counter_name": r.counter_name[:60],
                "balance_after": None if r.balance_after_cents is None else r.balance_after_cents / 100,
            }
            for r in rows[:PREVIEW_ROWS]
        ],
        "errors": [e.as_dict() for e in result.errors[:20]],
    }


def _existing_hashes(db: Session, hashes: list[str]) -> set[str]:
    """Which of these are already in the ledger. Chunked because SQLite's
    default variable limit is 999 and a 9k-row file blows straight past it."""
    found: set[str] = set()
    for start in range(0, len(hashes), 500):
        chunk = hashes[start:start + 500]
        found.update(
            db.scalars(select(Transaction.import_hash).where(Transaction.import_hash.in_(chunk))).all()
        )
    return found


def _upsert_account(db: Session, parsed: ParsedAccount) -> Account:
    account = db.scalar(select(Account).where(Account.key == parsed.key))
    if account is None:
        account = Account(
            key=parsed.key,
            kind=parsed.kind,
            iban=parsed.iban,
            card_last4=parsed.card_last4,
            product_name=parsed.product_name,
            settlement_iban=parsed.settlement_iban,
            currency=parsed.currency,
        )
        db.add(account)
        db.flush()
        log.info("Nieuwe rekening aangemaakt: %s", mask_iban(parsed.key))
    else:
        # Fill gaps from a newer export without overwriting user edits.
        account.product_name = account.product_name or parsed.product_name
        account.settlement_iban = account.settlement_iban or parsed.settlement_iban
    return account


def commit_import(db: Session, batch: ImportBatch, result: ParseResult) -> ImportBatch:
    """Write a parsed file into the ledger, then re-derive everything that
    depends on the whole dataset."""
    if len(result.rows) > config.MAX_ROWS_PER_FILE:
        raise ImportRejected(
            f"Bestand bevat {len(result.rows)} regels; het maximum is {config.MAX_ROWS_PER_FILE}."
        )

    accounts = {key: _upsert_account(db, parsed) for key, parsed in result.accounts.items()}
    known = _existing_hashes(db, [r.import_hash for r in result.rows])

    created: list[Transaction] = []
    seen: set[str] = set()
    for row in result.rows:
        if row.import_hash in known or row.import_hash in seen:
            continue
        seen.add(row.import_hash)
        account = accounts.get(row.account_key)
        if account is None:
            continue
        created.append(Transaction(
            account_id=account.id,
            import_batch_id=batch.id,
            import_hash=row.import_hash,
            booked_on=row.booked_on,
            value_date=row.value_date,
            processed_on=row.processed_on,
            amount_cents=row.amount_cents,
            balance_after_cents=row.balance_after_cents,
            currency=row.currency,
            description=row.description[:500],
            counter_iban=row.counter_iban[:40],
            counter_name=row.counter_name[:200],
            ultimate_party=row.ultimate_party[:200],
            bank_code=row.bank_code[:10],
            mandate_ref=row.mandate_ref[:80],
            creditor_id=row.creditor_id[:60],
            payment_ref=row.payment_ref[:120],
            bank_ref=row.bank_ref[:80],
            fx_amount_cents=row.fx_amount_cents,
            fx_currency=row.fx_currency[:3],
            fx_rate=row.fx_rate,
        ))

    db.add_all(created)
    db.flush()

    dates = [r.booked_on for r in result.rows]
    batch.format_key = result.format_key
    batch.format_label = result.format_label
    batch.rows_parsed = len(result.rows)
    batch.rows_imported = len(created)
    batch.rows_duplicate = len(result.rows) - len(created)
    batch.rows_failed = len(result.errors)
    batch.date_from = min(dates) if dates else None
    batch.date_to = max(dates) if dates else None
    batch.errors_json = json.dumps([e.as_dict() for e in result.errors[:200]]) if result.errors else None
    batch.committed = True
    db.commit()

    # Transfer matching runs over the whole table, not just the new rows: an
    # IBAN only becomes "one of yours" once its own export has been imported,
    # so earlier transfers to it pair up retroactively right here.
    transfers.rematch_all(db)
    recategorise_uncategorised(db)

    log.info(
        "Import %s: %s nieuw, %s duplicaat, %s mislukt",
        batch.id, batch.rows_imported, batch.rows_duplicate, batch.rows_failed,
    )
    return batch


def recategorise_uncategorised(db: Session) -> int:
    """Apply the rules to everything that has no category yet."""
    pending = db.scalars(
        select(Transaction).where(
            Transaction.category_id.is_(None),
            Transaction.is_internal.is_(False),
        )
    ).all()
    changed = categorize.apply_rules(db, pending)
    db.commit()
    return changed


def reapply_rules_to_all(db: Session, include_locked: bool = False) -> int:
    """Re-run every rule over the whole ledger — what you press after editing
    a rule. Manually categorised rows are preserved unless explicitly told
    otherwise."""
    rules = categorize.compile_rules(db)
    total = 0
    for offset in range(0, _count_transactions(db), 2000):
        chunk = db.scalars(
            select(Transaction).order_by(Transaction.id).offset(offset).limit(2000)
        ).all()
        total += categorize.apply_rules(db, chunk, rules, overwrite_locked=include_locked)
        db.commit()
    return total


def _count_transactions(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Transaction)) or 0


def delete_batch(db: Session, batch_id: int, delete_transactions: bool) -> dict:
    """Remove an import. Two flavours, both explicit:

    - file only: the CSV leaves the disk, the transactions stay in the ledger
    - file + transactions: a full undo of that import
    """
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise ImportRejected("Import niet gevonden.")

    removed_transactions = 0
    if delete_transactions:
        removed_transactions = db.scalar(
            select(func.count()).select_from(Transaction).where(Transaction.import_batch_id == batch_id)
        ) or 0
        db.execute(delete(Transaction).where(Transaction.import_batch_id == batch_id))

    if batch.stored_name:
        (config.UPLOAD_DIR / batch.stored_name).unlink(missing_ok=True)

    db.delete(batch)
    db.commit()

    if delete_transactions and removed_transactions:
        transfers.rematch_all(db)

    return {"deleted_transactions": removed_transactions, "batch_id": batch_id}


def count_transactions_for_batch(db: Session, batch_id: int) -> int:
    """Shown in the delete confirmation so the row count is known *before*
    the destructive choice, not after."""
    return db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.import_batch_id == batch_id)
    ) or 0


def parse_stored(batch: ImportBatch, format_key: Optional[str] = None) -> ParseResult:
    text = read_stored(batch)
    return parse_csv(text, format_key or batch.format_key)
