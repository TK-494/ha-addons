# Media Requests — Home Assistant add-on

A to-do list as the request queue for Lidarr, Readarr, Radarr and Sonarr. The end-user page is
[DOCS.md](DOCS.md) (Dutch).

## Why a to-do list

A to-do list is the HA-native object that any client can write to: the HA app, Assist, an
automation, or an AI assistant through the Home Assistant MCP server. No *arr app has to be exposed
outside the LAN, and requests wait in the list until the add-on can process them.

## How it works

```
app/main.py      poll loop: todo.get_items -> handler -> todo.update_item
app/handlers.py  prefix parsing + one handler per kind (album, artist, book, author, movie, series)
app/arr.py       *arr HTTP client, config.xml discovery, match scoring, MusicBrainz track->album
tests/           pytest with a fake HTTP layer; all fixtures invented
```

- **Stdlib only.** It sends a few JSON requests a minute, which doesn't justify a dependency tree
  that then needs auditing.
- **The summary is the key.** `/data/state.json` keeps `uid -> sha256(uid, summary)`. An item that
  was answered isn't touched again until its title changes, because renaming is how the user
  answers a question. Completed and deleted items are dropped from state.
- **An item is completed only when something was added or already present.** Ambiguous and failed
  items stay open with the reason in the description. Nothing disappears unseen.
- **No silent defaults.** Profile and root-folder resolution goes: configured name, else the only
  one, else the most-used one in the library (reported in the description), else a hard error that
  lists the names.
- **Transient errors (unreachable, 5xx) don't change the item.** It gets a ⏳ note once, and the add-on
  retries every poll. 4xx errors and lookups with no result are reported and wait for a rename.
- **Matching:** each candidate is scored as half `SequenceMatcher` ratio and half query-word
  coverage, taking the better of full label and bare title. It is accepted at ≥ 0.75 with a 0.08
  margin over the runner-up. Same-title remakes are always a question unless a year is given.
  Explicit IDs (`tmdb:`, `tvdb:`, `lidarr:`, `isbn:`, …) skip scoring.
- **Songs:** Lidarr tracks albums. When the album lookup has no clear match, the add-on queries
  MusicBrainz recordings (score ≥ 80). It keeps official releases in a release group with
  primary type Album and no secondary types, so not compilations or live albums, and prefers the
  earliest one. That release group then goes back into Lidarr as `lidarr:<rgid>`.
- **Single album/book requests don't monitor the whole artist/author** (`addOptions.monitor: none`).
  An album or book that's in the library but unmonitored gets monitored, then searched.

## API calls used

| App | Lookup | Add | Other |
|---|---|---|---|
| Lidarr v1 | `album/lookup`, `artist/lookup` | `POST album`, `POST artist` | `GET album?foreignAlbumId=`, `PUT album/monitor`, `command AlbumSearch` |
| Readarr v1 | `book/lookup`, `author/lookup` | `POST book`, `POST author` | `PUT book/monitor`, `command BookSearch` |
| Radarr v3 | `movie/lookup` | `POST movie` | |
| Sonarr v3 | `series/lookup` | `POST series` | `languageprofile` (v3 only; a 404 on v4 is ignored) |
| HA Core | `todo.get_items?return_response` | `todo.update_item` | optional notify service |

## Verified vs. not verified

The 38 pytest tests (counted, `pytest -q`) cover parsing, scoring, every handler's request body,
config.xml discovery, and the loop's answer-once, retry-after-rename and transient behaviour. All of
them run against a **fake** HTTP layer.

Not verified before the first install:
- That `map: all_addon_configs` mounts at `/addon_configs` on this Supervisor. `/app_configs` is
  also searched.
- The real response shapes of each *arr lookup on the installed versions, and that Lidarr accepts
  `lidarr:<release-group-id>` in `album/lookup`.
- That Readarr (retired upstream, running on rreading-glasses metadata) accepts `POST book` with one
  monitored edition.
- The Docker build. There's no Docker here, so HA's build is the first compile.

## Known limitations

- Readarr is retired upstream. If its metadata source fails, book lookups fail with it.
- MusicBrainz asks for at most one request per second. Normal use is far below that, and nothing
  enforces the limit.
- No ingress UI: the to-do list is the UI.
