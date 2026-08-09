"""Upload, preview, commit, replay and delete imported CSV files."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import ImportBatch
from ..parsers import AUTO, ParseError, format_choices, parse_csv
from ..security import contained_path
from ..services import importer

log = logging.getLogger("financials.import")

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("/formats")
def list_formats():
    """Contents of the "Bank / formaat" dropdown."""
    return format_choices()


@router.get("/")
def list_imports(db: Session = Depends(get_db)):
    batches = db.scalars(select(ImportBatch).order_by(ImportBatch.uploaded_at.desc())).all()
    return [
        {
            "id": b.id,
            "original_filename": b.original_filename,
            "format_key": b.format_key,
            "format_label": b.format_label,
            "sha256": b.sha256[:16],
            "size_bytes": b.size_bytes,
            "rows_parsed": b.rows_parsed,
            "rows_imported": b.rows_imported,
            "rows_duplicate": b.rows_duplicate,
            "rows_failed": b.rows_failed,
            "date_from": b.date_from.isoformat() if b.date_from else None,
            "date_to": b.date_to.isoformat() if b.date_to else None,
            "committed": b.committed,
            "file_removed": b.file_removed,
            "uploaded_at": b.uploaded_at.isoformat() if b.uploaded_at else None,
            "current_transactions": importer.count_transactions_for_batch(db, b.id),
            "errors": json.loads(b.errors_json) if b.errors_json else [],
        }
        for b in batches
    ]


@router.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    format_key: str = Form(AUTO),
    db: Session = Depends(get_db),
):
    """Store the file and return a preview. **Nothing is written to the
    ledger here** — the client calls `/imports/{id}/commit` after the user
    confirms what the preview shows.
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Bestand groter dan {config.MAX_UPLOAD_BYTES // 1048576} MB.")

    try:
        stored = importer.store_upload(file.file, file.filename or "upload.csv")
    except importer.ImportRejected as exc:
        raise HTTPException(400, str(exc)) from exc

    duplicate_of = db.scalar(
        select(ImportBatch).where(ImportBatch.sha256 == stored.sha256, ImportBatch.committed.is_(True))
    )

    try:
        text = importer.decode_csv_bytes(stored.path.read_bytes())
        result = parse_csv(text, format_key)
    except ParseError as exc:
        stored.path.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc

    batch = ImportBatch(
        original_filename=(file.filename or "upload.csv")[:255],
        stored_name=stored.stored_name,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        format_key=result.format_key,
        format_label=result.format_label,
    )
    db.add(batch)
    db.commit()

    preview = importer.build_preview(result, db)
    preview["batch_id"] = batch.id
    preview["original_filename"] = batch.original_filename
    preview["requested_format"] = format_key
    preview["duplicate_of"] = (
        None if duplicate_of is None
        else {
            "id": duplicate_of.id,
            "uploaded_at": duplicate_of.uploaded_at.isoformat() if duplicate_of.uploaded_at else None,
            "original_filename": duplicate_of.original_filename,
        }
    )
    return preview


@router.post("/{batch_id}/preview")
def repreview(
    batch_id: int,
    format_key: str = Query(AUTO),
    db: Session = Depends(get_db),
):
    """Re-parse a stored file as a different format — what happens when the
    user overrides the detected bank in the dropdown."""
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Import niet gevonden.")
    try:
        result = importer.parse_stored(batch, format_key)
    except (ParseError, importer.ImportRejected) as exc:
        raise HTTPException(422, str(exc)) from exc

    preview = importer.build_preview(result, db)
    preview["batch_id"] = batch.id
    preview["original_filename"] = batch.original_filename
    preview["requested_format"] = format_key
    return preview


@router.post("/{batch_id}/commit")
def commit(
    batch_id: int,
    format_key: str = Query(AUTO),
    db: Session = Depends(get_db),
):
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Import niet gevonden.")
    if batch.committed:
        raise HTTPException(409, "Deze import is al verwerkt.")

    try:
        result = importer.parse_stored(batch, format_key)
        importer.commit_import(db, batch, result)
    except (ParseError, importer.ImportRejected) as exc:
        raise HTTPException(422, str(exc)) from exc

    return {
        "batch_id": batch.id,
        "rows_imported": batch.rows_imported,
        "rows_duplicate": batch.rows_duplicate,
        "rows_failed": batch.rows_failed,
        "format_label": batch.format_label,
    }


@router.post("/{batch_id}/reimport")
def reimport(batch_id: int, db: Session = Depends(get_db)):
    """Replay a stored file. Existing rows dedupe on their hash, so this only
    adds what is genuinely missing — the button you press after fixing a rule
    rather than downloading from the bank again."""
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Import niet gevonden.")
    try:
        result = importer.parse_stored(batch)
        batch.committed = False
        importer.commit_import(db, batch, result)
    except (ParseError, importer.ImportRejected) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"batch_id": batch.id, "rows_imported": batch.rows_imported,
            "rows_duplicate": batch.rows_duplicate}


@router.get("/{batch_id}/download")
def download(batch_id: int, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if batch is None or not batch.stored_name or batch.file_removed:
        raise HTTPException(404, "Bestand niet beschikbaar.")

    # Containment check even though the name is a UUID we generated: the rule
    # is that every filesystem read derived from a request is checked, so a
    # future code path that lets a name in from outside cannot slip past.
    path = contained_path(config.UPLOAD_DIR, batch.stored_name)
    if path is None or not path.is_file():
        raise HTTPException(404, "Bestand niet gevonden op schijf.")

    return FileResponse(path, media_type="text/csv", filename=batch.original_filename)


@router.get("/{batch_id}/impact")
def impact(batch_id: int, db: Session = Depends(get_db)):
    """How many transactions a delete would take with it — shown in the
    confirmation dialog before the destructive choice is made."""
    if db.get(ImportBatch, batch_id) is None:
        raise HTTPException(404, "Import niet gevonden.")
    return {"transactions": importer.count_transactions_for_batch(db, batch_id)}


@router.delete("/{batch_id}")
def delete_import(
    batch_id: int,
    delete_transactions: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        return importer.delete_batch(db, batch_id, delete_transactions)
    except importer.ImportRejected as exc:
        raise HTTPException(404, str(exc)) from exc
