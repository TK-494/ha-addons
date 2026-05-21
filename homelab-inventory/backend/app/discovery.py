"""Auto-discovery of hardware and network hosts.

Sources
-------
1. **Home Assistant device registry** — every HA device becomes a hardware
   candidate. Manufacturer / model / area come along for the ride.
2. **HA entity attributes** — entities with `ip_address` and/or `mac_address`
   attributes become network-host candidates (DHCP discovery, device_tracker,
   router integrations all surface these).
3. **LAN ARP sweep** — `arp-scan --localnet` enumerates anything that answers
   ARP on the local subnet. Falls back to the kernel ARP cache (`ip neigh`)
   when arp-scan isn't installed or lacks NET_RAW.

Candidates land in `/data/discovery.json` as proposals (NOT written to the
inventory). The user clicks Import in the UI to promote one to a real
hardware / network.host entry, or Dismiss to suppress it in future scans.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from . import ha_client, storage
from .schemas import Application, Hardware, Host, Sensor


DISCOVERY_PATH = Path(os.getenv("DISCOVERY_PATH", "/data/discovery.json"))
SCAN_INTERVAL_SECONDS = int(os.getenv("DISCOVERY_SCAN_SECONDS", "600"))  # 10 min

_lock = RLock()
_task: Optional[asyncio.Task] = None
_scan_in_progress = False


# ─── persistence ────────────────────────────────────────────────────────────

def _empty_state() -> Dict[str, Any]:
    return {"last_scan_at": 0, "candidates": {}, "dismissed": []}


def _load() -> Dict[str, Any]:
    with _lock:
        if not DISCOVERY_PATH.exists():
            return _empty_state()
        try:
            data = json.loads(DISCOVERY_PATH.read_text(encoding="utf-8"))
            data.setdefault("candidates", {})
            data.setdefault("dismissed", [])
            return data
        except Exception:
            return _empty_state()


def _save(data: Dict[str, Any]) -> None:
    with _lock:
        DISCOVERY_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".discovery-", suffix=".json.tmp", dir=DISCOVERY_PATH.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, DISCOVERY_PATH)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


# ─── helpers ────────────────────────────────────────────────────────────────

def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "item"


def _known_inventory_keys() -> Dict[str, set]:
    """Return the set of HA device_ids / entity_ids / IPs already in inventory.

    Used by classifiers to skip anything we've already imported (or that the
    user imported manually and linked).
    """
    inv = storage.load()
    return {
        "hw_device_ids":     {h.ha_device_id for h in inv.hardware if h.ha_device_id},
        "app_entity_ids":    {a.ha_entity_id for a in inv.applications if a.ha_entity_id},
        "sensor_device_ids": {s.ha_device_id for s in inv.sensors if s.ha_device_id},
        "sensor_entity_ids": {s.ha_entity_id for s in inv.sensors if s.ha_entity_id},
        "host_ips":          {h.ip for h in inv.network.hosts if h.ip},
    }


# ─── source: HA device registry, properly classified ──────────────────────

# device_class → SensorKind. We pass HA's device_class through unchanged
# where our SensorKind literal covers it; everything else falls to "other".
_KNOWN_SENSOR_KINDS = {
    "motion", "occupancy", "presence",
    "door", "window", "opening", "garage_door",
    "temperature", "humidity", "pressure", "illuminance",
    "moisture", "water", "leak",
    "smoke", "gas", "co", "co2",
    "vibration", "tamper", "sound",
    "battery", "power", "energy",
}

# Manufacturer/model substring → HardwareType. Lower-case match.
_HW_TYPE_HINTS: List[Tuple[str, str]] = [
    # Network
    ("ubiquiti", "network"), ("unifi", "network"), ("mikrotik", "network"),
    ("tp-link", "network"), ("netgear", "network"), ("fritz", "network"),
    ("router", "network"), ("switch", "network"), ("access point", "network"),
    # AV
    ("philips tv", "av"), ("philips android tv", "av"),
    ("samsung tv", "av"), ("sony tv", "av"),
    ("apple tv", "av"), ("homepod", "av"),
    ("harman", "av"), ("sonos", "av"), ("denon", "av"), ("yamaha", "av"),
    ("speaker", "av"), ("receiver", "av"),
    # Hub
    ("zigbee", "hub"), ("z-wave", "hub"), ("hue bridge", "hub"),
    ("conbee", "hub"), ("deconz", "hub"),
    # Compute / NAS
    ("synology", "nas"), ("qnap", "nas"),
    ("raspberry pi", "compute"), ("nuc", "compute"), ("home assistant", "server"),
]


def _hw_type_from_hints(vendor: Optional[str], model: Optional[str]) -> str:
    """Best-effort HardwareType from vendor+model strings."""
    blob = f"{(vendor or '').lower()} {(model or '').lower()}".strip()
    if not blob:
        return "other"
    for needle, t in _HW_TYPE_HINTS:
        if needle in blob:
            return t
    return "iot"  # has a real vendor/model but no specific hint → assume IoT


def _device_entities_index(entities: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group entity registry entries by device_id."""
    idx: Dict[str, List[Dict[str, Any]]] = {}
    for e in entities or []:
        did = e.get("device_id")
        if not did:
            continue
        idx.setdefault(did, []).append(e)
    return idx


