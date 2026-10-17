# Changelog

## 0.1.4 — 2026-10-17
- Fixed: the Readarr author lookup searched "andy Project Hail Mary weir" — `authorTitle` carries the book title after the name ("weir, andy Project Hail Mary"); it is now stripped.
- Lookup timeout 30 → 60 s; Readarr's metadata mirror is slow.
- Close scores: the single candidate whose title is in the query and whose label covers the rest wins ("Mezzanine Massive Attack" no longer asks about "Mezzanine B-Sides"). Same-title remakes still ask.

## 0.1.3 — 2026-10-17
- Fixed: `album: Mezzanine Massive Attack` added an unrelated album. Every album titled "Mezzanine" tied on its bare title, so the artist was ignored; the bare title now only counts when the query names nothing else.
- Fixed: the MusicBrainz song fallback accepted any recording. It now runs for song prefixes only (`muziek:`, `nummer:`, …, never `album:`) and requires track + artist to match the query.
- Summaries, study guides and tribute/karaoke releases score half unless the query asks for them.

## 0.1.2 — 2026-10-17
- Fixed: a song request could add its single instead of the album. Direct Lidarr matches are now studio albums only; singles/EPs need an explicit `lidarr:` ID.
- Fixed: Readarr `POST book` failed with "Author.ForeignAuthorId must not be empty" — the book lookup returns an author stub, so the author is now resolved through `author/lookup` first.
- *arr validation errors are shown as their message, not as raw JSON.

## 0.1.1 — 2026-10-17
- Removed personal setup details from README and a code comment.
- Fixed: `SUPERVISOR_TOKEN missing` on start — s6-overlay doesn't pass it to a plain CMD; the token is now also read from `/run/s6/container_environment`.

## 0.1.0 — 2026-10-17
- First version. Polls `todo.media_verzoeken` and adds requests to Lidarr (album/artist, songs
  resolved to their studio album through MusicBrainz), Readarr (book/author), Radarr (movie) and
  Sonarr (series).
- API keys and URL bases are read from each app's `config.xml` through a read-only
  `all_addon_configs` map.
- Ambiguous matches stay open with paste-ready choices. Profile defaults are reported, never silent.
