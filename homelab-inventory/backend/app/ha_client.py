"""Home Assistant client.

Talks to HA Core through the Supervisor proxy. Inside an HA add-on, the
Supervisor injects `SUPERVISOR_TOKEN` and routes `http://supervisor/core/*`
to the running Core. REST gives us /api/states; the device registry is only
exposed via the WebSocket API, so we open a short-lived WS session for that.

All calls degrade gracefully when no token is present (i.e. running outside
HA, in `docker-compose` dev), returning empty data so the rest of the app
keeps working.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx
import websockets


SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN")
HA_REST_BASE = os.getenv("HA_REST_BASE", "http://supervisor/core/api")
HA_WS_URL = os.getenv("HA_WS_URL", "ws://supervisor/core/websocket")

_DEVICE_CACHE: Dict[str, Any] = {"at": 0.0, "data": []}
_DEVICE_TTL_SECONDS = 60.0


def is_configured() -> bool:
    return bool(SUPERVISOR_TOKEN)


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }


async def get_state(entity_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single entity's state. Returns None if unavailable/missing."""
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{HA_REST_BASE}/states/{entity_id}", headers=_headers())
            if r.status_code != 200:
                return None
            return r.json()
    except Exception:
        return None


async def list_states() -> List[Dict[str, Any]]:
    """Fetch all entity states. Returns [] on failure."""
    if not is_configured():
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{HA_REST_BASE}/states", headers=_headers())
            if r.status_code != 200:
                return []
            return r.json()
    except Exception:
        return []


async def list_devices(force: bool = False) -> List[Dict[str, Any]]:
    """Fetch the HA device registry over WebSocket. Cached for 60s."""
    now = time.time()
    if not force and _DEVICE_CACHE["data"] and (now - _DEVICE_CACHE["at"]) < _DEVICE_TTL_SECONDS:
        return _DEVICE_CACHE["data"]
    if not is_configured():
        return []
    try:
        data = await _ws_call("config/device_registry/list")
    except Exception:
        return _DEVICE_CACHE["data"] or []
    _DEVICE_CACHE["at"] = now
    _DEVICE_CACHE["data"] = data or []
    return _DEVICE_CACHE["data"]


async def list_entities_for_devices() -> List[Dict[str, Any]]:
    """Fetch the HA entity registry over WebSocket (maps entity_id → device_id)."""
    if not is_configured():
        return []
    try:
        return await _ws_call("config/entity_registry/list") or []
    except Exception:
        return []


async def _ws_call(ws_type: str) -> Any:
    """Open a WS session, authenticate, send one command, return its result."""
    async with websockets.connect(HA_WS_URL, max_size=None) as ws:
        hello = json.loads(await ws.recv())
        if hello.get("type") != "auth_required":
            raise RuntimeError(f"unexpected hello: {hello}")
        await ws.send(json.dumps({"type": "auth", "access_token": SUPERVISOR_TOKEN}))
        auth_resp = json.loads(await ws.recv())
        if auth_resp.get("type") != "auth_ok":
            raise RuntimeError(f"auth failed: {auth_resp}")
        await ws.send(json.dumps({"id": 1, "type": ws_type}))
        msg = json.loads(await ws.recv())
        if not msg.get("success"):
            raise RuntimeError(f"ws call failed: {msg}")
        return msg.get("result", [])
