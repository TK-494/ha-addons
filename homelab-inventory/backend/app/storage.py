"""YAML-backed storage for the inventory document."""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from threading import RLock

import yaml

from .schemas import Inventory

INVENTORY_PATH = Path(os.getenv("INVENTORY_PATH", "/data/infrastructure.yaml"))
BACKUP_DIR = INVENTORY_PATH.parent / "backups"

_lock = RLock()


def _ensure_parent() -> None:
    INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def load() -> Inventory:
    """Load the inventory, creating an empty one if it doesn't exist yet."""
    with _lock:
        _ensure_parent()
        if not INVENTORY_PATH.exists():
            inv = Inventory()
            save(inv)
            return inv
        with INVENTORY_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return Inventory.model_validate(data)


def save(inv: Inventory) -> None:
    """Atomically write the inventory to YAML, keeping a rolling backup."""
    with _lock:
        _ensure_parent()
        # Rolling backup of the previous file (keep last 10).
        if INVENTORY_PATH.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_target = BACKUP_DIR / f"infrastructure-{stamp}.yaml"
            try:
                shutil.copy2(INVENTORY_PATH, backup_target)
            except OSError:
                pass
            _prune_backups()

        # Atomic write: temp file in same dir, then rename.
        data = inv.model_dump(mode="json")
        fd, tmp_path = tempfile.mkstemp(
            prefix=".infrastructure-",
            suffix=".yaml.tmp",
            dir=INVENTORY_PATH.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    data,
                    f,
                    sort_keys=False,
                    default_flow_style=False,
                    allow_unicode=True,
                )
            os.replace(tmp_path, INVENTORY_PATH)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def _prune_backups(keep: int = 10) -> None:
    backups = sorted(BACKUP_DIR.glob("infrastructure-*.yaml"))
    for old in backups[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass


def raw_yaml() -> str:
    """Return the on-disk YAML text (for the raw editor view)."""
    with _lock:
        if not INVENTORY_PATH.exists():
            return ""
        return INVENTORY_PATH.read_text(encoding="utf-8")


def write_raw_yaml(text: str) -> Inventory:
    """Validate user-supplied YAML text and write it. Returns the parsed inventory."""
    data = yaml.safe_load(text) or {}
    inv = Inventory.model_validate(data)  # raises if invalid
    save(inv)
    return inv
