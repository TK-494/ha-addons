# Changelog — Financials

## 0.17.0 — 2026-08-09

### Fixed
- **Het overzicht laadde traag.** Drie van de elf verzoeken deden ieder afzonderlijk een volledige
  analyse van terugkerende betalingen over het hele grootboek — 136 ms per stuk, en een
  synchrone server handelt ze na elkaar af. De uitkomst hangt alleen af van de transacties en de
  periode-instelling, dus die wordt nu bewaard achter een vingerafdruk van allebei (één
  aggregaatquery van ~2 ms). **Samen 509 ms → 82 ms**; koud, na een import of herstart, 219 ms.

### Changed
- **Het overzicht is opgeschoond.** Het lastenblok, de grootste tegenpartijen en het saldoverloop
  stonden er dubbel: die hebben inmiddels hun eigen tabblad. Elf verzoeken zijn er zeven geworden.
  Op hun plek staat een verwijzingenblok, zodat wat verdween ook vindbaar blijft.
- **Saldoverloop verhuisd naar Rekeningen**, waar de saldi staan, met een keuze van 6 tot 60 maanden.

### Nieuw
- **Tabblad Nog te categoriseren** — een werkblad in plaats van een lijstje. Per tegenpartij één
  keuzelijst; kiezen verwerkt de hele groep in één keer en schrijft standaard meteen de regel, zodat
  dezelfde groep bij de volgende import niet terugkomt. Met voortgangsbalk en het openstaande bedrag.

### Techniek
- 223 tests, waaronder twee die bewaken dat de cache een hercategorisering of nieuwe transacties
  opmerkt.

## 0.16.0 — 2026-08-09

### Nieuw
- **Kleurenthema instelbaar** onder Instellingen → Uiterlijk, met een **Google**-thema dat de
  kleuren van het Google-thema in Home Assistant volgt: blauw #1a73e8, rood, geel en groen uit het
  Material-palet, vlakke kaarten en ronde knoppen. Licht/donker blijft je systeeminstelling volgen.
- De keuze staat bij de add-on opgeslagen, niet in de browser, dus telefoon en laptop zien er
  hetzelfde uit.

### Techniek
- Kleurschalen lopen nu via CSS-variabelen die Tailwind uitleest, zodat een thema één attribuut op
  `<html>` is in plaats van een herschrijving van 360 kleurklassen in 20 bestanden. Met
  `<alpha-value>` blijven opacity-varianten (`bg-slate-500/40`) werken.
- Het thema wordt vóór de eerste render uit een lokale cache toegepast en daarna verzoend met de
  opgeslagen instelling — anders zie je bij elke keer laden even het verkeerde palet.
- Gecontroleerd dat alle 51 gebruikte kleurklassen in beide paletten gedefinieerd zijn.
- 216 tests.

### Note
- Home Assistant geeft zijn thema niet door aan een add-on-iframe; daar is geen API voor. Dit is
  daarom een bijpassend voorkeursthema, geen live synchronisatie — dat staat ook zo in de UI.

## 0.15.0 — 2026-08-09

### Nieuw
- **Twee nieuwe tabbladen: Vaste lasten en Variabele uitgaven.** Elk met een taartdiagram per
  categorie, grootste tegenpartijen, verloop per maand en een tabel met bedrag, maandgemiddelde,
  aandeel en aantal transacties.
- **Periodekeuze** per tabblad: deze periode, 3, 6 of 12 maanden, of alles vanaf je oudste
  transactie. Voor variabele uitgaven is een langer bereik meestal zinvoller — één maand
  boodschappen is vooral ruis.
- Het taartdiagram is nu een gedeelde component, zodat het overzicht en beide tabbladen dezelfde
  kleuren en indeling gebruiken. Boven acht categorieën gaat de rest in één *overig*-punt, zodat de
  ring blijft kloppen met het bedrag erboven.

### Techniek
- `GET /dashboard/expense-breakdown?kind=&months=`; `months=0` betekent alles. Vast plus variabel is
  precies alle uitgaven, één keer geteld — daar staat een test op.
- 212 tests.

## 0.14.0 — 2026-08-09

### Nieuw
- **Sorteren op elke kolom** in het transactieoverzicht: datum, omschrijving, rekening, bedrag en
  categorie, op- en aflopend. Rekening sorteert op de weergavenaam, niet op nummer. Transacties
  zonder categorie komen in beide richtingen onderaan — een ontbrekende waarde is geen rangorde.
