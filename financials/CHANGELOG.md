# Changelog — Financials

## 0.11.0 — 2026-08-09

### Nieuw
- **Tabblad Salaris**: al je loonbetalingen bij elkaar, met per betaling de opbouw in vast en
  variabel, een gemiddelde over de laatste twaalf, en een gestapelde grafiek waarin de maand met
  vakantiegeld er direct uitspringt.
- **Sjabloon**: de laatst gemaakte verdeling wordt hergebruikt. De vaste delen blijven gelijk en het
  verschil landt op het variabele deel — je basissalaris is elke maand hetzelfde, de vergoeding is
  wat wisselt. Ook in één klik op alle nog niet verdeelde betalingen toe te passen.
- Weigert het sjabloon toe te passen als de vaste delen samen groter zijn dan die betaling, in plaats
  van een verdeling te maken die niet klopt.

### Fixed
- De salaris-route riep zichzelf intern aan als gewone functie, waardoor FastAPI's `Query`-object in
  plaats van het getal in de query terechtkwam en de fout ver van de oorzaak opdook.

### Techniek
- 191 tests.

## 0.10.0 — 2026-08-09

### Nieuw
- **Een regel kan meerdere patronen bevatten**, één per regel tekst, met dezelfde categorie en
  prioriteit. Varianten van dezelfde winkel horen daarmee bij elkaar in plaats van in losse regels.
- **Suggestie na handmatig categoriseren.** Zijn er meer transacties van dezelfde tegenpartij zonder
  categorie, dan biedt de app aan het patroon toe te voegen aan een *bestaande* regel voor die
  categorie. Zonder dat groeit de regellijst met elke correctie: op een echte set van 544 regels
  waren er 168 zelfgemaakt, waaronder drie aparte McDonald's-varianten en tien motorzaken.
- Je eigen regels worden als eerste voorgesteld, daarna regels die al meerdere patronen verzamelen.
  Een geseede regel met alleen `hypotheek` aanbieden als plek voor je huisbaas is technisch juist en
  duidelijk verkeerd.

### Techniek
- De regel-engine compileert een regel naar één vergelijking per patroon, dus de
  eerste-passende-wint-volgorde downstream verandert niet.
- Patronen behouden hun spaties; alleen de regeleindes die ze scheiden worden verwijderd.
- 181 tests.

## 0.9.0 — 2026-08-09

### Nieuw
- **Balk bovenaan het overzicht** met vrij besteedbaar bedrag, dagen tot het volgende loon, de
  verdeling vast/variabel inkomen, en tot welke datum de gegevens lopen.
- **Vrij besteedbaar** trekt niet alleen af wat je al uitgaf, maar ook de incasso's die deze periode
  nog komen. Alleen betalingen met een machtiging tellen mee — de supermarkt herhaalt zich ook, maar
  wordt niet geïncasseerd.
- **Dagen tot loon** uit je eigen betaalgeschiedenis, met weekends en Nederlandse feestdagen. Op 39
  historische betalingen voorspelt de regel er 36 exact, inclusief de verschuiving voor
  Pinkstermaandag. December wisselt te veel en wordt als schatting gemarkeerd in plaats van als feit.
- **Transacties verdelen over meerdere categorieën.** Bedoeld voor loon — basissalaris apart van
  reiskosten- en thuiswerkvergoeding — maar werkt net zo goed voor een bouwmarktbon. De delen moeten
  tot op de cent kloppen met het bedrag.
- **Variabel inkomen** als eigenschap van een categorie, zodat het overzicht vaste en wisselende
  inkomsten uit elkaar houdt.
- **Datumdekking per rekening**, met waarschuwing welke rekening achterloopt en hoeveel dagen.
- **Uitgebreidere regelcontrole**: naast dubbele en overschaduwde regels nu ook identieke regels,
  dezelfde organisatie in twee categorieën, en (op verzoek) regels die op geen enkele transactie
  passen.

### Techniek
- Categorie-overzichten lezen de delen van een verdeelde transactie in plaats van het totaalbedrag.
- Schemaversie 6: tabel `transaction_splits`, kolom `categories.variable_income`.
- 174 tests.

## 0.8.1 — 2026-08-09

