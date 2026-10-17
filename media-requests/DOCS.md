# Media Requests

Zet een item op de takenlijst **Media verzoeken** (`todo.media_verzoeken`). Binnen een minuut
voegt deze add-on het toe aan de juiste *arr-app. Wat er gebeurd is, staat daarna in de
beschrijving van het item.

## Zo schrijf je een verzoek

| Begin met | Gaat naar | Voorbeeld |
|---|---|---|
| `muziek:` / `nummer:` / `album:` | Lidarr (album) | `muziek: Teardrop - Massive Attack` |
| `artiest:` | Lidarr (hele artiest) | `artiest: Portishead` |
| `boek:` | Readarr (één boek) | `boek: Project Hail Mary` |
| `auteur:` | Readarr (hele auteur) | `auteur: Andy Weir` |
| `film:` | Radarr | `film: The Matrix 1999` |
| `serie:` | Sonarr | `serie: Breaking Bad` |

- **Een nummer** wordt het album waar het op staat. Lidarr kent geen losse nummers. Schrijf
  `titel - artiest`. De add-on zoekt via MusicBrainz het oorspronkelijke studioalbum op, dus geen
  verzamelalbum of single.
- **Een jaartal** helpt bij remakes: `film: Dune 2021`.
- **ID's** werken altijd: `film: tmdb:603`, `serie: tvdb:81189`, `album: lidarr:<MusicBrainz-id>`,
  `boek: isbn:9780593135204`.

## Wat er daarna gebeurt

- ✅ **Toegevoegd** of ☑️ **stond er al**: het item wordt afgevinkt.
- ❓ **Twijfel**: het item blijft open, met maximaal vier opties in de beschrijving. Wijzig de titel
  van het item in één van die regels, dan probeert hij het opnieuw.
- ⚠️ **Mislukt**: de reden staat in de beschrijving. Het item blijft open tot je de titel aanpast.
- ⏳ **App niet bereikbaar**: hij probeert het elke minuut opnieuw. Je hoeft niets te doen.

Een verzoek voor één album of boek bewaakt alleen dat album of boek, niet de hele discografie.
`artiest:` en `auteur:` bewaken wel alles (instelbaar).

## Instellingen

Je hoeft meestal niets in te vullen. De API-keys en eventuele URL-bases leest de add-on zelf uit
de `config.xml` van Lidarr, Readarr, Radarr en Sonarr.

- `*_quality_profile`, `*_metadata_profile`, `*_root_folder`: leeg laten betekent:
  - is er er maar één, dan gebruikt hij die;
  - zijn er meer, dan gebruikt hij degene die het meest in je bibliotheek voorkomt, en dat staat er
    dan bij in de beschrijving;
  - kan hij niet kiezen, dan krijg je een melding met de namen. Hij gokt nooit stilletjes.
- `notify_service`: bijvoorbeeld `notify.notify` voor een pushbericht na elke toevoeging.
- `*_url` / `*_api_key`: alleen nodig als automatisch uitlezen niet lukt. Het log toont bij de
  start per app waar de key vandaan komt.
