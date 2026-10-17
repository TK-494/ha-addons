# Changelog

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
