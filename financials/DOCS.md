# Financials

Je eigen huishoudboekje in Home Assistant. Je downloadt de CSV-export bij je
bank, uploadt die hier, en de add-on maakt er een overzicht van. Alles blijft op
je eigen systeem — er gaat niets naar buiten.

## Welke banken

| Bank | Welke export |
|---|---|
| Rabobank betaal- en spaarrekening | "Download transacties" → CSV (het bestand dat begint met `CSV_A_accounts`) |
| Rabobank creditcard | Creditcard-overzicht → CSV (bestand `RA_CC_…`) |
| ASN Bank | Transactiehistorie → CSV |

Eén Rabobank-bestand mag meerdere rekeningen bevatten; die worden automatisch
uit elkaar gehaald.

## Importeren

1. Ga naar **Importeren**.
2. Laat **Bank / formaat** op *Automatisch herkennen* staan, of kies zelf de
   bank als de herkenning ernaast zit.
3. Sleep het CSV-bestand naar het vak, of klik op *Bestand kiezen*.
4. Je krijgt eerst een **controlescherm**: welk formaat herkend is, om welke
   rekening het gaat, hoeveel regels erin zitten, over welke periode, en de
   eerste vijf regels zoals de app ze gelezen heeft.
5. Klopt het? Klik op **importeren**. Klopt het niet — bijvoorbeeld: alle
   bedragen staan op € 0,00 — kies dan eerst een ander formaat.

Er wordt niets opgeslagen voordat je op importeren klikt.

**Hetzelfde bestand nog eens uploaden kan geen kwaad.** Regels die er al in
staan worden overgeslagen; je ziet vooraf hoeveel er echt nieuw zijn. Handig als
je periodes downloadt die elkaar overlappen.

## Je bestanden blijven bewaard

Elk geüpload bestand blijft op schijf staan, in de map `/data/uploads` van de
add-on. Daardoor kun je:

- **Opnieuw inlezen** — nadat je een categorieregel hebt aangepast, zonder
  opnieuw bij de bank te downloaden.
- **Downloaden** — je krijgt het originele bestand terug.
- **Verwijderen** — in twee smaken:
  - *alleen het bestand*: de transacties blijven gewoon in de app staan;
  - *bestand én transacties*: de hele import wordt ongedaan gemaakt. Je ziet
    eerst om hoeveel transacties het gaat.

Omdat alles in `/data` staat, zit het automatisch in je Home Assistant-back-ups.

## Overboekingen tussen je eigen rekeningen

Als je € 200 van je betaalrekening naar je spaarrekening zet, is dat geen
uitgave en geen inkomen — het is hetzelfde geld dat verhuist. De add-on zoekt
die twee kanten bij elkaar en markeert ze als **interne overboeking**.

- Beide regels blijven gewoon staan bij hun eigen rekening, dus de saldi blijven
  kloppen met je bankafschrift.
- In het huishoudtotaal tellen ze niet mee als inkomsten of uitgaven.
- Zie je *"intern (andere kant ontbreekt)"*, dan staat de tegenkant nog niet in
  de app — meestal omdat je die rekening nog niet geïmporteerd hebt. Zodra dat
  wel zo is, worden ze alsnog aan elkaar gekoppeld.

Hetzelfde geldt voor de **creditcard**: de maandelijkse afschrijving van je
betaalrekening is dezelfde uitgave als de losse aankopen op de kaart. Die twee
worden aan elkaar gekoppeld, zodat je uitgaven niet dubbel geteld worden. De
losse aankopen blijven staan — díe hebben de winkelnaam en de categorie.

Op **Rekeningen** zet je per rekening het soort. Een spaarrekening wordt meestal vanzelf herkend —
er wordt nooit mee gepind of geïncasseerd, en het verkeer gaat vrijwel alleen van en naar je eigen
rekeningen. Klopt het niet, dan zet je het zelf om; jouw keuze wordt daarna nooit meer automatisch
overschreven.

Geld dat naar een spaarrekening gaat telt als **gespaard** in plaats van als uitgave. Staat er nog
geen enkele rekening op *Spaarrekening*, dan laat het overzicht bij Gespaard een streepje zien in
plaats van € 0,00 — want niets ingesteld is iets anders dan niets gespaard.

## Categorieën

Transacties worden automatisch ingedeeld op basis van regels — de add-on begint
met een set Nederlandse winkels en incassanten, en die mag je zelf aanpassen op
**Categorieën & regels**.

Sneller werkt het via **Transacties → Regel maken**: je ziet dan meteen hoeveel
transacties de nieuwe regel raakt, vóórdat je hem opslaat.

### Je eigen keuzes blijven staan

Zet je zelf een categorie op een transactie, dan krijgt die het label **vast**. Vanaf dat moment
laat de app hem met rust:

- *Regels opnieuw toepassen* slaat hem over, en meldt achteraf hoeveel handmatige keuzes met rust
  gelaten zijn.
- Blijkt een transactie later een interne overboeking te zijn — bijvoorbeeld omdat je de tegenrekening
  alsnog importeert — dan blijft jouw categorie gewoon staan. Alleen categorieën die de app zélf had
  geraden worden dan opgeschoond.
- Een nieuwe import verandert nooit iets aan wat je al hebt ingesteld.

