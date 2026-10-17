"""Clients for the *arr apps and the matching logic that picks a lookup result.

Stdlib only: the add-on does a handful of JSON requests a minute, which does not
justify a dependency tree that then needs auditing.
"""
from __future__ import annotations

import glob
import json
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from difflib import SequenceMatcher

TIMEOUT = 30
USER_AGENT = "media-requests-ha-addon/0.1 (https://github.com/TK-494/ha-addons)"


class TransientError(Exception):
    """Service unreachable or 5xx: retry later, don't touch the item."""


class RequestError(Exception):
    """The request itself is wrong (4xx, nothing found, config missing)."""


def http_json(method: str, url: str, headers: dict | None = None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, list):
                detail = "; ".join(str(x.get("errorMessage", x)) for x in parsed if isinstance(x, dict))
            elif isinstance(parsed, dict):
                detail = str(parsed.get("message") or parsed.get("errorMessage") or parsed)
        except ValueError:
            pass
        detail = detail[:300]
        if e.code >= 500:
            raise TransientError(f"HTTP {e.code} from {redact(url)}: {detail}") from e
        raise RequestError(f"HTTP {e.code} from {redact(url)}: {detail}") from e
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise TransientError(f"{redact(url)} unreachable: {e}") from e


def redact(url: str) -> str:
    return re.sub(r"(apikey=)[^&]+", r"\1***", url, flags=re.I)


# ---------------------------------------------------------------- matching ---

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return " ".join(w for w in s.split() if w not in {"the", "a", "an", "de", "het", "een"})


def score(query: str, candidate: str) -> float:
    """0..1. Half string similarity, half how many query words the candidate covers.

    Coverage matters because people type "matrix 1999" or "teardrop massive attack":
    the order and the missing articles shouldn't sink an obvious match.
    """
    q, c = norm(query), norm(candidate)
    if not q or not c:
        return 0.0
    ratio = SequenceMatcher(None, q, c).ratio()
    qt, ct = q.split(), set(c.split())
    coverage = sum(1 for w in qt if w in ct) / len(qt)
    return round(0.5 * ratio + 0.5 * coverage, 3)


ACCEPT = 0.75   # minimum score to add without asking
MARGIN = 0.08   # top result must beat the runner-up by this much


def pick(query: str, candidates: list[dict], label, explicit: bool):
    """Return (chosen, ranked). chosen is None when it's not a clear win."""
    if not candidates:
        return None, []
    if explicit:  # tmdb:/tvdb:/lidarr:/isbn: lookups return the thing asked for
        return candidates[0], [(1.0, candidates[0])]
    # Best of full label and bare title: "Dune" shouldn't lose points for not
    # also naming the author, and "dune herbert" shouldn't for naming them.
    ranked = sorted(((max(score(query, label(c)), score(query, c.get("title", ""))), c)
                     for c in candidates),
                    key=lambda t: t[0], reverse=True)
    top_s, top = ranked[0]
    second_s = ranked[1][0] if len(ranked) > 1 else 0.0
    if top_s >= ACCEPT and top_s - second_s >= MARGIN:
        return top, ranked
    # Identical scores happen when a title and its remake both match; only
    # accept a tie-free exact title.
    exact = [c for s, c in ranked if norm(c.get("title", "")) == norm(query)]
    if len(exact) == 1 and top_s >= ACCEPT:
        return exact[0], ranked
    return None, ranked


EXPLICIT_RE = re.compile(r"^(tmdb|imdb|tvdb|lidarr|mbid|isbn|asin|edition|work|author):\S+$", re.I)


# ------------------------------------------------------------ arr services ---

DEFAULTS = {
    # name: (default base url, api version, config.xml folder hints)
    "lidarr": ("http://a0d7b954-lidarr:8686", "v1", ["a0d7b954_lidarr", "*lidarr*"]),
    "readarr": ("http://db21ed7f-readarr-nas:8787", "v1", ["db21ed7f_readarr_nas", "*readarr*"]),
    "radarr": ("http://a0d7b954-radarr:7878", "v3", ["a0d7b954_radarr", "*radarr*"]),
    "sonarr": ("http://a0d7b954-sonarr:8989", "v3", ["a0d7b954_sonarr", "*sonarr*"]),
}
CONFIG_ROOTS = ["/addon_configs", "/app_configs"]


def find_config_xml(hints: list[str], roots=CONFIG_ROOTS) -> str | None:
    for root in roots:
        for hint in hints:
            for d in sorted(glob.glob(os.path.join(root, hint))):
                for depth in ("", "*", "*/*"):
                    hits = sorted(glob.glob(os.path.join(d, depth, "config.xml")))
                    if hits:
                        return hits[0]
    return None


def read_config_xml(path: str) -> dict:
    root = ET.parse(path).getroot()
    return {child.tag: (child.text or "") for child in root}


