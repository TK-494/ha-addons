"""JSON loader + in-memory cache voor het Health Dashboard.

Leest read-only uit HEALTH_DATA_DIR (default ./data/parsed).
Faalt fast bij ontbrekende files of verkeerde schema_version.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA_VERSION = 1

DATA_DIR = Path(os.environ.get("HEALTH_DATA_DIR", "./data/parsed"))

FILES = {
    "health": "health-data.json",
    "workouts": "workouts.json",
    "sleep": "sleep.json",
    "summary": "health-summary.json",
    "suspicious": "suspicious-workouts.json",
}

_lock = threading.RLock()
_store: dict[str, Any] = {}


def _read_json(name: str) -> dict[str, Any]:
    path = DATA_DIR / FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Verwacht JSON-bestand ontbreekt: {path}")
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    sv = obj.get("schema_version")
    if sv != EXPECTED_SCHEMA_VERSION:
        raise RuntimeError(
            f"{path.name}: schema_version {sv} != verwacht {EXPECTED_SCHEMA_VERSION}"
        )
    return obj


def load() -> dict[str, Any]:
    """Herlaad alle JSON-bronnen. Vervangt _store atomair."""
    with _lock:
        new_store: dict[str, Any] = {
            "health": _read_json("health"),
            "workouts": _read_json("workouts"),
            "sleep": _read_json("sleep"),
            "summary": _read_json("summary"),
            "suspicious": _read_json("suspicious"),
            "loaded_at": datetime.now().isoformat(timespec="seconds"),
            "mtimes": {
                key: datetime.fromtimestamp((DATA_DIR / fname).stat().st_mtime).isoformat(timespec="seconds")
                for key, fname in FILES.items()
            },
        }
        _store.clear()
        _store.update(new_store)
        return _store


def store() -> dict[str, Any]:
    if not _store:
        load()
    return _store


def _safe_store() -> dict[str, Any] | None:
    """Geef de store terug, of ``None`` als er nog geen data geimporteerd is."""
    try:
        return store()
    except FileNotFoundError:
        return None


def latest_day_key() -> str:
    days: dict[str, Any] = store()["health"]["days"]
    return max(days.keys())


def stale_status(latest: str, today_iso: str) -> dict[str, Any]:
    latest_d = date.fromisoformat(latest)
    today_d = date.fromisoformat(today_iso)
    days_ago = (today_d - latest_d).days
    if days_ago >= 30:
        level = "warn"
        message = "Nieuwe Apple Health export aanbevolen"
    elif days_ago >= 7:
        level = "mild"
        message = "Data is niet helemaal actueel"
    else:
        level = "ok"
        message = ""
    return {
        "latest_data_date": latest,
        "days_ago": days_ago,
        "is_today": days_ago == 0,
        "level": level,
        "message": message,
    }


def workouts_since(start: date) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = store()["workouts"]["workouts"]
    out = []
    for w in items:
        try:
            d = date.fromisoformat(w["date"])
        except (KeyError, ValueError):
            continue
        if d >= start:
            out.append(w)
    return out


def workout_aggregates(workouts: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, dict[str, float]] = {}
    for w in workouts:
        t = w.get("type", "Other")
        bucket = by_type.setdefault(t, {"count": 0, "duration_min": 0.0, "distance_km": 0.0})
        bucket["count"] += 1
        bucket["duration_min"] += float(w.get("duration_minutes", 0) or 0)
        bucket["distance_km"] += float(w.get("distance_km", 0) or 0)
    for v in by_type.values():
        v["duration_min"] = round(v["duration_min"], 1)
        v["distance_km"] = round(v["distance_km"], 2)
    return {"count": len(workouts), "by_type": by_type}


def workouts_by_date(workouts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for w in workouts:
        d = w.get("date")
        if not d:
            continue
        out.setdefault(d, []).append({
            "type": w.get("type", "Other"),
            "duration_min": round(float(w.get("duration_minutes", 0) or 0), 1),
            "distance_km": round(float(w.get("distance_km", 0) or 0), 2),
        })
    return out


def _get_path(obj: dict[str, Any], dotpath: str) -> Any:
    cur: Any = obj
    for part in dotpath.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def range_series(days_back: int, fields: list[str]) -> dict[str, Any]:
    s = _safe_store()
    days_dict: dict[str, dict[str, Any]] = (
        s.get("health", {}).get("days", {}) if s else {}
    )
    # Nog geen (of lege) dataset: lege maar geldige structuur teruggeven
    # i.p.v. een HTTP 500 via FileNotFoundError of max() op een lege dict.
    if not days_dict:
        today = date.today()
        start_empty = today - timedelta(days=days_back - 1)
        return {
            "start": start_empty.isoformat(),
            "end": today.isoformat(),
            "series": {f: [] for f in fields},
            "rolling_means": {},
            "has_data": False,
        }
    end_key = max(days_dict.keys())
    end_d = date.fromisoformat(end_key)
    start_d = end_d - timedelta(days=days_back - 1)

    series: dict[str, list[dict[str, Any]]] = {f: [] for f in fields}
    cursor = start_d
    while cursor <= end_d:
        key = cursor.isoformat()
        day_obj = days_dict.get(key)
        for f in fields:
            v = _get_path(day_obj, f) if day_obj else None
            series[f].append({"date": key, "v": v})
        cursor += timedelta(days=1)

    rolling: dict[str, list[dict[str, Any]]] = {}
    for f in fields:
        nums = [(p["date"], p["v"]) for p in series[f]]
        if not nums:
            continue
        if not all(isinstance(p[1], (int, float)) or p[1] is None for p in nums):
            continue
        window: list[float] = []
        out_points: list[dict[str, Any]] = []
        for d_iso, v in nums:
            window.append(float(v) if isinstance(v, (int, float)) else 0.0)
            if len(window) > 7:
                window.pop(0)
            if len(window) == 7:
                out_points.append({"date": d_iso, "v": round(sum(window) / 7, 1)})
        rolling[f"{f}_7d"] = out_points

    return {
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "series": series,
        "rolling_means": rolling,
        "has_data": True,
    }



_BASE_IMPORT_STATUS: dict[str, Any] = {
    "schema_version": EXPECTED_SCHEMA_VERSION,
    "scope": "volledige_export",
    "has_import": False,
    "status": "onbekend",
    "last_import_at": None,
    "processed_days": 0,
    "clean_workouts": 0,
    "suspicious_workouts": 0,
    "source": "fallback",
}

_ALLOWED_IMPORT_STATUSES = ("succesvol", "fout", "onbekend")


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _read_import_status_file() -> dict[str, Any] | None:
    target = DATA_DIR / "import-status.json"
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    status_value = payload.get("status")
    if status_value not in _ALLOWED_IMPORT_STATUSES:
        return None
    last_import_at = payload.get("last_import_at")
    if last_import_at is not None and not isinstance(last_import_at, str):
        last_import_at = None
    return {
        "status": status_value,
        "last_import_at": last_import_at,
        "processed_days": _coerce_int(payload.get("processed_days")),
        "clean_workouts": _coerce_int(payload.get("clean_workouts")),
        "suspicious_workouts": _coerce_int(payload.get("suspicious_workouts")),
    }


def _read_health_summary_fallback() -> dict[str, Any] | None:
    target = DATA_DIR / "health-summary.json"
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        return None
    totals = payload.get("totals")
    quality = payload.get("workout_quality")
    totals = totals if isinstance(totals, dict) else {}
    quality = quality if isinstance(quality, dict) else {}
    if not totals and not quality:
        return None
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str):
        generated_at = None
    return {
        "status": "succesvol",
        "last_import_at": generated_at,
        "processed_days": _coerce_int(totals.get("days_recorded")),
        "clean_workouts": _coerce_int(quality.get("clean_workouts_count")),
        "suspicious_workouts": _coerce_int(quality.get("suspicious_workouts_count")),
    }


def import_status() -> dict[str, Any]:
    """Lees de laatste importstatus.

    Leesvolgorde:
      1. ``import-status.json`` — bestaande status wordt altijd gerespecteerd
         (een ``fout``-status wordt nooit overschreven door de fallback).
      2. ``health-summary.json`` — synthetisch ``succesvol``-record als
         fallback wanneer de status-file ontbreekt of ongeldig is.
      3. Lege ``onbekend``-record.

    Geeft altijd alle vaste sleutels terug en bevat geen ruwe gezondheidsdata.
    """
    result = dict(_BASE_IMPORT_STATUS)

    primary = _read_import_status_file()
    if primary is not None:
        result.update(primary)
        result["has_import"] = True
        result["source"] = "import-status.json"
        return result

    fallback = _read_health_summary_fallback()
    if fallback is not None:
        result.update(fallback)
        result["has_import"] = True
        result["source"] = "health-summary.json"
        return result

    return result


def write_import_status(payload: dict[str, Any]) -> None:
    """Schrijf compacte importstatus zonder ruwe gezondheidsdata."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / "import-status.json"
    safe_payload = {
        "status": payload.get("status", "onbekend"),
        "last_import_at": payload.get("last_import_at"),
        "processed_days": int(payload.get("processed_days") or 0),
        "clean_workouts": int(payload.get("clean_workouts") or 0),
        "suspicious_workouts": int(payload.get("suspicious_workouts") or 0),
    }
    target.write_text(
        json.dumps(safe_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def _empty_summary_payload() -> dict[str, Any]:
    """Veilige lege structuur wanneer er nog geen data is (geen HTTP 500)."""
    return {
        "today": {},
        "stale": {"latest_data_date": None, "days_ago": None,
                  "is_today": False, "level": "empty", "message": ""},
        "totals": {},
        "workout_summary_alltime": {},
        "workouts_30d": {"count": 0, "by_type": {}},
        "workouts_90d": {"count": 0, "by_type": {}},
        "workouts_by_date_90d": {},
        "workouts_by_date_365d": {},
        "metric_availability": {},
        "date_range": {},
        "import_status": {},
        "has_data": False,
    }


def summary_payload() -> dict[str, Any]:
    s = _safe_store()
    if s is None or not s.get("health", {}).get("days"):
        return _empty_summary_payload()
    health = s["health"]
    summary = s["summary"]
    latest = latest_day_key()
    day = health["days"][latest]
    today_iso = date.today().isoformat()
    stale = stale_status(latest, today_iso)

    today_block = {
        "date": latest,
        "is_today": stale["is_today"],
        "days_ago": stale["days_ago"],
        "steps": day.get("steps"),
        "distance_km": day.get("distance_km"),
        "flights": day.get("flights"),
        "active_kcal": day.get("active_kcal"),
        "exercise_minutes": day.get("exercise_minutes"),
        "stand_hours": day.get("stand_hours"),
        "resting_hr": day.get("resting_hr"),
        "hrv_ms": day.get("hrv_ms"),
        "sleep": day.get("sleep"),
    }

    end_d = date.fromisoformat(latest)
    workouts_90d = workouts_since(end_d - timedelta(days=89))
    workouts_30d = workouts_since(end_d - timedelta(days=29))
    workouts_365d = workouts_since(end_d - timedelta(days=364))

    suspicious = s.get("suspicious", {}) or {}
    suspicious_workouts = suspicious.get("workouts", [])
    workouts_all = s["workouts"]["workouts"]

    import_status = {
        "json_loaded_at": s["loaded_at"],
        "parsed_at": summary.get("generated_at"),
        "export_made_at": summary.get("export_date"),
        "latest_data_date": latest,
        "clean_workouts": len(workouts_all),
        "suspicious_workouts": len(suspicious_workouts),
        "days_recorded": summary.get("totals", {}).get("days_recorded"),
        "data_mtimes": s["mtimes"],
        "filter_criteria": list(suspicious.get("filter_criteria", {}).keys()),
        "gps_routes_excluded": True,
    }

    return {
        "today": today_block,
        "stale": stale,
        "totals": summary.get("totals", {}),
        "workout_summary_alltime": summary.get("workout_summary", {}),
        "workouts_30d": workout_aggregates(workouts_30d),
        "workouts_90d": workout_aggregates(workouts_90d),
        "workouts_by_date_90d": workouts_by_date(workouts_90d),
        "workouts_by_date_365d": workouts_by_date(workouts_365d),
        "metric_availability": summary.get("metric_availability", {}),
        "date_range": summary.get("date_range", {}),
        "import_status": import_status,
    }
