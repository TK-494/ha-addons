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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import websockets


# Defaults assume we're an HA add-on with Supervisor's reverse proxy at
# http://supervisor/core/*. If the user pastes ha_base_url in options.json
# we'll switch to that (with a derived WS URL).
_DEFAULT_REST = "http://supervisor/core/api"
_DEFAULT_WS = "ws://supervisor/core/websocket"
HA_REST_BASE = os.getenv("HA_REST_BASE", _DEFAULT_REST)
HA_WS_URL = os.getenv("HA_WS_URL", _DEFAULT_WS)

# Order matters: SUPERVISOR_TOKEN is the modern name; HASSIO_TOKEN is the
# legacy one (still injected by older HA versions and some forks); HA_TOKEN
# is our own opt-in env name for users pasting a long-lived token directly.
_TOKEN_ENV_VARS = ("SUPERVISOR_TOKEN", "HASSIO_TOKEN", "HA_TOKEN")

# HA Supervisor writes the add-on's user-configured options to this path,
# as a JSON object keyed by the field names in config.yaml `options:`.
_OPTIONS_PATH = Path(os.getenv("OPTIONS_PATH", "/data/options.json"))

_DEVICE_CACHE: Dict[str, Any] = {"at": 0.0, "data": []}
_DEVICE_TTL_SECONDS = 60.0


def _load_options() -> Dict[str, Any]:
    """Read /data/options.json if present. Returns {} on any error."""
    try:
        if _OPTIONS_PATH.exists():
            return json.loads(_OPTIONS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _token_with_source() -> Tuple[Optional[str], Optional[str]]:
    """Look up the auth token. Order: options.json → env vars.

    options.json is the escape hatch when Supervisor isn't injecting a token
    (Roel's exact situation: container env is OLDPWD/PATH/PWD/SHLVL only).
    The user pastes a Long-Lived Access Token in the add-on Configuration tab
    and HA writes it to /data/options.json as `ha_token`. Same field works in
    standalone docker via the option file mount.
    """
    opts = _load_options()
    t = opts.get("ha_token")
    if isinstance(t, str) and t.strip():
        return t.strip(), "options.json:ha_token"
    for var in _TOKEN_ENV_VARS:
        v = os.getenv(var)
        if v:
            return v, var
    return None, None


def _token() -> Optional[str]:
    """Resolve the auth token at call time (not import time)."""
    return _token_with_source()[0]


def token_env_var() -> Optional[str]:
    """Diagnostic: where the current token came from."""
    return _token_with_source()[1]


def _base_from_options() -> Optional[str]:
    """A user-supplied ha_base_url like `http://homeassistant.local:8123`."""
    opts = _load_options()
    raw = opts.get("ha_base_url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip().rstrip("/")


def rest_base() -> str:
    """REST base URL. Honors options.json ha_base_url → env → Supervisor proxy."""
    base = _base_from_options()
    if base:
        # When the user gives `http://homeassistant.local:8123` we want `/api`.
        return base + "/api"
    return os.getenv("HA_REST_BASE", _DEFAULT_REST).rstrip("/")


def ws_url() -> str:
    """WS URL. Derived from ha_base_url when set, otherwise env / Supervisor proxy."""
    base = _base_from_options()
    if base:
        scheme = "wss" if base.startswith("https://") else "ws"
        host = base.split("://", 1)[1]
        return f"{scheme}://{host}/api/websocket"
    return os.getenv("HA_WS_URL", _DEFAULT_WS)


def is_configured() -> bool:
    return bool(_token())


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }


async def get_state(entity_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single entity's state. Returns None if unavailable/missing."""
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{rest_base()}/states/{entity_id}", headers=_headers())
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
            r = await client.get(f"{rest_base()}/states", headers=_headers())
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
    async with websockets.connect(ws_url(), max_size=None) as ws:
        hello = json.loads(await ws.recv())
        if hello.get("type") != "auth_required":
            raise RuntimeError(f"unexpected hello: {hello}")
        await ws.send(json.dumps({"type": "auth", "access_token": _token()}))
        auth_resp = json.loads(await ws.recv())
        if auth_resp.get("type") != "auth_ok":
            raise RuntimeError(f"auth failed: {auth_resp}")
        await ws.send(json.dumps({"id": 1, "type": ws_type}))
        msg = json.loads(await ws.recv())
        if not msg.get("success"):
            raise RuntimeError(f"ws call failed: {msg}")
        return msg.get("result", [])
