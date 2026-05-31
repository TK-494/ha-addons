"""FastAPI dashboard voor het Health Dashboard.

Lokaal-only: bind op 127.0.0.1. Reload-endpoint blijft token-protected; upload is open op het interne netwerk.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import data

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
INDEX_FILE = STATIC_DIR / "index.html"
UPLOAD_FORM = STATIC_DIR / "upload.html"
PARSER = APP_DIR.parent / "parser" / "parse_health.py"
HEALTH_DIR = Path(os.environ.get("HEALTH_DIR", "./data"))

RELOAD_TOKEN = os.environ.get("RELOAD_TOKEN", "")

app = FastAPI(title="Health Dashboard", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def _startup() -> None:
    try:
        data.load()
    except FileNotFoundError:
        pass


@app.get("/")
def root() -> FileResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="index.html ontbreekt")
    return FileResponse(str(INDEX_FILE))


@app.get("/upload")
def upload_form() -> FileResponse:
    if not UPLOAD_FORM.exists():
        raise HTTPException(status_code=404, detail="upload.html ontbreekt")
    return FileResponse(str(UPLOAD_FORM))


@app.get("/api/summary")
def api_summary() -> JSONResponse:
    return JSONResponse(data.summary_payload())


@app.get("/api/import/status")
def api_import_status() -> JSONResponse:
    return JSONResponse(data.import_status())


@app.get("/api/range")
def api_range(
    days: int = Query(30, ge=1, le=365),
    fields: str = Query("steps"),
) -> JSONResponse:
    field_list = [f.strip() for f in fields.split(",") if f.strip()]
    if not field_list:
        raise HTTPException(status_code=400, detail="fields mag niet leeg zijn")
    return JSONResponse(data.range_series(days, field_list))


@app.post("/api/reload")
def api_reload(x_reload_token: str | None = Header(default=None)) -> JSONResponse:
    if not RELOAD_TOKEN:
        raise HTTPException(status_code=503, detail="RELOAD_TOKEN niet geconfigureerd")
    if x_reload_token != RELOAD_TOKEN:
        raise HTTPException(status_code=401, detail="ongeldig token")
    store = data.load()
    return JSONResponse({
        "status": "reloaded",
        "loaded_at": store["loaded_at"],
        "days": len(store["health"]["days"]),
        "workouts": len(store["workouts"]["workouts"]),
    })


@app.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
) -> JSONResponse:
    started = datetime.now()
    ts = started.strftime("%Y%m%d-%H%M%S")
    uploads = HEALTH_DIR / "uploads"
    uploads.mkdir(mode=0o700, parents=True, exist_ok=True)
    archived = uploads / f"export-{ts}.zip"

    size = 0
    with archived.open("wb") as fh:
        while True:
            chunk = await file.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            size += len(chunk)

    if size < 1024:
        archived.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"upload te klein: {size} bytes")

    # Kopie naar default parser-input (parse_health.py leest export.zip)
    shutil.copy2(archived, HEALTH_DIR / "export.zip")

    proc = subprocess.run(
        ["python3", str(PARSER)],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout)[-500:]
        data.write_import_status({
            "status": "fout",
            "last_import_at": started.isoformat(timespec="seconds"),
            "processed_days": 0,
            "clean_workouts": 0,
            "suspicious_workouts": 0,
        })
        raise HTTPException(status_code=500, detail=f"parser fout: {tail}")

    store = data.load()
    latest = max(store["health"]["days"].keys())
    duration = (datetime.now() - started).total_seconds()
    size_mb = size / (1024 * 1024)
    summary = store["summary"]
    quality = summary.get("workout_quality", {})
    data.write_import_status({
        "status": "succesvol",
        "last_import_at": datetime.now().isoformat(timespec="seconds"),
        "processed_days": len(store["health"]["days"]),
        "clean_workouts": len(store["workouts"]["workouts"]),
        "suspicious_workouts": int(quality.get("suspicious_workouts_count") or 0),
    })

    return JSONResponse({
        "status": "ok",
        "latest_date": latest,
        "archived": archived.name,
        "size_mb": round(size_mb, 1),
        "duration_s": round(duration, 1),
        "days": len(store["health"]["days"]),
        "workouts": len(store["workouts"]["workouts"]),
    })
