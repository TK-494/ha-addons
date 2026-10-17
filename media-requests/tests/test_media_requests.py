"""Behaviour tests with a fake HTTP layer. All fixtures are invented."""
import json
import os
import sys
import urllib.parse

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import arr  # noqa: E402
import handlers  # noqa: E402
import main  # noqa: E402


class Fake:
    """Routes (method, path) to canned JSON and records every write."""

    def __init__(self):
        self.routes, self.calls = {}, []

    def on(self, method, path, value):
        self.routes[(method, path)] = value

    def __call__(self, method, url, headers=None, body=None):
        u = urllib.parse.urlparse(url)
        key = (method, u.path)
        self.calls.append((method, u.path, urllib.parse.parse_qs(u.query), body))
        if key not in self.routes:
            raise AssertionError(f"unexpected {method} {u.path}")
        v = self.routes[key]
        if isinstance(v, Exception):
            raise v
        return v(urllib.parse.parse_qs(u.query), body) if callable(v) else v

    def writes(self, method=None, path=None):
        return [c for c in self.calls if c[0] != "GET" and (method is None or c[0] == method)
                and (path is None or c[1].endswith(path))]


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(arr, "http_json", f)
    monkeypatch.setattr(main, "http_json", f)
    return f


def mk(name, opts=None, tmp_path=None):
    o = {f"{name}_api_key": "k", f"{name}_url": f"http://{name}"}
    o.update(opts or {})
    return arr.Arr(name, o, config_roots=[str(tmp_path)] if tmp_path else [])


def profiles(fake, base, api, owners, owner_path, metadata=True):
    fake.on("GET", f"{base}/api/{api}/qualityprofile", [{"id": 1, "name": "Any"}, {"id": 4, "name": "HD"}])
    if metadata:
        fake.on("GET", f"{base}/api/{api}/metadataprofile", [{"id": 2, "name": "Standard"}])
    fake.on("GET", f"{base}/api/{api}/rootfolder", [{"id": 1, "path": "/share/media/x"}])
    fake.on("GET", f"{base}/api/{api}/{owner_path}", owners)


# ------------------------------------------------------------------ parse ---

@pytest.mark.parametrize("s,expected", [
    ("film: The Matrix", ("radarr", "movie", "The Matrix")),
    ("Muziek: Teardrop - Massive Attack", ("lidarr", "album", "Teardrop - Massive Attack")),
    ("boek：Dune", ("readarr", "book", "Dune")),
    ("serie: tvdb:81189  (Breaking Bad (2008))", ("sonarr", "series", "tvdb:81189")),
    ("artiest: Portishead", ("lidarr", "artist", "Portishead")),
])
def test_parse(s, expected):
    assert handlers.parse(s)[:3] == expected


@pytest.mark.parametrize("s", ["The Matrix", "taart: appel", ""])
def test_parse_rejects(s):
    assert handlers.parse(s) is None


# ---------------------------------------------------------------- scoring ---

def test_pick_clear_winner():
    cands = [{"title": "The Matrix", "year": 1999}, {"title": "The Matrix Reloaded", "year": 2003}]
    chosen, _ = arr.pick("the matrix 1999", cands, handlers._movie_label, False)
    assert chosen["year"] == 1999


def test_pick_refuses_remake_tie():
    cands = [{"title": "Dune", "year": 1984}, {"title": "Dune", "year": 2021}]
    chosen, ranked = arr.pick("Dune", cands, handlers._movie_label, False)
    assert chosen is None and len(ranked) == 2


def test_pick_year_breaks_tie():
    cands = [{"title": "Dune", "year": 1984}, {"title": "Dune", "year": 2021}]
    chosen, _ = arr.pick("Dune 2021", cands, handlers._movie_label, False)
    assert chosen["year"] == 2021


def test_pick_rejects_weak():
    chosen, _ = arr.pick("completely different", [{"title": "The Matrix", "year": 1999}],
                         handlers._movie_label, False)
    assert chosen is None


# ----------------------------------------------------------------- radarr ---

def test_radarr_adds_movie(fake):
    a = mk("radarr")
    fake.on("GET", "/api/v3/movie/lookup", [{"title": "The Matrix", "year": 1999, "tmdbId": 603}])
    profiles(fake, "", "v3", [{"qualityProfileId": 4}, {"qualityProfileId": 4}, {"qualityProfileId": 1}], "movie",
             metadata=False)
    fake.on("POST", "/api/v3/movie", {})
    r = handlers.radarr_movie(a, "The Matrix 1999", "film")
    assert r.status == "added"
    body = fake.writes("POST", "/movie")[0][3]
    assert body["qualityProfileId"] == 4 and body["addOptions"]["searchForMovie"] is True
    assert any("meest gebruikt" in n for n in r.notes)  # the derived default is reported, not silent