class Arr:
    """One *arr instance. Profiles and folders are cached per instance lifetime."""

    def __init__(self, name: str, opts: dict, config_roots=CONFIG_ROOTS):
        self.name = name
        default_url, self.api, hints = DEFAULTS[name]
        url = (opts.get(f"{name}_url") or "").strip()
        key = (opts.get(f"{name}_api_key") or "").strip()
        self.source = "options"
        if not key or not url:
            path = find_config_xml(hints, config_roots)
            if path:
                cfg = read_config_xml(path)
                key = key or cfg.get("ApiKey", "")
                if not url:
                    base = cfg.get("UrlBase", "").strip("/")
                    url = default_url + (f"/{base}" if base else "")
                self.source = f"config.xml ({path})"
        self.url = (url or default_url).rstrip("/")
        self.key = key
        self.quality_name = (opts.get(f"{name}_quality_profile") or "").strip()
        self.metadata_name = (opts.get(f"{name}_metadata_profile") or "").strip()
        self.root_folder = (opts.get(f"{name}_root_folder") or "").strip()
        self._cache: dict = {}

    @property
    def title(self) -> str:
        return self.name.capitalize()

    def configured(self) -> bool:
        return bool(self.key)

    def call(self, method: str, path: str, body=None, **params):
        if not self.key:
            raise RequestError(
                f"{self.title}: geen API-key gevonden. Vul '{self.name}_api_key' in bij de add-on-opties.")
        qs = ("?" + urllib.parse.urlencode(params)) if params else ""
        return http_json(method, f"{self.url}/api/{self.api}/{path}{qs}",
                         {"X-Api-Key": self.key}, body)

    # --- defaults, never silent: every choice is reported back in `notes` ---

    def _choose(self, kind: str, items: list[dict], wanted: str, used_ids: list[int],
                key="name") -> tuple[dict, str]:
        if not items:
            raise RequestError(f"{self.title} heeft geen {kind}.")
        if wanted:
            for it in items:
                if str(it.get(key, "")).lower() == wanted.lower():
                    return it, ""
            names = ", ".join(str(i.get(key)) for i in items)
            raise RequestError(f"{self.title}: {kind} '{wanted}' bestaat niet. Beschikbaar: {names}.")
        if len(items) == 1:
            return items[0], ""
        counts = Counter(used_ids)
        if counts:
            top_id = counts.most_common(1)[0][0]
            for it in items:
                if it.get("id") == top_id:
                    return it, f"{kind} '{it.get(key)}' (meest gebruikt in je bibliotheek)"
        names = ", ".join(str(i.get(key)) for i in items)
        raise RequestError(
            f"{self.title}: meerdere {kind} en geen keuze ingesteld. Kies er één in de add-on-opties: {names}.")

    def library(self, path: str) -> list[dict]:
        if path not in self._cache:
            self._cache[path] = self.call("GET", path) or []
        return self._cache[path]

    def profiles(self, owner_path: str, need_metadata: bool):
        """Returns (qualityProfileId, metadataProfileId|None, rootFolderPath, notes)."""
        notes = []
        owners = self.library(owner_path)
        q, n = self._choose("quality profile", self.call("GET", "qualityprofile"), self.quality_name,
                            [o.get("qualityProfileId") for o in owners])
        notes += [n] if n else []
        m_id = None
        if need_metadata:
            m, n = self._choose("metadata profile", self.call("GET", "metadataprofile"),
                                self.metadata_name, [o.get("metadataProfileId") for o in owners])
            m_id = m["id"]
            notes += [n] if n else []
        folders = self.call("GET", "rootfolder") or []
        if self.root_folder or len(folders) <= 1:
            rf, n = self._choose("root folder", folders, self.root_folder, [], key="path")
        else:
            rf, n = self._choose_folder(folders, owners)
        notes += [n] if n else []
        return q["id"], m_id, rf["path"], notes

    def _choose_folder(self, folders, owners):
        used = Counter()
        for o in owners:
            p = o.get("rootFolderPath") or o.get("path") or ""
            for f in folders:
                if p.startswith(f["path"].rstrip("/")):
                    used[f["path"]] += 1
        if used:
            path = used.most_common(1)[0][0]
            return next(f for f in folders if f["path"] == path), f"root folder '{path}' (meest gebruikt)"
        names = ", ".join(f["path"] for f in folders)
        raise RequestError(f"{self.title}: meerdere root folders, stel er één in: {names}.")


# ---------------------------------------------------------- MusicBrainz ---

MB = "https://musicbrainz.org/ws/2"


def musicbrainz_album_for_track(text: str) -> list[dict]:
    """Resolve a song to candidate studio albums: [{rgid, title, artist, year, score}].

    Lidarr only tracks albums, so a song request becomes "the album it's on".
    Studio albums (no secondary type) are preferred over compilations and live sets.
    """
    if " - " in text:
        a, b = [p.strip() for p in text.split(" - ", 1)]
        queries = [f'recording:"{a}" AND artist:"{b}"', f'recording:"{b}" AND artist:"{a}"']
    else:
        queries = [text]
    out: dict[str, dict] = {}
    for q in queries:
        url = f"{MB}/recording?" + urllib.parse.urlencode({"query": q, "fmt": "json", "limit": 15})
        data = http_json("GET", url) or {}
        for rec in data.get("recordings", []):
            if rec.get("score", 0) < 80:
                continue
            artist = " ".join(c.get("name", "") + c.get("joinphrase", "")
                              for c in rec.get("artist-credit", [])).strip()
            for rel in rec.get("releases", []):
                rg = rel.get("release-group") or {}
                if rg.get("primary-type") != "Album" or rg.get("secondary-types"):
                    continue
                if rel.get("status") not in (None, "Official"):
                    continue
                year = (rel.get("date") or "")[:4]
                cur = out.get(rg["id"])
                if cur is None or (year and (not cur["year"] or year < cur["year"])):
                    out[rg["id"]] = {"rgid": rg["id"], "title": rg.get("title", ""), "artist": artist,
                                     "year": year, "track": rec.get("title", ""), "score": rec["score"]}
        if out:
            break
    # Earliest release first: the original album, not the remaster.
    return sorted(out.values(), key=lambda r: (-r["score"], r["year"] or "9999"))