### Fixed
- **Salarisdag deed niets zolang er geen betaler gekozen was.** Zonder salarisbron valt er geen
  salarisdatum te vinden, dus viel elke maand terug op de vaste dag — de stand leek actief maar
  gedroeg zich exact als *Vaste dag*. Een salaris dat op de 22e binnenkwam telde daardoor nog steeds
  mee met de vorige maand.
  - Kies je nu Salarisdag en is er een duidelijke kandidaat in je gegevens, dan wordt die automatisch
    ingesteld en krijg je te zien wie. Een betaler die je zelf hebt ingevuld wordt nooit overschreven.
  - Is er geen kandidaat, dan staat er een waarschuwing in plaats van stilte.

## 0.8.0 — 2026-08-09

### Nieuw
- **Regels zijn volledig te bewerken.** Tot nu toe kon je een regel alleen uitzetten of verwijderen;
  nu pas je categorie, veld, vergelijking (bevat / is exact / begint met), waarde, bedragbereik en
  actief-status aan in één scherm.
- **Prioriteit direct in de tabel** aanpasbaar, zonder het bewerkscherm te openen — dat is de knop
  die je nodig hebt als twee regels om dezelfde transactie vechten.
- **Live voorbeeld tijdens het bewerken**: hoeveel transacties de regel raakt, hoeveel er al in die
  categorie staan, hoeveel handmatig vastgezet zijn en hoeveel er dus werkelijk zouden verhuizen,
  met voorbeeldregels. Zo maak je een regel niet per ongeluk te breed.
- Waarschuwing in het bewerkscherm als een waarde een spatie aan het begin of eind heeft, zodat je
  hem niet per ongeluk weghaalt.
- De herkomstkolom toont nu ook wélke batch, of dat een regel vanaf een transactie of via import is
  ontstaan.

### Techniek
- 160 tests, waaronder één die bewijst dat het verlagen van een prioriteit daadwerkelijk een andere
  regel laat winnen.

## 0.7.0 — 2026-08-09

### Nieuw
- **Tweede set standaardregels** voor categorieën die in de praktijk ontstaan: Betaalverzoeken,
  Gaming, Bios/Uitjes, Dating, ICT Hardware en Software, Motor en benodigdheden, plus uitbreidingen
  op Bankkosten, Belasting, Brandstof, Leningen, Sport & Fitness, Zorg & Apotheek, Restaurant,
  Abonnementen, Kleding en Beleggen. Opgesteld op basis van wat er in echte Nederlandse bankdata
  blijft liggen, niet op gevoel.
- **Seed in genummerde batches.** Een update kan nu nieuwe standaardregels meebrengen zonder
  bestaande installaties te overschrijven en zonder regels terug te zetten die je bewust weghaalde.
- **Regels exporteren en importeren** als JSON, inclusief herkomst per regel en het aantal
  transacties dat hij vangt. Categorieën op naam, dus het bestand overleeft een herinstallatie.
- **Conflictcontrole**: waarschuwt bij dubbele patronen en bij regels die door een bredere regel
  worden overschaduwd en dus nooit vuren.
- Elke regel houdt bij hoe hij ontstaan is: standaard, handmatig, vanaf een transactie, of
  geïmporteerd.

### Fixed
- **Regelwaarden werden getrimd.** De spatie in `"ns "` is juist wat voorkomt dat hij "jetbrai**ns**"
  vangt; bij import werd die weggehaald, wat 28 precieze regels stilzwijgend zou verbreden. Waarden
  worden nu overal letterlijk bewaard.
- `bioscoop` niet opgenomen in de nieuwe set: het bevat `coop`, dat al met hogere prioriteit naar
  Boodschappen wijst, dus de regel had nooit kunnen vuren.

### Techniek
- Nieuwe regels krijgen bewust een lagere prioriteit dan bestaande. Ze kunnen daardoor alleen
  transacties oppakken die nog nergens bij horen — je bestaande categorisering verandert niet.
- Schemaversie 5: `rules.origin`, `seed_batch`, `source_transaction_id`, `note`.
- 155 tests.

## 0.6.0 — 2026-08-09

