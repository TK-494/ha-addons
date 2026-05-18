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
from .schemas import Hardware, Host


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


def _known_inventory_keys() -> Tuple[set, set, set]:
    """Return (hardware_ha_device_ids, host_ips, host_macs) already in inventory."""
    inv = storage.load()
    hw_ids = {h.ha_device_id for h in inv.hardware if h.ha_device_id}
    host_ips: set = set()
    host_macs: set = set()
    for h in inv.network.hosts:
        if h.ip:
            host_ips.add(h.ip)
    return hw_ids, host_ips, host_macs


# ─── source: HA device registry ─────────────────────────────────────────────

async def _ha_device_candidates() -> List[Dict[str, Any]]:
    devices = await ha_client.list_devices()
    if not devices:
        return []
    hw_ids, _, _ = _known_inventory_keys()
    out: List[Dict[str, Any]] = []
    for d in devices:
        did = d.get("id")
        if not did or did in hw_ids:
            continue
        name = d.get("name_by_user") or d.get("name") or did
        proposal = Hardware(
            id=_slug(f"ha-{name}-{did[:6]}"),
            name=name,
            type="other",
            vendor=d.get("manufacturer") or None,
            model=d.get("model") or None,
            ha_device_id=did,
            notes=f"Discovered from HA device registry. Area: {d.get('area_id') or 'n/a'}.",
            tags=["discovered", "ha"],
        ).model_dump(mode="json")
        out.append({
            "key": f"hw:ha:{did}",
            "kind": "hardware",
            "source": "ha-device",
            "label": name,
            "subtitle": " • ".join([x for x in [d.get("manufacturer"), d.get("model")] if x]) or "—",
            "proposal": proposal,
        })
    return out


# ─── source: HA entity attributes with IP/MAC ───────────────────────────────

async def _ha_host_candidates() -> List[Dict[str, Any]]:
    states = await ha_client.list_states()
    if not states:
        return []
    _, host_ips, host_macs = _known_inventory_keys()
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
    _, host_ips, _ = _known_inventory_keys()
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
        # If id collides, append a short suffix.
        existing_ids = {h.id for h in inv.hardware}
        item = _ensure_unique_id(item, existing_ids)
        inv.hardware.append(item)
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
