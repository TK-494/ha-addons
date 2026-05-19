"""FastAPI app for the Homelab Inventory add-on.

Endpoints:
  GET  /api/health                — liveness probe
  GET  /api/inventory             — full inventory as JSON
  PUT  /api/inventory             — replace full inventory (JSON body)
  GET  /api/inventory/raw         — raw YAML text
  PUT  /api/inventory/raw         — replace raw YAML text (validated)

  GET    /api/{section}                — list items in section
  POST   /api/{section}                — create item
  PUT    /api/{section}/{item_id}      — update item
  DELETE /api/{section}/{item_id}      — delete item

  Where {section} ∈ {hardware, applications, integrations,
                     network/subnets, network/vlans, network/hosts}.

Static frontend mounted at /.
"""

import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from . import discovery, ha_client, storage, uptime
from .schemas import (
    Hardware,
    Application,
    Integration,
    Subnet,
    Vlan,
    Host,
    Inventory,
)
from .seed import initial_inventory


app = FastAPI(title="Homelab Inventory", version="1.2.5")


# Security headers. The app is served same-origin under HA Ingress, so no CORS
# is required — dropping the wildcard middleware narrows what a misconfigured
# reverse proxy or sibling add-on could do. CSP whitelists exactly the three
# CDNs the SPA pulls (tailwind, alpinejs, vis-network) and bans inline event
# handlers; Alpine's `x-data`/`x-text` attrs are evaluated by Alpine itself,
# not by the browser as inline JS, so `script-src` doesn't need 'unsafe-inline'.
# 'unsafe-eval' is required by Alpine 3's expression evaluator.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", _CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        return response


# When the add-on uses host_network: true (required for arp-scan), uvicorn
# has to listen on 0.0.0.0 so Supervisor's ingress proxy can reach it from
# its own container — but that also makes the port reachable from the LAN.
# Supervisor stamps every ingress-proxied request with X-Hass-User-* /
# X-Ingress-Path headers; LAN clients connecting directly don't. We reject
# anything missing those headers.
#
# Set INGRESS_ONLY=0 for standalone docker-compose runs (no HA in front).
_INGRESS_ONLY = os.getenv("INGRESS_ONLY", "1") == "1"
_INGRESS_HEADER_MARKERS = ("x-ingress-path", "x-hass-user-id", "x-hassio-key")
_INGRESS_EXEMPT_PATHS = {"/api/health"}


class IngressOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if _INGRESS_ONLY and request.url.path not in _INGRESS_EXEMPT_PATHS:
            if not any(h in request.headers for h in _INGRESS_HEADER_MARKERS):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Direct access not allowed. Open the add-on through "
                                  "Home Assistant's sidebar (ingress)."
                    },
                )
        return await call_next(request)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(IngressOnlyMiddleware)


SECTION_MODELS = {
    "hardware": Hardware,
    "applications": Application,
    "integrations": Integration,
}

NETWORK_SECTION_MODELS = {
    "subnets": Subnet,
    "vlans": Vlan,
    "hosts": Host,
}


# ─── lifecycle ──────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """Seed an empty inventory on first run, then start the uptime poller."""
    inv = storage.load()
    if (
        not inv.hardware
        and not inv.applications
        and not inv.integrations
        and not inv.network.hosts
        and not inv.network.subnets
        and not inv.network.vlans
    ):
        storage.save(initial_inventory())
    uptime.start()
    discovery.start()


# ─── meta ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# ─── whole-document endpoints ───────────────────────────────────────────────

@app.get("/api/inventory")
def get_inventory() -> Inventory:
    return storage.load()


@app.put("/api/inventory")
def put_inventory(payload: Inventory) -> Inventory:
    storage.save(payload)
    return payload


@app.get("/api/inventory/raw", response_class=PlainTextResponse)
def get_raw() -> str:
    return storage.raw_yaml()


@app.put("/api/inventory/raw", response_class=PlainTextResponse)
async def put_raw(request: Request) -> str:
    text = (await request.body()).decode("utf-8")
    try:
        storage.write_raw_yaml(text)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return storage.raw_yaml()


# ─── Home Assistant proxy ──────────────────────────────────────────────────