def test_radarr_existing_is_not_readded(fake):
    a = mk("radarr")
    fake.on("GET", "/api/v3/movie/lookup", [{"id": 7, "title": "The Matrix", "year": 1999, "tmdbId": 603}])
    r = handlers.radarr_movie(a, "The Matrix", "film")
    assert r.status == "exists" and fake.writes() == []


def test_radarr_ambiguous_offers_ids(fake):
    a = mk("radarr")
    fake.on("GET", "/api/v3/movie/lookup", [{"title": "Dune", "year": 1984, "tmdbId": 841},
                                            {"title": "Dune", "year": 2021, "tmdbId": 438631}])
    r = handlers.radarr_movie(a, "Dune", "film")
    assert r.status == "ambiguous" and fake.writes() == []
    assert r.choices[0].startswith("film: tmdb:")
    # pasting a choice back resolves it
    assert handlers.parse(r.choices[0])[2].startswith("tmdb:")


def test_no_profile_choice_is_a_hard_error(fake):
    a = mk("radarr")
    fake.on("GET", "/api/v3/movie/lookup", [{"title": "Heat", "year": 1995, "tmdbId": 949}])
    profiles(fake, "", "v3", [], "movie", metadata=False)  # empty library: nothing to derive from
    with pytest.raises(arr.RequestError, match="meerdere quality profile"):
        handlers.radarr_movie(a, "Heat 1995", "film")
    assert fake.writes() == []


def test_configured_profile_wins(fake):
    a = mk("radarr", {"radarr_quality_profile": "any"})
    fake.on("GET", "/api/v3/movie/lookup", [{"title": "Heat", "year": 1995, "tmdbId": 949}])
    profiles(fake, "", "v3", [{"qualityProfileId": 4}], "movie", metadata=False)
    fake.on("POST", "/api/v3/movie", {})
    r = handlers.radarr_movie(a, "Heat 1995", "film")
    assert fake.writes("POST")[0][3]["qualityProfileId"] == 1 and r.notes == []


# ----------------------------------------------------------------- sonarr ---

def test_sonarr_v4_without_language_profiles(fake):
    a = mk("sonarr")
    fake.on("GET", "/api/v3/series/lookup", [{"title": "Breaking Bad", "year": 2008, "tvdbId": 81189}])
    profiles(fake, "", "v3", [{"qualityProfileId": 1}], "series", metadata=False)
    fake.on("GET", "/api/v3/languageprofile", arr.RequestError("HTTP 404"))
    fake.on("POST", "/api/v3/series", {})
    r = handlers.sonarr_series(a, "Breaking Bad", "serie", "all")
    body = fake.writes("POST")[0][3]
    assert r.status == "added" and "languageProfileId" not in body
    assert body["addOptions"] == {"monitor": "all", "searchForMissingEpisodes": True}


# ----------------------------------------------------------------- lidarr ---

def album(title, artist, fid, year=1998, **kw):
    return dict({"title": title, "foreignAlbumId": fid, "releaseDate": f"{year}-04-20",
                 "artist": {"artistName": artist, "foreignArtistId": "art-1"}}, **kw)


def test_lidarr_album_direct(fake):
    a = mk("lidarr")
    fake.on("GET", "/api/v1/album/lookup", [album("Mezzanine", "Massive Attack", "rg-1")])
    fake.on("GET", "/api/v1/album", [])
    profiles(fake, "", "v1", [{"qualityProfileId": 1, "metadataProfileId": 2}], "artist")
    fake.on("POST", "/api/v1/album", {})
    r = handlers.lidarr_album(a, "Mezzanine Massive Attack", "muziek")
    body = fake.writes("POST")[0][3]
    assert r.status == "added"
    assert body["artist"]["addOptions"]["monitor"] == "none"  # only this album, not the discography
    assert body["addOptions"] == {"searchForNewAlbum": True}


def test_lidarr_track_resolves_via_musicbrainz(fake, monkeypatch):
    a = mk("lidarr")

    def lookup(q, _):
        term = q["term"][0]
        return [album("Mezzanine", "Massive Attack", "rg-1")] if term == "lidarr:rg-1" else \
            [album("Teardrop (single)", "Someone Else", "rg-9", 2010)]
    fake.on("GET", "/api/v1/album/lookup", lookup)
    monkeypatch.setattr(handlers, "musicbrainz_album_for_track",
                        lambda t: [{"rgid": "rg-1", "title": "Mezzanine", "artist": "Massive Attack",
                                    "year": "1998", "track": "Teardrop", "score": 100}])
    fake.on("GET", "/api/v1/album", [])
    profiles(fake, "", "v1", [{"qualityProfileId": 1, "metadataProfileId": 2}], "artist")
    fake.on("POST", "/api/v1/album", {})
    r = handlers.lidarr_album(a, "Teardrop - Massive Attack", "muziek")
    assert r.status == "added" and "Teardrop" in r.message and "Mezzanine" in r.message