def _sensor_kind_for_entities(entities: List[Dict[str, Any]]) -> Optional[str]:
    """Pick the most representative sensor kind across a device's entities.

    Strategy: pull device_class values for binary_sensor/sensor entities. If
    any maps to a known SensorKind, prefer "physical-event" kinds (motion/door)
    over scalar ones (battery/illuminance) since those are what users actually
    inventory.
    """
    classes: List[str] = []
    for e in entities:
        eid = (e.get("entity_id") or "")
        dc = (e.get("original_device_class") or e.get("device_class") or "").lower()
        if not dc:
            # Fall back to entity_id name heuristics for older HA versions.
            for needle in ("motion", "door", "window", "leak", "smoke", "presence",
                           "occupancy", "temperature", "humidity"):
                if needle in eid:
                    dc = needle
                    break
        if dc in _KNOWN_SENSOR_KINDS:
            classes.append(dc)
    if not classes:
        return None
    # Priority — physical events first.
    for preferred in ("motion", "occupancy", "presence",
                      "door", "window", "opening", "garage_door",
                      "smoke", "gas", "co", "co2",
                      "leak", "moisture", "water",
                      "vibration", "tamper",
                      "temperature", "humidity", "illuminance", "pressure",
                      "energy", "power", "battery"):
        if preferred in classes:
            return preferred
    return classes[0]


def _primary_sensor_entity(entities: List[Dict[str, Any]], kind: str) -> Optional[str]:
    """Pick the entity_id that best represents the sensor's primary reading."""
    # Prefer entities whose device_class matches the chosen kind exactly.
    for e in entities:
        dc = (e.get("original_device_class") or e.get("device_class") or "").lower()
        if dc == kind:
            return e.get("entity_id")
    # Otherwise the first binary_sensor/sensor entity.
    for prefix in ("binary_sensor.", "sensor."):
        for e in entities:
            eid = e.get("entity_id") or ""
            if eid.startswith(prefix):
                return eid
    return (entities[0].get("entity_id") if entities else None)