- **Kolombreedtes zijn versleepbaar** en worden onthouden, met een knop om ze terug te zetten. De
  omschrijving wordt niet meer afgekapt maar loopt door, zodat breder maken ook echt meer laat zien.
- **Sidebar inklapbaar** tot pictogrammen (≈170 px winst voor de tabel), met de naam als tooltip.
  Ook onthouden.

### Techniek
- De sorteer-join zit alleen op de paginaquery, niet op de telling en de somrijen: anders zou een
  transactie met een ontbrekende rekeningregel stil uit de totalen vallen terwijl hij wel in de
  lijst staat. Daar staat een test op.
- 206 tests.

## 0.13.1 — 2026-08-09

### Security
- **Afhankelijkheden bijgewerkt na een audit.** `pip-audit` meldde veertien
  beveiligingsadviezen tegen de vastgezette versies, allemaal in `starlette` en
  `python-multipart` — precies de twee bibliotheken die het uploaden van bestanden afhandelen, en
  dus het grootste aanvalsoppervlak van deze add-on. Bijgewerkt naar fastapi 0.141.1,
  starlette 1.6.0, python-multipart 0.0.32, sqlalchemy 2.0.51, pydantic 2.13.4, uvicorn 0.52.1.
  Daarna: geen bekende kwetsbaarheden, alle 208 tests groen, en met een echte server geverifieerd
  door 9.193 regels te importeren.

### Fixed
- **Testaantallen klopten niet.** Vanaf 0.9.0 stonden er te hoge getallen in dit changelog — geschat
  in plaats van geteld. De suite telt **201 gevallen** uit 189 testfuncties (parametrisering telt
  door). Er ontbreekt niets; alleen het getal was mis.
- **Schemaversie stond op 3** terwijl er migraties voor 4, 5 en 6 bestonden. Een bestaande database
  werd daardoor bij elke start opnieuw door de migratiestappen gehaald (onschadelijk — de
  kolomcontrole is idempotent) en de beveiliging tegen een terugval naar een oudere add-on-versie
  deed niets. Nu op 6.

## 0.13.0 — 2026-08-09

### Nieuw
- **Filteren en zoeken op de pagina Terugkerend**: op ritme, categorie, soort (vast of variabel),
  herkomst (incassant-ID of naam), bedragbereik per maand, en alleen gewijzigde bedragen. Zoeken op
  naam en categorie, sorteren op zes velden op- of aflopend.
- **Het totaal rekent mee met het filter.** "Alleen maandelijks" beantwoordt daarmee direct wat je
  maandabonnementen samen kosten, in plaats van een kortere lijst te geven om zelf op te tellen.
- De keuzelijsten tonen hoeveel posten er per ritme en per categorie zijn.
- Elke post laat nu zien of hij als vaste last of als variabel telt, met uitleg bij het label.

### Note
- Overwogen om de detectie strenger te maken zodat losse aankopen niet als "jaarlijks" opduiken,
  maar op echte gegevens blijkt regelmaat van tussenpozen daar geen bruikbaar signaal voor: Netflix,
  HBO Max en Amazon hebben grillige tussenpozen door gaten in de historie, terwijl drie
  supermarktbezoeken toevallig regelmatig kunnen liggen. Een drempel die de ruis wegfiltert sloopt
  ook zeventien echte incasso's. Het filter *alleen vaste lasten* doet dit werk beter dan een
  heuristiek dat zou kunnen.

### Techniek
- 201 tests. (Eerdere regels in dit changelog noemen te hoge aantallen; zie 0.13.1.)

## 0.12.0 — 2026-08-09

### Nieuw
- **Lastenoverzicht op het dashboard.** De gestapelde grafiek liet zien *hoeveel* vastlag maar niet
  *wat*. Nu drie kerngetallen (vast, variabel, over na vaste lasten), een verhoudingsbalk, de vaste
  posten stuk voor stuk met bedrag per maand en interval, en daarnaast het variabele geld per
  categorie. De maandgrafiek zit nog steeds in het blok, ingeklapt.

### Changed
- **Scherpere definitie van "vast".** Terugkerend is niet hetzelfde als vast: de supermarkt komt ook
  elke week terug. Een kost geldt nu als vast bij een incassomachtiging, of bij een bedrag dat binnen
  15% gelijk blijft (dat vangt creditcard-abonnementen). Op echte gegevens levert dat € 1.402 per
  maand aan verplichtingen op, terwijl tankbeurten, thuisbezorgd en motorkleding terecht aan de
  variabele kant blijven — 26 terugkerende posten die géén vaste last zijn.

### Techniek
- 201 tests.

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