### Nieuw
- **Maandgrens volgt de werkelijke salarisdatum.** Tot nu toe was *Salarisdag* één vaste dag van de
  maand. Werkgevers schuiven die betaling als hij in het weekend valt of rond de feestdagen, waardoor
  het salaris in die maanden in de vorige periode belandde — in deze gegevens 12 van de 26 maanden.
  Elke periode begint nu op de dag dat het salaris echt geboekt is.
- **Salaris herkennen op naam van de betaler** in plaats van op bedrag. Een drempel van "boven
  €1.000" ving ook leningen op, die op willekeurige dagen binnenkomen en de grens meesleepten. De app
  stelt de werkgever zelf voor op basis van terugkerende grote inkomsten.
- **Correctie per maand** onder Instellingen, met per maand de bron: salarisdatum, vaste dag of
  handmatig. Een handmatige correctie wint altijd en is met één klik terug te draaien.

### Techniek
- De maandindeling in SQL volgt de echte grenzen: één extra CASE-tak per afwijkende maand in plaats
  van één per maand in de historie.
- De "gebruikelijke betaaldag" wordt pas afgeleid vanaf drie waarnemingen; daaronder blijft de
  ingestelde terugvaldag staan in plaats van een dag uit ruis te verzinnen.
- Schemaversie 4: tabel `period_overrides`.
- 141 tests.

## 0.5.0 — 2026-08-09

### Nieuw
- **Spaarrekeningen worden automatisch herkend** — geen pinbetalingen, geen incasso's, verkeer bijna
  volledig tussen eigen rekeningen. Daarmee klopt *Gespaard* meteen, in plaats van € 0,00 te tonen
  tot je een verborgen instelling vindt. Een handmatig gekozen soort wordt nooit overschreven.
- **Inkomsten per categorie** als tweede taartdiagram op het overzicht, even groot als de uitgaven
  ernaast, zodat "waar komt het vandaan" net zo leesbaar is als "waar gaat het heen".
- **Alles selecteren** in het transactieoverzicht: een vinkje in de kopregel voor de hele pagina, en
  *Alle … selecteren* voor de volledige filterselectie over alle pagina's heen.
- Handmatig ingestelde categorieën zijn nu zichtbaar gemarkeerd als **vast**.

### Fixed
- **Handmatig ingestelde categorieën konden verdwijnen.** Werd een transactie later herkend als
  interne overboeking of als creditcard-afrekening, dan werd de categorie gewist — ook als jij hem
  zelf had gezet. Nu wordt alleen een door de app geraden categorie opgeschoond.
- *Ook handmatige keuzes overschrijven* zat wel in de API maar zonder waarschuwing. Die zit nu achter
  een bevestiging die eerst uitrekent hoeveel van jouw keuzes eraan zouden gaan.
- Bankcode `db` werd als incasso gelezen, maar Rabobank gebruikt hem voor diverse boekingen: geen van
  de 1.989 `db`-regels heeft een incassant-ID, terwijl alle 1.679 echte incasso's op `ei` staan. Dat
  blokkeerde de herkenning van een spaarrekening waarvan élke regel `db` is, en gaf een fout label in
  het transactieoverzicht.

### Techniek
- Schemaversie 3: kolom `accounts.kind_auto`, met een echte ALTER voor bestaande installaties.
- 126 tests, waaronder een set die specifiek bewaakt dat geen enkel automatisch proces een handmatige
  keuze ongevraagd overschrijft.

## 0.4.0 — 2026-08-09

### Nieuw
- **Labels**: een tweede laag naast de categorie, voor uitgaven die bij meerdere dingen horen —
  bijvoorbeeld brandstof die bij een vakantie hoort. Eén categorie per transactie (de boekhouding
  blijft kloppen), daarnaast onbeperkt labels.
  - Labels per transactie, met de mogelijkheid er direct een nieuwe aan te maken.
  - Een hele selectie in één keer labelen of ontlabelen.
  - Filteren op label in het transactieoverzicht, en labels in de CSV-export.
  - Pagina **Labels** met per label het totaal, uitgesplitst per categorie.

### Techniek
- Schema-versie 2: nieuwe tabellen `tags` en `transaction_tags`, geen wijziging aan bestaande
  tabellen, dus bestaande installaties migreren vanzelf.
- Labels raken geen enkel bedrag: inkomsten, uitgaven, budgetten en categorieën blijven identiek.
  Daar zijn expliciet tests voor.
- 109 tests.

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
