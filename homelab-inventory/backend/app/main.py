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

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import storage
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


app = FastAPI(title="Homelab Inventory", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
def on_startup() -> None:
    """Seed an empty inventory on first run."""
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

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path:
        target = STATIC_DIR / full_path
        if target.is_file():
            return FileResponse(target)
    return FileResponse(STATIC_DIR / "index.html")
