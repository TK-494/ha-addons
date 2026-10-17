"""One handler per media kind. Each returns a Result; none of them write to HA."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from arr import EXPLICIT_RE, Arr, RequestError, musicbrainz_album_for_track, pick


@dataclass
class Result:
    status: str              # added | exists | ambiguous | failed
    message: str
    choices: list[str] = field(default_factory=list)  # ready-to-paste item titles
    notes: list[str] = field(default_factory=list)


# prefix -> (service, kind)
PREFIXES = {
    "muziek": ("lidarr", "album"), "music": ("lidarr", "album"), "nummer": ("lidarr", "album"),
    "song": ("lidarr", "album"), "track": ("lidarr", "album"), "album": ("lidarr", "album"),
    "artiest": ("lidarr", "artist"), "artist": ("lidarr", "artist"), "band": ("lidarr", "artist"),
    "boek": ("readarr", "book"), "book": ("readarr", "book"),
    "auteur": ("readarr", "author"), "author": ("readarr", "author"), "schrijver": ("readarr", "author"),
    "film": ("radarr", "movie"), "movie": ("radarr", "movie"),
    "serie": ("sonarr", "series"), "series": ("sonarr", "series"), "tv": ("sonarr", "series"),
    "show": ("sonarr", "series"),
}
PREFIX_RE = re.compile(r"^\s*([A-Za-zë]+)\s*[:：]\s*(.+?)\s*$")


def parse(summary: str):
    """'film: The Matrix 1999' -> ('radarr', 'movie', 'The Matrix 1999', 'film'). None if no prefix."""
    m = PREFIX_RE.match(summary or "")
    if not m or m.group(1).lower() not in PREFIXES:
        return None
    service, kind = PREFIXES[m.group(1).lower()]
    query = m.group(2)
    # A pasted choice line keeps its "(label)" tail; only the ID before it counts.
    pasted = re.match(r"^(\w+:\S+)\s+\(.*\)$", query)
    if pasted and EXPLICIT_RE.match(pasted.group(1)):
        query = pasted.group(1)
    return service, kind, query, m.group(1).lower()


def _year(x: dict) -> str:
    y = x.get("year") or (x.get("releaseDate") or "")[:4]
    return str(y) if y else ""


def _ambiguous(prefix: str, ranked, label, ident, what: str) -> Result:
    if not ranked:
        return Result("failed", f"Niets gevonden voor deze {what}. Controleer de spelling of gebruik een ID.")
    choices = [f"{prefix}: {ident(c)}  ({label(c)})" for _, c in ranked[:4]]
    return Result("ambiguous", f"Meerdere mogelijke {what}s of geen duidelijke match. "
                               "Hernoem dit item naar één van de opties hieronder (alleen het deel vóór de haakjes is nodig).",
                  choices)


# ------------------------------------------------------------------ lidarr ---

def _album_label(a):
    artist = (a.get("artist") or {}).get("artistName", "")
    return f"{a.get('title', '')} — {artist} {_year(a)}".strip()


def lidarr_album(arr: Arr, query: str, prefix: str) -> Result:
    explicit = bool(EXPLICIT_RE.match(query))
    albums = arr.call("GET", "album/lookup", term=query) or []
    # A song title also matches its single ("Teardrop" the single), which isn't what a
    # song request means. Singles and EPs are only added by explicit ID.
    studio = [a for a in albums if str(a.get("albumType", "Album")).lower() == "album"]
    chosen, ranked = pick(query, albums if explicit else studio, _album_label, explicit)
    via_track = ""
    if chosen is None and not explicit:
        # Probably a song title: find the album it's on through MusicBrainz.
        for cand in musicbrainz_album_for_track(query)[:3]:
            hits = arr.call("GET", "album/lookup", term=f"lidarr:{cand['rgid']}") or []
            if hits:
                chosen = hits[0]
                via_track = f" (album met het nummer '{cand['track']}')"
                break
    if chosen is None:
        return _ambiguous(prefix, ranked, _album_label, lambda a: f"lidarr:{a.get('foreignAlbumId')}", "album")

    label = _album_label(chosen) + via_track
    existing = _lidarr_existing_album(arr, chosen.get("foreignAlbumId"))
    if existing:
        if existing.get("monitored"):
            return Result("exists", f"Staat al bewaakt in Lidarr: {label}.")
        arr.call("PUT", "album/monitor", {"albumIds": [existing["id"]], "monitored": True})
        arr.call("POST", "command", {"name": "AlbumSearch", "albumIds": [existing["id"]]})
        return Result("added", f"Lidarr had dit album al maar bewaakte het niet. Nu bewaakt en gezocht: {label}.")

    q_id, m_id, root, notes = arr.profiles("artist", need_metadata=True)
    artist = dict(chosen.get("artist") or {})
    artist.update({
        "qualityProfileId": q_id, "metadataProfileId": m_id, "rootFolderPath": root,
        "monitored": True, "monitorNewItems": "none",
        "addOptions": {"monitor": "none", "searchForMissingAlbums": False},
    })
    body = dict(chosen)
    body.update({"artist": artist, "monitored": True, "anyReleaseOk": True,
                 "addOptions": {"searchForNewAlbum": True}})
    arr.call("POST", "album", body)
    return Result("added", f"Toegevoegd aan Lidarr en zoekopdracht gestart: {label}.", notes=notes)


def _lidarr_existing_album(arr: Arr, foreign_id):
    if not foreign_id:
        return None
    hits = arr.call("GET", "album", foreignAlbumId=foreign_id) or []
    return hits[0] if hits else None


def lidarr_artist(arr: Arr, query: str, prefix: str, monitor: str) -> Result:
    explicit = bool(EXPLICIT_RE.match(query))
    found = arr.call("GET", "artist/lookup", term=query) or []
    label = lambda a: f"{a.get('artistName', '')} {a.get('disambiguation') or ''}".strip()
    chosen, ranked = pick(query, [dict(c, title=c.get("artistName", "")) for c in found], label, explicit)
    if chosen is None:
        return _ambiguous(prefix, ranked, label, lambda a: f"lidarr:{a.get('foreignArtistId')}", "artiest")
    if chosen.get("id"):
        return Result("exists", f"Staat al in Lidarr: {label(chosen)}.")
    q_id, m_id, root, notes = arr.profiles("artist", need_metadata=True)
    chosen.pop("title", None)
    chosen.update({"qualityProfileId": q_id, "metadataProfileId": m_id, "rootFolderPath": root,
                   "monitored": True, "monitorNewItems": "all",
                   "addOptions": {"monitor": monitor, "searchForMissingAlbums": True}})
    arr.call("POST", "artist", chosen)
    return Result("added", f"Artiest toegevoegd aan Lidarr (bewaken: {monitor}): {label(chosen)}.", notes=notes)


# ----------------------------------------------------------------- readarr ---

def _book_label(b):
    author = (b.get("author") or {}).get("authorName", "") or b.get("authorTitle", "")
    return f"{b.get('title', '')} — {author} {_year(b)}".strip()


def readarr_book(arr: Arr, query: str, prefix: str) -> Result:
    explicit = bool(EXPLICIT_RE.match(query))
    books = arr.call("GET", "book/lookup", term=query) or []
    chosen, ranked = pick(query, books, _book_label, explicit)
    if chosen is None:
        return _ambiguous(prefix, ranked, _book_label, lambda b: f"work:{b.get('foreignBookId')}", "boek")
    label = _book_label(chosen)
    if chosen.get("id"):
        if chosen.get("monitored"):
            return Result("exists", f"Staat al bewaakt in Readarr: {label}.")
        arr.call("PUT", "book/monitor", {"bookIds": [chosen["id"]], "monitored": True})
        arr.call("POST", "command", {"name": "BookSearch", "bookIds": [chosen["id"]]})
        return Result("added", f"Readarr had dit boek al maar bewaakte het niet. Nu bewaakt en gezocht: {label}.")

    q_id, m_id, root, notes = arr.profiles("author", need_metadata=True)
    author = _readarr_full_author(arr, chosen)
    author.update({
        "qualityProfileId": q_id, "metadataProfileId": m_id, "rootFolderPath": root,
        "monitored": True, "monitorNewItems": "none",
        "addOptions": {"monitor": "none", "searchForMissingBooks": False},
    })
    body = dict(chosen)
    editions = body.get("editions") or []
    if editions and not any(e.get("monitored") for e in editions):
        editions[0]["monitored"] = True  # Readarr needs one monitored edition to grab
    body.update({"author": author, "monitored": True, "editions": editions,
                 "addOptions": {"searchForNewBook": True}})
    arr.call("POST", "book", body)
    return Result("added", f"Toegevoegd aan Readarr en zoekopdracht gestart: {label}.", notes=notes)


def _readarr_full_author(arr: Arr, book: dict) -> dict:
    """book/lookup can return an author stub without foreignAuthorId; POST book rejects that."""
    author = dict(book.get("author") or {})
    if author.get("foreignAuthorId"):
        return author
    name = author.get("authorName") or ""
    if not name and book.get("authorTitle"):  # "weir, andy" -> "andy weir"
        last, _, first = book["authorTitle"].partition(",")
        name = f"{first.strip()} {last.strip()}".strip()
    if not name:
        raise RequestError("Readarr gaf geen auteur bij dit boek; voeg eerst de auteur toe met 'auteur: <naam>'.")
    found = arr.call("GET", "author/lookup", term=name) or []
    chosen, _ = pick(name, [dict(c, title=c.get("authorName", "")) for c in found],
                     lambda a: a.get("authorName", ""), False)
    if chosen is None:
        raise RequestError(f"Readarr: auteur '{name}' niet eenduidig gevonden; voeg eerst de auteur toe met "
                           f"'auteur: <naam>'.")
    chosen.pop("title", None)
    return chosen


def readarr_author(arr: Arr, query: str, prefix: str, monitor: str) -> Result:
    explicit = bool(EXPLICIT_RE.match(query))
    found = arr.call("GET", "author/lookup", term=query) or []
    label = lambda a: a.get("authorName", "")
    chosen, ranked = pick(query, [dict(c, title=c.get("authorName", "")) for c in found], label, explicit)
    if chosen is None:
        return _ambiguous(prefix, ranked, label, lambda a: f"author:{a.get('foreignAuthorId')}", "auteur")
    if chosen.get("id"):
        return Result("exists", f"Staat al in Readarr: {label(chosen)}.")
    q_id, m_id, root, notes = arr.profiles("author", need_metadata=True)
    chosen.pop("title", None)
    chosen.update({"qualityProfileId": q_id, "metadataProfileId": m_id, "rootFolderPath": root,
                   "monitored": True, "monitorNewItems": "all",
                   "addOptions": {"monitor": monitor, "searchForMissingBooks": True}})
    arr.call("POST", "author", chosen)
    return Result("added", f"Auteur toegevoegd aan Readarr (bewaken: {monitor}): {label(chosen)}.", notes=notes)


# ------------------------------------------------------------------ radarr ---

def _movie_label(m):
    return f"{m.get('title', '')} ({_year(m)})"


def radarr_movie(arr: Arr, query: str, prefix: str) -> Result:
    explicit = bool(EXPLICIT_RE.match(query))
    movies = arr.call("GET", "movie/lookup", term=query) or []
    chosen, ranked = pick(query, movies, _movie_label, explicit)
    if chosen is None:
        return _ambiguous(prefix, ranked, _movie_label, lambda m: f"tmdb:{m.get('tmdbId')}", "film")
    if chosen.get("id"):
        return Result("exists", f"Staat al in Radarr: {_movie_label(chosen)}.")
    q_id, _, root, notes = arr.profiles("movie", need_metadata=False)
    chosen.update({"qualityProfileId": q_id, "rootFolderPath": root, "monitored": True,
                   "minimumAvailability": "released",
                   "addOptions": {"searchForMovie": True, "monitor": "movieOnly"}})
    arr.call("POST", "movie", chosen)
    return Result("added", f"Toegevoegd aan Radarr en zoekopdracht gestart: {_movie_label(chosen)}.", notes=notes)


# ------------------------------------------------------------------ sonarr ---

def _series_label(s):
    return f"{s.get('title', '')} ({_year(s)})"


def sonarr_series(arr: Arr, query: str, prefix: str, monitor: str) -> Result:
    explicit = bool(EXPLICIT_RE.match(query))
    series = arr.call("GET", "series/lookup", term=query) or []
    chosen, ranked = pick(query, series, _series_label, explicit)
    if chosen is None:
        return _ambiguous(prefix, ranked, _series_label, lambda s: f"tvdb:{s.get('tvdbId')}", "serie")
    if chosen.get("id"):
        return Result("exists", f"Staat al in Sonarr: {_series_label(chosen)}.")
    q_id, _, root, notes = arr.profiles("series", need_metadata=False)
    chosen.update({"qualityProfileId": q_id, "rootFolderPath": root, "monitored": True,
                   "seasonFolder": True,
                   "addOptions": {"monitor": monitor, "searchForMissingEpisodes": True}})
    try:  # Sonarr v3 requires a language profile; v4 dropped the endpoint
        langs = arr.call("GET", "languageprofile") or []
        if langs:
            chosen["languageProfileId"] = langs[0]["id"]
    except RequestError:
        pass
    arr.call("POST", "series", chosen)
    return Result("added", f"Toegevoegd aan Sonarr (bewaken: {monitor}) en zoekopdracht gestart: "
                           f"{_series_label(chosen)}.", notes=notes)


def handle(arrs: dict, opts: dict, service: str, kind: str, query: str, prefix: str) -> Result:
    arr = arrs[service]
    if kind == "album":
        return lidarr_album(arr, query, prefix)
    if kind == "artist":
        return lidarr_artist(arr, query, prefix, opts.get("lidarr_artist_monitor", "all"))
    if kind == "book":
        return readarr_book(arr, query, prefix)
    if kind == "author":
        return readarr_author(arr, query, prefix, opts.get("readarr_author_monitor", "all"))
    if kind == "movie":
        return radarr_movie(arr, query, prefix)
    if kind == "series":
        return sonarr_series(arr, query, prefix, opts.get("sonarr_series_monitor", "all"))
    raise RequestError(f"Onbekend soort verzoek: {kind}")