@app.get("/api/ha/status")
def ha_status() -> Dict[str, Any]:
    # Diagnostic helpers — env var NAMES only (never values). Three views:
    #  1. supervisor_env_present: names matching the well-known prefixes
    #     (SUPERVISOR/HASSIO/HOMEASSISTANT). The common case.
    #  2. all_env_keys: every env var name in the container. Helps when (1)
    #     comes back empty so we can spot whatever Supervisor IS injecting
    #     under an unexpected name.
    #  3. addon_version + bind metadata so we can confirm the running build.
    supervisor_env_present = sorted(
        k for k in os.environ.keys()
        if k.startswith(("SUPERVISOR", "HASSIO", "HOMEASSISTANT"))
    )
    return {
        "configured": ha_client.is_configured(),
        "token_env_var": ha_client.token_env_var(),
        "rest_base": ha_client.HA_REST_BASE,
        "supervisor_env_present": supervisor_env_present,
        "all_env_keys": sorted(os.environ.keys()),
        "addon_version": app.version,
    }


@app.get("/api/ha/devices")
async def ha_devices() -> Dict[str, Any]:
    devices = await ha_client.list_devices()
    entities = await ha_client.list_entities_for_devices()
    by_device: Dict[str, list] = {}
    for e in entities:
        did = e.get("device_id")
        if did:
            by_device.setdefault(did, []).append(
                {"entity_id": e.get("entity_id"), "platform": e.get("platform")}
            )
    enriched = []
    for d in devices:
        did = d.get("id")
        enriched.append({
            "id": did,
            "name": d.get("name_by_user") or d.get("name"),
            "manufacturer": d.get("manufacturer"),
            "model": d.get("model"),
            "area_id": d.get("area_id"),
            "disabled_by": d.get("disabled_by"),
            "entities": by_device.get(did, []),
        })
    return {"count": len(enriched), "devices": enriched}


@app.get("/api/ha/entities")
async def ha_entities() -> Dict[str, Any]:
    states = await ha_client.list_states()
    slim = [
        {
            "entity_id": s.get("entity_id"),
            "state": s.get("state"),
            "friendly_name": (s.get("attributes") or {}).get("friendly_name"),
            "device_class": (s.get("attributes") or {}).get("device_class"),
        }
        for s in states
    ]
    return {"count": len(slim), "entities": slim}


# ─── Uptime ────────────────────────────────────────────────────────────────

@app.get("/api/uptime")
def uptime_snapshot() -> Dict[str, Any]:
    return uptime.snapshot()


# ─── Discovery ─────────────────────────────────────────────────────────────

@app.get("/api/discovery")
def discovery_snapshot() -> Dict[str, Any]:
    return discovery.snapshot()


@app.post("/api/discovery/scan")
async def discovery_scan() -> Dict[str, Any]:
    await discovery.scan()
    return discovery.snapshot()


@app.post("/api/discovery/import")
def discovery_import(payload: Dict[str, Any]) -> Dict[str, Any]:
    key = payload.get("key")
    if not key:
        raise HTTPException(status_code=400, detail="missing 'key'")
    try:
        return discovery.import_candidate(key, payload.get("overrides"))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/discovery/dismiss")
def discovery_dismiss(payload: Dict[str, Any]) -> Dict[str, Any]:
    key = payload.get("key")
    if not key:
        raise HTTPException(status_code=400, detail="missing 'key'")
    return discovery.dismiss(key)


@app.post("/api/discovery/undismiss")
def discovery_undismiss(payload: Dict[str, Any]) -> Dict[str, Any]:
    key = payload.get("key")
    if not key:
        raise HTTPException(status_code=400, detail="missing 'key'")
    return discovery.undismiss(key)


# ─── flat sections: hardware, applications, integrations ───────────────────

def _flat_list(inv: Inventory, section: str) -> list:
    return getattr(inv, section)


@app.get("/api/{section}")
def list_section(section: str) -> list:
    if section not in SECTION_MODELS:
        raise HTTPException(status_code=404, detail="unknown section")
    return [m.model_dump(mode="json") for m in _flat_list(storage.load(), section)]


