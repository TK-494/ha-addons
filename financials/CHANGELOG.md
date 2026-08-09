# Changelog — Financials

## 0.3.2 — 2026-08-09

### Fixed
- **Build brak op Home Assistant.** `pip install --require-hashes=false` is ongeldig: het is een
  schakelaar zonder waarde, dus pip stopte met een usage-fout en de image werd nooit gebouwd. Vlag
  verwijderd; de versies staan al vast in `requirements.txt` en `scripts/audit.sh` controleert ze
  buiten de build om.
- Het opruimen van `__pycache__` gebeurde met een glob die op een andere basis-image niets vindt en
  dan de build laat mislukken. Weggehaald — `PYTHONDONTWRITEBYTECODE` doet het werk al.
- De gebruiker werd op UID 1000 vastgezet, wat botst als de basis-image dat nummer al gebruikt.
  Alpine kiest nu zelf een nummer; niets buiten de container hangt ervan af.

## 0.3.1 — 2026-08-09

### Fixed
- Categorieën konden alleen verwijderd worden, niet aangemaakt of hernoemd. De API kon het al; het
  formulier ontbrak. Nu een **Nieuwe categorie**-knop en klik-om-te-bewerken, inclusief kleur,
  inkomsten-vlag en *buiten het budget houden*.

## 0.3.0 — 2026-08-09

### Nieuw
- **Budget per categorie per maand**, met doorschuiven van wat je overhoudt, *vorige maand
  overnemen* en een voorstel op basis van de mediaan van de afgelopen zes maanden.
- **Sensoren in Home Assistant** via de Supervisor — saldo totaal en per rekening, uitgaven en
  inkomsten deze maand, vaste lasten en het aantal ongecategoriseerde transacties. Geen token of
  configuratie nodig; bijgewerkt na elke import en elk half uur.

### Techniek
- Sensorpublicatie is best effort: een onbereikbare Supervisor laat een import nooit mislukken, en
  buiten Home Assistant doet de module niets.
- Interne overboekingen tellen nooit mee in een budget.
- 93 tests.

## 0.2.0 — 2026-08-09

### Nieuw
- **Overzichtspagina**: KPI's met vergelijking t.o.v. vorige periode, cashflow per maand,
  categorieverdeling, saldoverloop en vaste-versus-variabele lasten. Om te schakelen tussen
  huishouden (interne overboekingen eruit) en één rekening (die tellen wél mee).
- **Categorie-detail** met verloop en grootste tegenpartijen.
- **Terugkerende betalingen** herkend op incassant-ID, met bedrag per maand en signalering als een
  bedrag verandert.
- **Werkvoorraad**: ongecategoriseerde transacties gegroepeerd, grootste bedragen eerst.
- **Eigen rekening toevoegen zonder import**, zodat geld naar een rekening die je niet importeert
  niet als uitgave telt.

### Fixed
- Creditcard-afschrijvingen van vóór de kaartexport telden als uitgave; nu herkend als intern met de
  melding dat de andere kant ontbreekt.
- `detect_salary_day` gebruikte een ongeldig SQL-type en liet de instellingenpagina crashen.

## 0.1.0 — 2026-08-09

Eerste versie. Opvolger van de `finance-dashboard` add-on, opnieuw opgebouwd
zodat meerdere rekeningen en een creditcard vanaf het begin in het datamodel
passen.

### Nieuw

- **Drie CSV-formaten**: Rabobank betaal/spaar, Rabobank creditcard en ASN Bank.
  Automatische herkenning met handmatige keuze eroverheen.
- **Controlescherm vóór import**: herkend formaat, rekening, aantal regels,
  periode en de eerste vijf regels zoals ze gelezen zijn. Pas daarna wordt er
  iets opgeslagen.
- **Geüploade bestanden blijven bewaard** in `/data/uploads`: opnieuw inlezen,
  downloaden, of verwijderen — met of zonder de bijbehorende transacties.
- **Scheiding tussen rekeningen**: overboekingen tussen je eigen rekeningen
  worden aan elkaar gekoppeld en tellen niet mee als inkomsten of uitgaven,
  terwijl beide regels blijven bestaan en de saldi blijven kloppen.
- **Creditcard-afrekening verrekend** tegen de losse kaartaankopen, zodat
  uitgaven niet dubbel geteld worden.
- **Categorieregels in de database** in plaats van in de code, met een
  Nederlandse startset en een "regel maken"-knop die vooraf toont hoeveel
  transacties geraakt worden.
- **Maandgrens instelbaar**: kalendermaand, salarisdag of een vaste dag.

### Techniek

- Bedragen als hele centen; geen floats in de boekhouding.
- Geen pandas: stdlib `csv`, wat de image fors kleiner maakt.
- Container draait als niet-root gebruiker waar het kan, met een eerlijke
  waarschuwing als dat op de host niet lukt.
- CSP, nosniff, referrer-policy en permissions-policy; `X-Frame-Options`
  bewust weggelaten omdat Ingress de add-on in een iframe toont.
- Padtraversal-bescherming op alle bestandspaden, upload-limiet van 25 MB in
  blokken gelezen, formule-injectie geneutraliseerd bij export, IBAN's
  afgekort in de logs.
- 64 tests op synthetische bestanden; geen echte bankgegevens in de repository.

### Bekend

- Geen `package-lock.json`, dus de Docker-build gebruikt `npm install`.
- Overzichtspagina met grafieken volgt in 0.2.0.