def test_lidarr_unmonitored_album_gets_monitored(fake):
    a = mk("lidarr")
    fake.on("GET", "/api/v1/album/lookup", [album("Mezzanine", "Massive Attack", "rg-1")])
    fake.on("GET", "/api/v1/album", [{"id": 55, "monitored": False}])
    fake.on("PUT", "/api/v1/album/monitor", {})
    fake.on("POST", "/api/v1/command", {})
    r = handlers.lidarr_album(a, "Mezzanine Massive Attack", "muziek")
    assert r.status == "added"
    assert fake.writes("PUT")[0][3] == {"albumIds": [55], "monitored": True}
    assert not fake.writes("POST", "/album")


def test_musicbrainz_prefers_studio_album(fake):
    rec = {"score": 100, "title": "Teardrop", "artist-credit": [{"name": "Massive Attack"}], "releases": [
        {"status": "Official", "date": "2006-01-01",
         "release-group": {"id": "comp", "title": "Collected", "primary-type": "Album",
                           "secondary-types": ["Compilation"]}},
        {"status": "Official", "date": "1998-04-20",
         "release-group": {"id": "rg-1", "title": "Mezzanine", "primary-type": "Album"}},
        {"status": "Official", "date": "1998-04-27",
         "release-group": {"id": "single", "title": "Teardrop", "primary-type": "Single"}},
    ]}
    fake.on("GET", "/ws/2/recording", {"recordings": [rec]})
    out = arr.musicbrainz_album_for_track("Teardrop - Massive Attack")
    assert [o["rgid"] for o in out] == ["rg-1"]


# ---------------------------------------------------------------- readarr ---

def test_readarr_book_marks_one_edition(fake):
    a = mk("readarr")
    fake.on("GET", "/api/v1/book/lookup", [{"title": "Dune", "releaseDate": "1965-08-01", "foreignBookId": "w1",
                                           "author": {"authorName": "Frank Herbert", "foreignAuthorId": "a-1"},
                                           "editions": [{"id": 0, "monitored": False}, {"monitored": False}]}])
    profiles(fake, "", "v1", [{"qualityProfileId": 1, "metadataProfileId": 2}], "author")
    fake.on("POST", "/api/v1/book", {})
    r = handlers.readarr_book(a, "Dune Frank Herbert", "boek")
    body = fake.writes("POST")[0][3]
    assert r.status == "added" and [e["monitored"] for e in body["editions"]] == [True, False]


# --------------------------------------------------------------- config.xml ---

def test_api_key_and_urlbase_from_config_xml(tmp_path):
    d = tmp_path / "db21ed7f_readarr_nas" / "readarr"
    d.mkdir(parents=True)
    (d / "config.xml").write_text("<Config><ApiKey>abc</ApiKey><UrlBase>/readarr</UrlBase></Config>")
    a = arr.Arr("readarr", {}, config_roots=[str(tmp_path)])
    assert a.key == "abc" and a.url == "http://db21ed7f-readarr-nas:8787/readarr"


def test_missing_key_is_reported(tmp_path):
    a = arr.Arr("sonarr", {}, config_roots=[str(tmp_path)])
    with pytest.raises(arr.RequestError, match="sonarr_api_key"):
        a.call("GET", "series")


# --------------------------------------------------------------- main loop ---

class FakeHA(main.HA):
    def __init__(self, items):
        self.items, self.updates = items, []

    def open_items(self, entity):
        return [i for i in self.items if i["status"] == "needs_action"]

    def update(self, entity, uid, description, done):
        self.updates.append((uid, description, done))
        for i in self.items:
            if i["uid"] == uid and done:
                i["status"] = "completed"


def test_loop_answers_once_and_retries_after_rename(fake):
    a = {"radarr": mk("radarr")}
    fake.on("GET", "/api/v3/movie/lookup", lambda q, _: [{"title": "Dune", "year": 1984, "tmdbId": 841},
                                                          {"title": "Dune", "year": 2021, "tmdbId": 438631}]
            if q["term"][0] == "Dune" else [{"id": 3, "title": "Dune", "year": 2021}])
    ha = FakeHA([{"uid": "u1", "summary": "film: Dune", "status": "needs_action"}])
    state = {}
    main.process(ha, a, {"todo_entity": "todo.x"}, state)
    main.process(ha, a, {"todo_entity": "todo.x"}, state)
    assert len(ha.updates) == 1 and ha.updates[0][2] is False  # asked once, item left open
    ha.items[0]["summary"] = "film: tmdb:438631"
    main.process(ha, a, {"todo_entity": "todo.x"}, state)
    assert ha.updates[-1][2] is True and ha.items[0]["status"] == "completed"
    main.process(ha, a, {"todo_entity": "todo.x"}, state)
    assert state == {}  # completed items are forgotten