def _classify_device(
    d: Dict[str, Any],
    entities: List[Dict[str, Any]],
) -> Tuple[str, Optional[str]]:
    """Return (candidate_kind, subtype_hint).

    candidate_kind: "skip" | "hardware" | "sensor" | "application"
    subtype_hint:   HardwareType / SensorKind / AppType depending on kind.
    """
    # 1. HA service-only entries — these are virtual (Sun, Backup, Cloud, ...).
    if (d.get("entry_type") or "").lower() == "service":
        return ("skip", None)

    vendor = d.get("manufacturer") or ""
    model = d.get("model") or ""
    # 2. HA add-ons / Supervisor entries: integration name in identifiers.
    # HA stores identifiers as a list of [domain, unique_id] pairs.
    identifiers = d.get("identifiers") or []
    flat_ids = ",".join(
        ":".join(str(x) for x in p)
        for p in identifiers
        if isinstance(p, (list, tuple)) and len(p) >= 2
    ).lower()
    if "hassio" in flat_ids or "supervisor" in flat_ids:
        return ("application", "ha_addon")

    # 3. If the device exposes mostly classified sensor entities → Sensor.
    kind = _sensor_kind_for_entities(entities)
    if kind:
        return ("sensor", kind)

    # 4. Device with a real vendor / model → Hardware, with a best-effort type.
    if vendor or model:
        return ("hardware", _hw_type_from_hints(vendor, model))

    # 5. No vendor, no sensor entities, not a service — best guess: skip.
    # These are usually integration shells (e.g. "Cast", "Apple TV"). Suppress
    # by default rather than create noise; if the user wants them they can
    # add manually.
    return ("skip", None)


async def _ha_device_candidates() -> List[Dict[str, Any]]:
    devices = await ha_client.list_devices()
    if not devices:
        return []
    try:
        entities = await ha_client.list_entities_for_devices()
    except Exception:
        entities = []
    ent_idx = _device_entities_index(entities)
    known = _known_inventory_keys()

    out: List[Dict[str, Any]] = []
    for d in devices:
        did = d.get("id")
        if not did:
            continue
        if did in known["hw_device_ids"] or did in known["sensor_device_ids"]:
            continue
        kind, subtype = _classify_device(d, ent_idx.get(did, []))
        if kind == "skip":
            continue
        name = d.get("name_by_user") or d.get("name") or did
        vendor = d.get("manufacturer") or None
        model = d.get("model") or None
        area = d.get("area_id") or None
        common = {
            "id": _slug(f"ha-{name}-{did[:6]}"),
            "name": name,
            "vendor": vendor,
            "model": model,
            "ha_device_id": did,
            "notes": f"Discovered from HA device registry. Area: {area or 'n/a'}.",
            "tags": ["discovered", "ha"],
        }

        if kind == "hardware":
            proposal = Hardware(type=subtype or "other", **common).model_dump(mode="json")
            out.append({
                "key": f"hw:ha:{did}",
                "kind": "hardware",
                "source": "ha-device",
                "label": name,
                "subtitle": " • ".join(x for x in [subtype, vendor, model] if x) or "—",
                "proposal": proposal,
            })
        elif kind == "sensor":
            ent = ent_idx.get(did, [])
            primary = _primary_sensor_entity(ent, subtype or "other")
            proposal = Sensor(
                kind=subtype or "other",
                location=area,
                ha_entity_id=primary,
                **common,
            ).model_dump(mode="json")
            out.append({
                "key": f"sensor:ha:{did}",
                "kind": "sensor",
                "source": "ha-device",
                "label": name,
                "subtitle": " • ".join(x for x in [subtype, vendor, model, primary] if x) or "—",
                "proposal": proposal,
            })
        elif kind == "application":
            if did in known["app_entity_ids"]:
                continue
            proposal = Application(
                id=common["id"],
                name=name,
                type=subtype or "ha_addon",
                notes=common["notes"],
                tags=["discovered", "ha"],
            ).model_dump(mode="json")
            out.append({
                "key": f"app:ha:{did}",
                "kind": "application",
                "source": "ha-device",
                "label": name,
                "subtitle": " • ".join(x for x in ["ha_addon", vendor, model] if x) or "ha_addon",
                "proposal": proposal,
            })
    return out


# ─── source: HA entity attributes with IP/MAC ───────────────────────────────

