# Changelog

## 0.1.0 — 2026-10-17
- First version. Polls `todo.media_verzoeken` and adds requests to Lidarr (album/artist, songs
  resolved to their studio album through MusicBrainz), Readarr (book/author), Radarr (movie) and
  Sonarr (series).
- API keys and URL bases are read from each app's `config.xml` through a read-only
  `all_addon_configs` map.
- Ambiguous matches stay open with paste-ready choices. Profile defaults are reported, never silent.