def test_loop_transient_error_writes_once_then_succeeds(fake):
    a = {"radarr": mk("radarr")}
    fake.on("GET", "/api/v3/movie/lookup", arr.TransientError("down"))
    ha = FakeHA([{"uid": "u1", "summary": "film: Heat", "status": "needs_action"}])
    state = {}
    for _ in range(3):
        main.process(ha, a, {"todo_entity": "todo.x"}, state)
    assert len(ha.updates) == 1 and "niet bereikbaar" in ha.updates[0][1]
    fake.on("GET", "/api/v3/movie/lookup", [{"id": 9, "title": "Heat", "year": 1995}])
    main.process(ha, a, {"todo_entity": "todo.x"}, state)
    assert ha.updates[-1][2] is True


def test_loop_unknown_prefix_and_bug_do_not_stall(fake, monkeypatch):
    a = {"radarr": mk("radarr")}
    monkeypatch.setattr(main, "handle", lambda *a, **k: 1 / 0)
    ha = FakeHA([{"uid": "u1", "summary": "zomaar iets", "status": "needs_action"},
                 {"uid": "u2", "summary": "film: Heat", "status": "needs_action"}])
    main.process(ha, a, {"todo_entity": "todo.x"}, {})
    assert [u[0] for u in ha.updates] == ["u1", "u2"]
    assert "Geen soort" in ha.updates[0][1] and "Interne fout" in ha.updates[1][1]


def test_ha_get_items_shape(fake):
    fake.on("POST", "/core/api/services/todo/get_items",
            {"changed_states": [], "service_response": {"todo.x": {"items": [{"uid": "1", "summary": "s"}]}}})
    ha = main.HA("t", "http://supervisor/core/api")
    assert ha.open_items("todo.x") == [{"uid": "1", "summary": "s"}]
    assert json.dumps(fake.calls[0][3]) == '{"entity_id": "todo.x", "status": "needs_action"}'


# ------------------------------------------------------ live-found regressions ---

def test_lidarr_song_does_not_pick_its_single(fake, monkeypatch):
    a = mk("lidarr")
    fake.on("GET", "/api/v1/album/lookup", lambda q, _: [album("Mezzanine", "Massive Attack", "rg-1")]
            if q["term"][0] == "lidarr:rg-1" else
            [album("Teardrop", "Massive Attack", "rg-s", albumType="Single")])
    monkeypatch.setattr(handlers, "musicbrainz_album_for_track",
                        lambda t: [{"rgid": "rg-1", "title": "Mezzanine", "artist": "Massive Attack",
                                    "year": "1998", "track": "Teardrop", "score": 100}])
    fake.on("GET", "/api/v1/album", [])
    profiles(fake, "", "v1", [{"qualityProfileId": 1, "metadataProfileId": 2}], "artist")
    fake.on("POST", "/api/v1/album", {})
    r = handlers.lidarr_album(a, "Teardrop - Massive Attack", "muziek")
    assert fake.writes("POST")[0][3]["foreignAlbumId"] == "rg-1" and "Mezzanine" in r.message


def test_readarr_author_stub_is_resolved(fake):
    a = mk("readarr")
    fake.on("GET", "/api/v1/book/lookup", [{"title": "Project Hail Mary", "releaseDate": "2021-05-04",
                                           "foreignBookId": "w2", "authorTitle": "weir, andy",
                                           "author": {"authorName": None}, "editions": [{"monitored": True}]}])
    fake.on("GET", "/api/v1/author/lookup", [{"authorName": "Andy Weir", "foreignAuthorId": "a-9"}])
    profiles(fake, "", "v1", [{"qualityProfileId": 1, "metadataProfileId": 2}], "author")
    fake.on("POST", "/api/v1/book", {})
    r = handlers.readarr_book(a, "Project Hail Mary", "boek")
    body = fake.writes("POST")[0][3]
    assert r.status == "added" and body["author"]["foreignAuthorId"] == "a-9"
    assert [c[2]["term"] for c in fake.calls if c[1].endswith("author/lookup")] == [["andy weir"]]


def test_validation_error_is_compact(monkeypatch):
    import io
    import urllib.error
    err = urllib.error.HTTPError("http://x/api", 400, "Bad", {},
                                 io.BytesIO(b'[{"propertyName":"A","errorMessage":"A must not be empty."}]'))
    monkeypatch.setattr(arr.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(err))
    with pytest.raises(arr.RequestError, match=r"HTTP 400 from http://x/api: A must not be empty\.$"):
        arr.http_json("GET", "http://x/api")