async def _ha_host_candidates() -> List[Dict[str, Any]]:
    states = await ha_client.list_states()
    if not states:
        return []
    host_ips = _known_inventory_keys()["host_ips"]
    out: List[Dict[str, Any]] = []
    seen_ips: set = set()
    for s in states:
        attrs = s.get("attributes") or {}
        ip = attrs.get("ip") or attrs.get("ip_address")
        mac = attrs.get("mac") or attrs.get("mac_address") or attrs.get("source")
        host = attrs.get("host_name") or attrs.get("hostname") or attrs.get("friendly_name")
        if not ip or ip in host_ips or ip in seen_ips:
            continue
        seen_ips.add(ip)
        entity_id = s.get("entity_id") or ""
        proposal = Host(
            id=_slug(f"ha-{host or entity_id}-{ip}"),
            hostname=host or entity_id,
            ip=ip,
            purpose=f"Discovered from HA entity {entity_id}",
        ).model_dump(mode="json")
        out.append({
            "key": f"host:ha:{ip}",
            "kind": "host",
            "source": "ha-entity",
            "label": host or entity_id,
            "subtitle": f"{ip}" + (f" • {mac}" if mac else ""),
            "proposal": proposal,
        })
    return out


# ─── source: LAN ARP sweep ──────────────────────────────────────────────────

_ARP_SCAN_RE = re.compile(r"^(?P<ip>\d+\.\d+\.\d+\.\d+)\s+(?P<mac>[0-9a-fA-F:]{17})\s*(?P<vendor>.*)$")
_IP_NEIGH_RE = re.compile(r"^(?P<ip>\d+\.\d+\.\d+\.\d+)\s+\S+\s+\S+\s+lladdr\s+(?P<mac>[0-9a-fA-F:]{17})")


def _run(cmd: List[str], timeout: float = 20.0) -> Tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""
    except Exception as e:
        return 1, str(e)


def _arp_scan_pairs() -> List[Tuple[str, str, str]]:
    """Return list of (ip, mac, vendor). Tries arp-scan first, falls back to ip neigh."""
    pairs: List[Tuple[str, str, str]] = []
    if shutil.which("arp-scan"):
        rc, out = _run(["arp-scan", "--localnet", "--retry=2", "--ignoredups"], timeout=30.0)
        if rc == 0 and out:
            for line in out.splitlines():
                m = _ARP_SCAN_RE.match(line.strip())
                if m:
                    pairs.append((m.group("ip"), m.group("mac").lower(), m.group("vendor").strip()))
            if pairs:
                return pairs
    # Fallback: kernel ARP cache.
    if shutil.which("ip"):
        rc, out = _run(["ip", "neigh", "show"], timeout=5.0)
        if rc == 0 and out:
            for line in out.splitlines():
                m = _IP_NEIGH_RE.match(line.strip())
                if m:
                    pairs.append((m.group("ip"), m.group("mac").lower(), ""))
    return pairs


def _arp_candidates() -> List[Dict[str, Any]]:
    host_ips = _known_inventory_keys()["host_ips"]
    pairs = _arp_scan_pairs()
    out: List[Dict[str, Any]] = []
    for ip, mac, vendor in pairs:
        if ip in host_ips:
            continue
        proposal = Host(
            id=_slug(f"lan-{ip}"),
            hostname=ip,
            ip=ip,
            purpose=f"Discovered via ARP{(' (' + vendor + ')') if vendor else ''}",
            notes=f"MAC {mac}" + (f" — {vendor}" if vendor else ""),
        ).model_dump(mode="json")
        out.append({
            "key": f"host:arp:{mac}",
            "kind": "host",
            "source": "arp",
            "label": ip,
            "subtitle": f"{mac}" + (f" • {vendor}" if vendor else ""),
            "proposal": proposal,
        })
    return out


# ─── scan orchestration ─────────────────────────────────────────────────────

