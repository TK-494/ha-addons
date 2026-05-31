# Installatiehandleiding — Apple Health Dashboard

Deze handleiding helpt je het gezondheidsdashboard te installeren, lokaal of op
een server in je eigen netwerk. Je hebt er geen technische voorkennis voor
nodig; volg de stappen op volgorde.

De app is bedoeld voor **lokaal, offline en intern gebruik**. Alle data blijft op
je eigen machine. De app start ook **zonder** data: je krijgt dan een leeg
dashboard en vult het later via de uploadpagina.

## Vereisten

Installeer vooraf:

- **Git** — om de code te downloaden.
- **Docker** — om de app in een container te draaien.
- **Docker Compose** (de `docker compose`-plugin, versie 2) — wordt door Docker
  gebruikt om de app te starten.

Op een Mac krijg je Docker en Docker Compose samen via Docker Desktop. Op een
Linux-server installeer je Docker Engine met de Docker Compose-plugin.

## Stap 1 — Code downloaden

```bash
git clone <REPO_URL>
cd apple-health-dashboard
```

Vervang `<REPO_URL>` door het adres van de repository.

## Stap 2 — Installeren

Er zijn drie manieren om te starten. Kies er één.

### Lokaal (aanbevolen om mee te beginnen)

```bash
./scripts/quickstart.sh
```

Dit controleert Docker, maakt een `.env` aan met veilige standaardwaarden en
start de app. Een bestaande `.env` wordt nooit overschreven. De app is daarna
alleen bereikbaar vanaf deze machine, op `http://127.0.0.1:8095`.

### Testen op een andere poort

Wil je de app naast een bestaande installatie testen, kies dan een andere poort:

```bash
APP_PORT=18095 ./scripts/quickstart.sh
```

De app is dan bereikbaar op `http://127.0.0.1:18095`.

### Op een interne server / LAN

Wil je de app vanaf andere apparaten in je eigen netwerk kunnen openen:

```bash
APP_HOST=<LOCAL_SERVER> APP_PORT=18095 ./scripts/quickstart.sh
```

Vervang `<LOCAL_SERVER>` door het interne adres of de hostnaam van je server.

#### Lokaal of intern — wat is het verschil?

- `APP_HOST=127.0.0.1` is **veilig lokaal**: de app is alleen bereikbaar vanaf de
  machine waarop hij draait.
- `APP_HOST=<LOCAL_SERVER>` maakt de app **bereikbaar op het interne netwerk**:
  andere apparaten in hetzelfde netwerk kunnen hem openen.

> **Waarschuwing.** Zodra je de app op het interne netwerk beschikbaar maakt, is
> ook de **uploadpagina** bereikbaar voor elk apparaat dat bij dat netwerk kan.
> De uploadpagina heeft geen eigen wachtwoord. Doe dit alleen op een vertrouwd
> netwerk. Zet de app **nooit** zomaar op het open internet (zie *Publieke
> toegang* onderaan).

## Stap 3 — Het dashboard openen

Open in je browser:

- lokaal: `http://127.0.0.1:8095`
- testpoort: `http://127.0.0.1:18095`
- interne server: `http://<LOCAL_SERVER>:18095`

Bij de eerste keer is het dashboard **leeg**. Dat is normaal: er is nog geen
data geïmporteerd.

## Stap 4 — De uploadpagina openen

Voeg `/upload` toe aan het adres, bijvoorbeeld:

```
http://127.0.0.1:8095/upload
```

Hier upload je je Apple Health `export.zip`. Hoe je die export maakt, staat in
[APPLE_HEALTH_EXPORT.md](APPLE_HEALTH_EXPORT.md). Na een geslaagde import vult het
dashboard zich vanzelf.

## Configuratie — het `.env`-bestand

De instellingen staan in een `.env`-bestand in de projectmap. `quickstart.sh`
maakt dit bestand met veilige standaardwaarden; meestal hoef je niets aan te
passen. Commit je `.env` nooit.

| Instelling | Wat het doet | Standaard |
|---|---|---|
| `APP_HOST` | Bepaalt wie de app kan bereiken. `127.0.0.1` = alleen deze machine; een intern adres = bereikbaar op het LAN. | `127.0.0.1` |
| `APP_PORT` | De poort waarop de app luistert. | `8095` |
| `HEALTH_DATA_DIR` | De map waarin de verwerkte data wordt bewaard. Blijft buiten version control. | `./data/parsed` |
| `RELOAD_TOKEN` | Beschermt het herlaad-endpoint van de app. Laat dit niet op de standaardwaarde staan zodra de app breder bereikbaar is. | `change-me` |

> Bewaar tokens buiten de repo en zet ze niet in commando's of broncode.

## Opruimen

De app stoppen en de container verwijderen:

```bash
docker compose down
```

Je data in `HEALTH_DATA_DIR` blijft hierbij staan; die wordt niet verwijderd.

## Problemen oplossen

**De poort is al in gebruik.**
Kies een andere poort, bijvoorbeeld `APP_PORT=18095 ./scripts/quickstart.sh`, en
open de app op die poort.

**"Docker niet gevonden" of "docker compose werkt niet".**
Docker of de Docker Compose-plugin is niet geïnstalleerd of nog niet gestart.
Start Docker (op Mac: Docker Desktop) en probeer het opnieuw. Controleren kan met
`docker compose version`.

**"Permission denied" bij `git clone`.**
Je hebt geen toegang tot de repository, of geen schrijfrechten in de huidige map.
Controleer de `<REPO_URL>` en je toegangsrechten, en clone naar een map waar je
mag schrijven.

**Het dashboard is leeg.**
Dat is normaal zolang er nog geen data is geïmporteerd. Ga naar `/upload` en
upload je Apple Health `export.zip`.

**De uploadpagina opent, maar er verschijnt geen data.**
De import loopt mogelijk nog of er ging iets mis. Wacht tot de import klaar is en
ververs het dashboard. De importstatus kun je controleren via
`/api/import/status`. Zie ook de troubleshooting in
[APPLE_HEALTH_EXPORT.md](APPLE_HEALTH_EXPORT.md).

## Publieke toegang — niet zonder extra beveiliging

Deze app is bedoeld voor lokaal en intern gebruik. Wil je hem toch buiten je
eigen netwerk bereikbaar maken (bijvoorbeeld op `https://<APP_DOMAIN>`), zet er
dan altijd je eigen reverse proxy met versleuteling (TLS) en een inlogscherm vóór,
of gebruik een VPN. Zet de uploadpagina nooit onbeveiligd op het open internet.
