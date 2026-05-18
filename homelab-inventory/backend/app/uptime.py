"""Uptime / downtime tracker for inventory items bound to HA entities.

A background task polls Home Assistant every POLL_INTERVAL_SECONDS, classifies
each tracked entity as "up" or "down", and accumulates the time spent in each
state. State lives in /data/uptime.json so it survives add-on restarts.

Up/down rule
------------
Any HA state in {"unavailable", "unknown", "off", "not_home"} or a missing
entity counts as DOWN. Everything else counts as UP. This matches the common
case: `binary_sensor` connectivity sensors report on/off, lights/media players
report unavailable when the host is offline, network pings report on/off.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from . import ha_client, storage


UPTIME_PATH = Path(os.getenv("UPTIME_PATH", "/data/uptime.json"))
POLL_INTERVAL_SECONDS = int(os.getenv("UPTIME_POLL_SECONDS", "30"))

DOWN_STATES = {"unavailable", "unknown", "off", "not_home", "none", ""}

_lock = RLock()
_task: Optional[asyncio.Task] = None


# ─── persistence ────────────────────────────────────────────────────────────

def _load() -> Dict[str, Any]:
    with _lock:
        if not UPTIME_PATH.exists():
            return {}
        try:
            return json.loads(UPTIME_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}


def _save(data: Dict[str, Any]) -> None:
    with _lock:
        UPTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".uptime-", suffix=".json.tmp", dir=UPTIME_PATH.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, UPTIME_PATH)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


# ─── classification ─────────────────────────────────────────────────────────

def _classify(state: Optional[str]) -> str:
    if state is None:
        return "down"
    return "down" if str(state).strip().lower() in DOWN_STATES else "up"


def _tracked_entity_ids() -> List[str]:
    inv = storage.load()
    ids: List[str] = []
    for hw in inv.hardware:
        if hw.ha_entity_id:
            ids.append(hw.ha_entity_id)
    for app in inv.applications:
        if app.ha_entity_id:
            ids.append(app.ha_entity_id)
    # de-dupe, preserve order
    seen: set = set()
    out: List[str] = []
    for e in ids:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


# ─── polling ────────────────────────────────────────────────────────────────

async def _poll_once() -> None:
    entity_ids = _tracked_entity_ids()
    if not entity_ids:
        return

    now = time.time()
    data = _load()

    # Fetch all states in one call, then index by entity_id.
    states = await ha_client.list_states()
    state_by_id: Dict[str, Optional[str]] = {s.get("entity_id"): s.get("state") for s in states}

    for entity_id in entity_ids:
        raw_state = state_by_id.get(entity_id)
        # If the bulk call returned nothing (e.g. HA not configured), try a single get.
        if raw_state is None and not states:
            one = await ha_client.get_state(entity_id)
            raw_state = one.get("state") if one else None

        status = _classify(raw_state)
        record = data.get(entity_id) or {
            "first_seen": now,
            "last_poll_at": now,
            "current_state": status,
            "current_state_started_at": now,
            "total_up_seconds": 0.0,
            "total_down_seconds": 0.0,
            "last_state_change_at": now,
            "last_raw_state": raw_state,
        }

        delta = max(0.0, now - record["last_poll_at"])
        if record["current_state"] == "up":
            record["total_up_seconds"] += delta
        else:
            record["total_down_seconds"] += delta

        if status != record["current_state"]:
            record["current_state"] = status
            record["current_state_started_at"] = now
            record["last_state_change_at"] = now

        record["last_poll_at"] = now
        record["last_raw_state"] = raw_state
        data[entity_id] = record

    # Drop entries no longer tracked.
    tracked_set = set(entity_ids)
    for stale in [k for k in data.keys() if k not in tracked_set]:
        del data[stale]

    _save(data)


async def _poll_loop() -> None:
    while True:
        try:
            await _poll_once()
        except Exception:
            pass
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start() -> None:
    global _task
    if _task is None or _task.done():
        loop = asyncio.get_event_loop()
        _task = loop.create_task(_poll_loop())


# ─── read API ───────────────────────────────────────────────────────────────

def snapshot() -> Dict[str, Any]:
    """Return current uptime state, augmented with the live current-streak duration."""
    now = time.time()
    data = _load()
    out: Dict[str, Any] = {}
    for entity_id, rec in data.items():
        current_streak = now - rec["current_state_started_at"]
        total_up = rec["total_up_seconds"]
        total_down = rec["total_down_seconds"]
        # Include the in-flight portion of the current state in the totals shown.
        delta = max(0.0, now - rec["last_poll_at"])
        if rec["current_state"] == "up":
            total_up += delta
        else:
            total_down += delta
        observed = total_up + total_down
        uptime_pct = (total_up / observed * 100.0) if observed > 0 else None
        out[entity_id] = {
            **rec,
            "current_streak_seconds": current_streak,
            "uptime_pct": uptime_pct,
            "observed_seconds": observed,
        }
    return out