async def scan() -> Dict[str, Any]:
    global _scan_in_progress
    if _scan_in_progress:
        return _load()
    _scan_in_progress = True
    try:
        # ARP scan blocks; run in a thread so the event loop stays responsive.
        ha_devs, ha_hosts, arp = await asyncio.gather(
            _ha_device_candidates(),
            _ha_host_candidates(),
            asyncio.to_thread(_arp_candidates),
        )
        all_found = ha_devs + ha_hosts + arp

        data = _load()
        dismissed = set(data.get("dismissed", []))
        now = time.time()
        new_candidates: Dict[str, Any] = {}
        for c in all_found:
            key = c["key"]
            if key in dismissed:
                continue
            prev = data["candidates"].get(key, {})
            new_candidates[key] = {
                **c,
                "first_seen": prev.get("first_seen", now),
                "last_seen": now,
            }
        data["candidates"] = new_candidates
        data["last_scan_at"] = now
        _save(data)
        return data
    finally:
        _scan_in_progress = False


async def _loop() -> None:
    while True:
        try:
            await scan()
        except Exception:
            pass
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


def start() -> None:
    global _task
    if _task is None or _task.done():
        loop = asyncio.get_event_loop()
        _task = loop.create_task(_loop())


# ─── read / mutate API ──────────────────────────────────────────────────────

def snapshot() -> Dict[str, Any]:
    data = _load()
    return {
        "last_scan_at": data.get("last_scan_at", 0),
        "scan_in_progress": _scan_in_progress,
        "dismissed_count": len(data.get("dismissed", [])),
        "candidates": list(data.get("candidates", {}).values()),
    }


def dismiss(key: str) -> Dict[str, Any]:
    data = _load()
    if key in data["candidates"]:
        del data["candidates"][key]
    if key not in data["dismissed"]:
        data["dismissed"].append(key)
    _save(data)
    return snapshot()


def undismiss(key: str) -> Dict[str, Any]:
    data = _load()
    data["dismissed"] = [k for k in data.get("dismissed", []) if k != key]
    _save(data)
    return snapshot()


def import_candidate(key: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Promote a candidate into the real inventory. Returns the saved item."""
    data = _load()
    cand = data["candidates"].get(key)
    if not cand:
        raise KeyError(f"unknown candidate: {key}")

    proposal = {**(cand.get("proposal") or {}), **(overrides or {})}
    inv = storage.load()
    if cand["kind"] == "hardware":
        item = Hardware.model_validate(proposal)
        existing_ids = {h.id for h in inv.hardware}
        item = _ensure_unique_id(item, existing_ids)
        inv.hardware.append(item)
        saved = item.model_dump(mode="json")
    elif cand["kind"] == "sensor":
        item = Sensor.model_validate(proposal)
        existing_ids = {s.id for s in inv.sensors}
        item = _ensure_unique_id(item, existing_ids)
        inv.sensors.append(item)
        saved = item.model_dump(mode="json")
    elif cand["kind"] == "application":
        item = Application.model_validate(proposal)
        existing_ids = {a.id for a in inv.applications}
        item = _ensure_unique_id(item, existing_ids)
        inv.applications.append(item)
        saved = item.model_dump(mode="json")
    elif cand["kind"] == "host":
        item = Host.model_validate(proposal)
        existing_ids = {h.id for h in inv.network.hosts}
        item = _ensure_unique_id(item, existing_ids)
        inv.network.hosts.append(item)
        saved = item.model_dump(mode="json")
    else:
        raise ValueError(f"unsupported kind: {cand['kind']}")

    storage.save(inv)
    # Drop the candidate; don't dismiss so it can resurface if it ever drifts back.
    del data["candidates"][key]
    _save(data)
    return {"imported": saved, "kind": cand["kind"]}


def _ensure_unique_id(item, existing_ids: set):
    if item.id not in existing_ids:
        return item
    n = 2
    while f"{item.id}-{n}" in existing_ids:
        n += 1
    item.id = f"{item.id}-{n}"
    return item