@app.post("/api/{section}")
def create_section_item(section: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if section not in SECTION_MODELS:
        raise HTTPException(status_code=404, detail="unknown section")
    Model = SECTION_MODELS[section]
    try:
        item = Model.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors())

    inv = storage.load()
    items = _flat_list(inv, section)
    if any(getattr(x, "id") == item.id for x in items):
        raise HTTPException(status_code=409, detail=f"id already exists: {item.id}")
    items.append(item)
    storage.save(inv)
    return item.model_dump(mode="json")


@app.put("/api/{section}/{item_id}")
def update_section_item(
    section: str, item_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    if section not in SECTION_MODELS:
        raise HTTPException(status_code=404, detail="unknown section")
    Model = SECTION_MODELS[section]
    inv = storage.load()
    items = _flat_list(inv, section)
    for idx, x in enumerate(items):
        if getattr(x, "id") == item_id:
            merged = {**x.model_dump(mode="json"), **payload, "id": payload.get("id", item_id)}
            try:
                new_item = Model.model_validate(merged)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=e.errors())
            items[idx] = new_item
            storage.save(inv)
            return new_item.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"id not found: {item_id}")


@app.delete("/api/{section}/{item_id}")
def delete_section_item(section: str, item_id: str) -> Dict[str, str]:
    if section not in SECTION_MODELS:
        raise HTTPException(status_code=404, detail="unknown section")
    inv = storage.load()
    items = _flat_list(inv, section)
    new_items = [x for x in items if getattr(x, "id") != item_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail=f"id not found: {item_id}")
    setattr(inv, section, new_items)
    storage.save(inv)
    return {"deleted": item_id}


# ─── nested network sections: subnets, vlans, hosts ────────────────────────

@app.get("/api/network/{section}")
def list_network(section: str) -> list:
    if section not in NETWORK_SECTION_MODELS:
        raise HTTPException(status_code=404, detail="unknown network section")
    return [m.model_dump(mode="json") for m in getattr(storage.load().network, section)]


@app.post("/api/network/{section}")
def create_network_item(section: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if section not in NETWORK_SECTION_MODELS:
        raise HTTPException(status_code=404, detail="unknown network section")
    Model = NETWORK_SECTION_MODELS[section]
    try:
        item = Model.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.errors())

    inv = storage.load()
    items = getattr(inv.network, section)
    if any(getattr(x, "id") == item.id for x in items):
        raise HTTPException(status_code=409, detail=f"id already exists: {item.id}")
    items.append(item)
    storage.save(inv)
    return item.model_dump(mode="json")


@app.put("/api/network/{section}/{item_id}")
def update_network_item(
    section: str, item_id: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    if section not in NETWORK_SECTION_MODELS:
        raise HTTPException(status_code=404, detail="unknown network section")
    Model = NETWORK_SECTION_MODELS[section]
    inv = storage.load()
    items = getattr(inv.network, section)
    for idx, x in enumerate(items):
        if getattr(x, "id") == item_id:
            merged = {**x.model_dump(mode="json"), **payload, "id": payload.get("id", item_id)}
            try:
                new_item = Model.model_validate(merged)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=e.errors())
            items[idx] = new_item
            storage.save(inv)
            return new_item.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"id not found: {item_id}")


@app.delete("/api/network/{section}/{item_id}")
def delete_network_item(section: str, item_id: str) -> Dict[str, str]:
    if section not in NETWORK_SECTION_MODELS:
        raise HTTPException(status_code=404, detail="unknown network section")
    inv = storage.load()
    items = getattr(inv.network, section)
    new_items = [x for x in items if getattr(x, "id") != item_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail=f"id not found: {item_id}")
    setattr(inv.network, section, new_items)
    storage.save(inv)
    return {"deleted": item_id}


# ─── frontend ──────────────────────────────────────────────────────────────

STATIC_DIR = (Path(__file__).parent / "static").resolve()


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path:
        # Resolve and confirm the path stays under STATIC_DIR — protects against
        # traversal like `GET /../../etc/passwd`. Path.resolve() collapses `..`
        # before we check containment; is_relative_to is the actual gate.
        try:
            target = (STATIC_DIR / full_path).resolve()
        except (OSError, RuntimeError):
            target = None
        if target and target.is_file() and target.is_relative_to(STATIC_DIR):
            return FileResponse(target)
    return FileResponse(STATIC_DIR / "index.html")
