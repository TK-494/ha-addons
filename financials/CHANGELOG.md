# Changelog — Financials

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
