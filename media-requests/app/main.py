"""Poll a Home Assistant to-do list and turn its items into *arr requests.

The list is the queue: anyone (Roel, Assist, Claude through the HA MCP server)
adds "film: The Matrix" and this loop does the rest. Results go into the item's
description; an item is only marked completed when something was actually added
or already present, so nothing disappears unseen.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import sys
import time

from arr import Arr, RequestError, TransientError, http_json
from handlers import Result, handle, parse

OPTIONS_PATH = os.environ.get("OPTIONS_PATH", "/data/options.json")
STATE_PATH = os.environ.get("STATE_PATH", "/data/state.json")
HA_URL = os.environ.get("HA_URL", "http://supervisor/core/api")

log = logging.getLogger("media-requests")


class HA:
    def __init__(self, token: str, base: str = HA_URL):
        self.base, self.h = base.rstrip("/"), {"Authorization": f"Bearer {token}"}

    def service(self, domain: str, svc: str, data: dict, response=False):
        url = f"{self.base}/services/{domain}/{svc}" + ("?return_response" if response else "")
        return http_json("POST", url, self.h, data)

    def open_items(self, entity: str) -> list[dict]:
        resp = self.service("todo", "get_items", {"entity_id": entity, "status": "needs_action"}, True) or {}
        return (resp.get("service_response") or {}).get(entity, {}).get("items", [])

    def update(self, entity: str, uid: str, description: str, done: bool):
        data = {"entity_id": entity, "item": uid, "description": description}
        if done:
            data["status"] = "completed"
        self.service("todo", "update_item", data)

    def notify(self, target: str, title: str, message: str):
        domain, _, svc = target.partition(".")
        if domain and svc:
            self.service(domain, svc, {"title": title, "message": message})


def fingerprint(item: dict) -> str:
    # Renaming an item is how the user answers a question, so the summary is the key.
    return hashlib.sha256((item.get("uid", "") + "\0" + item.get("summary", "")).encode()).hexdigest()[:16]


def load_json(path: str, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path: str, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


ICON = {"added": "✅", "exists": "☑️", "ambiguous": "❓", "failed": "⚠️", "waiting": "⏳"}


def render(r: Result) -> str:
    lines = [f"{ICON.get(r.status, '')} {r.message}"]
    lines += [f"- {c}" for c in r.choices]
    if r.notes:
        lines.append("Gekozen standaard: " + "; ".join(r.notes) + ".")
    lines.append(time.strftime("(%Y-%m-%d %H:%M)"))
    return "\n".join(lines)


def process(ha: HA, arrs: dict, opts: dict, state: dict) -> int:
    """One pass over the list. Returns how many items were written to."""
    entity = opts["todo_entity"]
    written = 0
    seen = set()
    for item in ha.open_items(entity):
        uid, summary = item.get("uid"), item.get("summary", "")
        fp = fingerprint(item)
        seen.add(uid)
        prev = state.get(uid, {})
        if prev.get("fp") == fp and prev.get("status") != "waiting":
            continue  # already answered; waiting for the user to rename it

        parsed = parse(summary)
        if parsed is None:
            r = Result("failed", "Geen soort herkend. Begin met muziek:, artiest:, boek:, auteur:, "
                                 "film: of serie: — bijv. 'film: The Matrix'.")
        else:
            service, kind, query, prefix = parsed
            try:
                r = handle(arrs, opts, service, kind, query, prefix)
            except TransientError as e:
                log.warning("%s: %s", summary, e)
                if prev.get("fp") != fp or prev.get("status") != "waiting":
                    ha.update(entity, uid, render(Result(
                        "waiting", f"{arrs[service].title} is nu niet bereikbaar; ik probeer het elke minuut opnieuw.")), False)
                    written += 1
                state[uid] = {"fp": fp, "status": "waiting"}
                continue
            except RequestError as e:
                r = Result("failed", str(e))
            except Exception as e:  # a bug must not stall the queue on one item
                log.exception("unexpected error on %r", summary)
                r = Result("failed", f"Interne fout ({type(e).__name__}: {e}). Zie de add-on-log.")

        done = r.status in ("added", "exists")
        ha.update(entity, uid, render(r), done)
        written += 1
        state[uid] = {"fp": fp, "status": r.status}
        log.info("%s -> %s: %s", summary, r.status, r.message)
        if done and r.status == "added" and opts.get("notify_service"):
            try:
                ha.notify(opts["notify_service"], "Media toegevoegd", r.message)
            except (TransientError, RequestError) as e:
                log.warning("notify failed: %s", e)
    for uid in list(state):  # forget items that were completed or deleted
        if uid not in seen:
            del state[uid]
    return written


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(message)s")
    opts = load_json(OPTIONS_PATH, {})
    opts.setdefault("todo_entity", "todo.media_verzoeken")
    interval = max(15, int(opts.get("poll_seconds") or 60))
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        log.error("SUPERVISOR_TOKEN missing: is homeassistant_api enabled in config.yaml?")
        sys.exit(1)
    ha = HA(token)
    arrs = {n: Arr(n, opts) for n in ("lidarr", "readarr", "radarr", "sonarr")}
    for a in arrs.values():
        log.info("%s: %s, key %s", a.title, a.url, f"from {a.source}" if a.key else "MISSING")
    log.info("watching %s every %ss", opts["todo_entity"], interval)

    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(1))
    state = load_json(STATE_PATH, {})
    while not stop:
        try:
            for a in arrs.values():
                a._cache.clear()  # library counts change; profiles are cheap to refetch
            before = json.dumps(state, sort_keys=True)
            process(ha, arrs, opts, state)
            if json.dumps(state, sort_keys=True) != before:
                save_json(STATE_PATH, state)
        except (TransientError, RequestError) as e:
            log.warning("todo list unavailable: %s", e)
        for _ in range(interval):
            if stop:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
