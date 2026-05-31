# Apple Health Dashboard

Een zelf-gehost, privé gezondheidsdashboard op basis van je eigen Apple
Health-export. Een parser zet de export om naar compacte gegevens; een lokale
webapp toont daar een dashboard bovenop met trends voor stappen, workouts, slaap
en conditie.

De app is bedoeld voor **lokaal, offline en intern gebruik**. Je
gezondheidsgegevens blijven op je eigen machine.

## Privacywaarschuwing

Dit project verwerkt **gevoelige persoonlijke gezondheidsdata**. Ruwe exports,
verwerkte data en uploads horen **niet** in version control en worden nooit
meegecommit. Zet de app niet onbeveiligd op het open internet. Lees
[PRIVACY.md](PRIVACY.md) en [SECURITY.md](SECURITY.md) voordat je begint.

## Snelle installatie

Vanaf een verse download, met één commando:

```bash
./scripts/quickstart.sh
```

Het script controleert Docker, maakt een `.env` aan met veilige
standaardwaarden, start de app en toont de lokale URL. Een bestaande `.env`
wordt nooit overschreven.

Wil je naast een bestaande installatie testen op een andere poort:

```bash
APP_PORT=18095 ./scripts/quickstart.sh
```

## De site openen

Open de app in je browser:

- standaard: `http://127.0.0.1:8095`
- met testpoort: `http://127.0.0.1:18095`

## Eerste gebruik

Bij de eerste start is het **dashboard leeg** — dat is normaal, er is nog geen
data. Vul het zo:

1. Open de uploadpagina: `/upload`.
2. Upload je Apple Health `export.zip`.
3. Wacht tot de import klaar is; het dashboard en de grafieken vullen zich.

Hoe je die export op je iPhone maakt, staat in
[docs/APPLE_HEALTH_EXPORT.md](docs/APPLE_HEALTH_EXPORT.md).

## Meer lezen

- [docs/INSTALL.md](docs/INSTALL.md) — volledige installatiehandleiding (lokaal, test en intern netwerk)
- [docs/APPLE_HEALTH_EXPORT.md](docs/APPLE_HEALTH_EXPORT.md) — Apple Health-export maken en uploaden
- [PRIVACY.md](PRIVACY.md) — hoe met gezondheidsdata wordt omgegaan
- [SECURITY.md](SECURITY.md) — veilige opslag en toegang