Wil je toch alles gelijktrekken met de regels, dan is daar één knop voor: *Ook handmatige keuzes
overschrijven…*. Die vraagt eerst hoeveel van jouw keuzes eraan gaan en doet niets tot je bevestigt.

### Selecteren en in bulk aanpassen

Met het vinkje in de kopregel selecteer je alles op de pagina. Staan er meer resultaten dan op één
pagina passen, dan verschijnt **Alle … selecteren** om de hele filterselectie te pakken. Daarna kun
je in één keer een categorie of een label toekennen.

## Labels — meerdere dimensies naast de categorie

Soms hoort een uitgave bij twee dingen tegelijk: die tankbeurt is **brandstof**, én hij hoort bij de
**vakantie**. Daar zijn labels voor.

Een transactie heeft altijd precies één categorie — dat is de boekhouding, en daardoor blijft de
optelsom kloppen. Daarnaast kan hij zoveel labels dragen als je wilt. De tankbeurt blijft dus gewoon
Brandstof staan, met het label *Vakantie 2019* erbij.

> Waarom niet gewoon twee categorieën? Omdat €60 brandstof tijdens de vakantie voor 100% brandstof
> is én voor 100% vakantie. Tel je hem in twee categorieën volledig mee, dan tellen je categorieën
> samen op tot meer dan je hebt uitgegeven. Halveer je hem, dan zie je te weinig brandstof. Met een
> label klopt allebei.

**Eén transactie labelen:** Transacties → knop **Labels** op de regel. Daar kun je meteen een nieuw
label aanmaken als het nog niet bestaat.

**Een hele reis in één keer:** filter op de periode (Van/Tot), zet eventueel *Richting* op *Af*,
selecteer de regels met de vinkjes en kies het label in de balk bovenaan. Let op dat je vaste lasten
die toevallig in die periode vallen — verzekering, abonnementen — er weer uit vinkt; die horen niet
bij de reis.

**Wat het oplevert:** op de pagina **Labels** klap je een label open en zie je wat het in totaal
gekost heeft, uitgesplitst per categorie. Zo zie je in één oogopslag wat een vakantie of verbouwing
werkelijk gekost heeft, over alle categorieën heen.

Labels veranderen niets aan je inkomsten-, uitgaven- of budgetcijfers. Ze zijn puur een extra manier
om te filteren en op te tellen.

## Budget

Onder **Budget** stel je per categorie een maandbedrag in. Je ziet direct hoeveel er al op staat en
hoeveel er over is. Twee knoppen schelen werk:

- **Vorige maand overnemen** — kopieert alle bedragen van de vorige maand.
- **Voorstel op basis van historie** — rekent de mediaan uit van de laatste zes maanden. Bewust de
  mediaan en niet het gemiddelde: één dure maand mag je boodschappenbudget niet omhoog trekken. Er
  wordt niets opgeslagen tot je op *Alles overnemen* klikt.

Zet **doorschuiven** aan bij categorieën die per maand sterk wisselen (kleding, auto-onderhoud): wat
je overhoudt telt dan op bij de volgende maand.

## Terugkerende betalingen

De pagina **Terugkerend** zoekt abonnementen en vaste lasten op. Bij Rabobank-incasso's gebeurt dat
op het incassant-ID uit je machtiging, dus die groepen kloppen exact. De rest wordt op naam
gegroepeerd en kan er af en toe naast zitten — dat staat erbij in de kolom *Herkomst*.

Alles wordt omgerekend naar een bedrag per maand, zodat een jaarpolis en een maandabonnement
vergelijkbaar zijn. Verandert een bedrag ten opzichte van wat gebruikelijk was, dan krijgt de regel
het label *gewijzigd* — handig om stille prijsverhogingen te zien.

## Sensoren in Home Assistant

De add-on zet een paar waarden als sensor in Home Assistant, zonder dat je iets hoeft in te stellen:

| Sensor | Wat |
|---|---|
| `sensor.financials_saldo_totaal` | Totaal saldo van alle rekeningen |
| `sensor.financials_saldo_<rekening>` | Saldo per rekening |
| `sensor.financials_uitgaven_deze_maand` | Uitgaven in de lopende periode |
| `sensor.financials_inkomsten_deze_maand` | Inkomsten in de lopende periode |
| `sensor.financials_vaste_lasten` | Herkende vaste lasten per maand |
| `sensor.financials_ongecategoriseerd` | Aantal transacties zonder categorie |

Je kunt daar dashboardkaarten en automatiseringen op bouwen — bijvoorbeeld een melding als de
uitgaven deze maand boven een bedrag komen. De waarden worden bijgewerkt na elke import en verder
elk half uur.

## Instellingen

Onder **Maandgrens** kies je waar een maand begint: op de 1e, op je salarisdag,
of op een vaste dag die je zelf kiest. Dit is alleen een weergave-instelling —
je kunt vrij wisselen, er wordt niets opnieuw ingelezen.

## Privacy

- Alle gegevens staan in `/data` binnen de add-on. Er is geen internetverbinding
  nodig en er wordt niets verstuurd.
- In de logboeken van de add-on worden rekeningnummers afgekort tot
  `NL96…1953`.
- De naam van de kaarthouder in de creditcard-export wordt niet opgeslagen.
