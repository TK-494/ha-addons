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

### Een suggestie na het handmatig categoriseren

Zet je zelf een categorie op een transactie, dan kijkt de app of dat vaker voorkomt. Staan er nog
meer van dezelfde tegenpartij zonder categorie, dan verschijnt bovenaan:

> Er staan nog **78** transacties van `WOONSTICHTING TRIADA` zonder categorie. Zal ik die ook
> **Wonen** maken?

Met daarbij een knop per bestaande regel voor die categorie. Klik je die aan, dan wordt het patroon
aan die regel toegevoegd — er komt géén nieuwe regel bij. Dat is precies het verschil: zonder dit
groeit je regellijst met elke correctie, en krijg je uiteindelijk drie losse McDonald's-regels.

Je eigen regels staan bovenaan, daarna regels die al meerdere patronen verzamelen. Past het nergens
bij, dan is *Liever een nieuwe regel* er nog.

### Een regel met meerdere patronen

Een regel bevat één patroon per regel tekst. Alle patronen delen dezelfde categorie en prioriteit,
dus varianten van dezelfde winkel horen bij elkaar:

```
McDonald
Mc Donald's
MCDONALDS
```

In de lijst zie je het eerste patroon met daarachter hoeveel er nog meer zijn. Klik erop om ze alle
te bewerken.

### Een regel aanpassen

Klik op de waarde van een regel, of op **Bewerken**. Je kunt alles wijzigen: de categorie, waar hij
naar kijkt, of hij *bevat* / *is exact* / *begint met* gebruikt, de waarde zelf, een bedragbereik, en
of hij actief is.

Terwijl je typt telt de app mee: hoeveel transacties de regel raakt, hoeveel er al in die categorie
staan, hoeveel je handmatig hebt vastgezet (die blijven ongewijzigd) en hoeveel er dus echt zouden
verhuizen — met een paar voorbeelden erbij. Zo zie je vóór het opslaan of je een regel te breed
maakt.

**Prioriteit** pas je direct in de tabel aan, zonder het scherm te openen. Een lager getal wint: bij
twee regels die dezelfde transactie vangen, telt die met het laagste nummer. De standaardregels
zitten op 10–270, de tweede set op 500 en hoger, en regels die je zelf maakt op 1 — die winnen dus
standaard van alles.

Na een wijziging klik je op **Regels opnieuw toepassen** om bestaande transacties bij te werken. Wat
je handmatig hebt ingesteld blijft daarbij staan.

### Regels exporteren en importeren

**Regels exporteren** geeft een JSON-bestand met álle regels: naar welke categorie ze wijzen, hoe ze
matchen, met welke prioriteit, **waar ze vandaan komen** (standaard / handmatig / gemaakt vanaf een
transactie / geïmporteerd) en hoeveel transacties elke regel nu daadwerkelijk vangt. Dat laatste
maakt het bestand leesbaar in plaats van een dump — je ziet meteen welke regels werk doen en welke
niets.

Handig als je aanpassingen wilt laten doorvoeren: stuur het bestand op, laat het aanpassen, en lees
het met **Importeren** weer in. Je krijgt eerst te zien hoeveel regels nieuw zijn en hoeveel al
bestaan; er wordt niets geschreven tot je bevestigt. Bestaande regels en de categorie van je
transacties blijven ongemoeid.

Categorieën staan op naam in het bestand, niet op nummer, dus het overleeft een herinstallatie.

### Botsende regels

Boven aan de pagina verschijnt een waarschuwing zodra regels elkaar in de weg zitten:

- **dubbel** — hetzelfde patroon wijst naar twee categorieën; alleen die met de laagste prioriteit
  vuurt ooit.
- **overschaduwd** — een bredere regel vangt hem altijd eerder af. `verzekering` vangt bijvoorbeeld
  ook `eno zorgverzekering`, waardoor die tweede nooit aan bod komt.

Op te lossen door de prioriteit van de specifieke regel te verlagen (lager getal wint), of de brede
regel aan te scherpen.

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

## Wat is er nog vrij deze maand

Bovenaan het overzicht staat een balk met vier dingen:

- **Vrij te besteden** — wat er binnenkwam, min wat je al uitgaf, min de incasso's die vóór het einde
  van de periode nog afgeschreven worden. Die laatste aftrek is het punt: op de 3e is de huur nog
  niet afgeschreven, en zonder die correctie lijkt het bedrag royaal precies wanneer dat niet zo is.
  Alleen betalingen met een incassomachtiging tellen mee — boodschappen herhalen zich ook, maar zijn
  een keuze.
- **Volgend loon** — over hoeveel dagen. Berekend uit je eigen betaalgeschiedenis, met weekends én
  Nederlandse feestdagen erin (25 mei 2026 was Pinkstermaandag, vandaar dat je toen op de 22e betaald
  kreeg). Wisselt de betaaldag in een bepaalde maand te veel — december meestal — dan staat erbij dat
  het een schatting is.
- **Inkomsten**, gesplitst in vast en variabel.
- **Gegevens bijgewerkt tot** — de datum van de nieuwste transactie. Loopt een rekening achter, dan
  staat eronder welke en hoeveel dagen. Zonder dat is "je hebt nog € 62 over" een misleidende
  uitspraak als je laatste import drie weken oud is.

Klik op *Hoe is dit berekend?* voor de som en de lijst met verwachte incasso's.

## Vaste en variabele lasten

Op het overzicht staat een blok dat je uitgaven in tweeën deelt, met bovenaan drie getallen: wat er
deze periode vastlag, wat variabel was, en wat je van je inkomen overhoudt als de vaste lasten eraf
zijn. De balk eronder laat in één oogopslag zien hoeveel van elke euro vastligt.

Daaronder staat het belangrijkste: **welke** posten dat zijn. Huur, lening, zorgverzekering, energie,
telefoon — met bedrag per maand, hoe vaak ze komen, en een melding als het bedrag veranderd is. Naast
die lijst zie je waar het variabele geld heen ging, per categorie.

### Wanneer telt iets als vast?

Niet elke terugkerende betaling is een vaste last. De supermarkt komt ook elke week terug, maar die
kun je overslaan. Een kost telt als vast wanneer:

- er een **incassomachtiging** op zit — dan wordt het hoe dan ook afgeschreven, ook als het bedrag
  schommelt zoals bij een verzekeringspremie of een aflossing; of
- het **elke keer hetzelfde bedrag** is (binnen 15%), wat abonnementen op je creditcard vangt zoals
  YouTube Premium.

Alles wat wel terugkeert maar wisselt en niet geïncasseerd wordt — tankbeurten, thuisbezorgd,
motorkleding — staat aan de variabele kant. Onderaan het blok zie je hoeveel posten dat zijn.

## Salaris

Het tabblad **Salaris** verzamelt al je loonbetalingen op één plek, zodat je ze niet hoeft op te
zoeken tussen duizenden transacties. Je ziet per betaling het bedrag, en zodra je hem verdeeld hebt
ook hoeveel daarvan vast was en hoeveel variabel.

Bovenaan staat het gemiddelde over de laatste twaalf betalingen, uitgesplitst in vast en variabel,
plus hoeveel betalingen je al verdeeld hebt. De grafiek toont de opbouw per maand — daar zie je in
één oogopslag de maand met vakantiegeld eruit springen.

### Sjabloon

Zodra je één loonbetaling verdeeld hebt, wordt die verdeling het sjabloon voor de rest. Klik op
**Sjabloon** bij een betaling en de vaste delen worden overgenomen; het verschil komt automatisch op
het variabele deel terecht. Dat is precies goed, want je basissalaris is elke maand hetzelfde en de
vergoeding is wat wisselt.

Met **Sjabloon op alle … toepassen** doe je in één keer alle betalingen die nog niet verdeeld zijn.

Zijn de vaste delen samen groter dan een bepaalde betaling — bijvoorbeeld een maand met minder
uren — dan weigert de app dat en moet je die maand handmatig verdelen. Een verdeling die niet klopt
is erger dan geen verdeling.

Een nog niet verdeelde betaling telt volledig als vast inkomen. Dat is wat er bekend is, geen
bewering dat er geen vergoeding in zat.

## Vast en variabel inkomen

Je loonstrook is één bankregel, maar bestaat uit meerdere delen: basissalaris plus reiskosten- en
thuiswerkvergoeding. Die vergoedingen krijg je niet elke maand hetzelfde, dus het is nuttig ze apart
te houden van waar je echt op kunt rekenen.

1. Maak categorieën aan voor de vergoedingen (bijvoorbeeld *Reiskostenvergoeding*), vink daarbij
   **Dit is een inkomstencategorie** én **Variabel inkomen** aan.
2. Ga naar de loonbetaling in **Transacties** en klik op **Verdelen**.
3. Vul de delen in. De app rekent mee en accepteert pas als het tot op de cent klopt met het
   overgemaakte bedrag — een verdeling die niet sluit zou elk totaal eronder stilletjes fout maken.

Daarna zie je in het overzicht bij Inkomsten hoeveel vast en hoeveel variabel was, en verschijnen de
delen apart in de inkomstentaart.

Verdelen werkt ook voor uitgaven: € 120 bij de bouwmarkt als € 80 tuin en € 40 huishouden.

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

Onder **Maandgrens** kies je waar een maand begint: op de 1e, op je salarisdag, of op een vaste dag
die je zelf kiest. Dit is alleen een weergave-instelling — je kunt vrij wisselen, er wordt niets
opnieuw ingelezen.

### Vaste en variabele lasten

Op het overzicht staat een blok dat je uitgaven in tweeën deelt, met bovenaan drie getallen: wat er
deze periode vastlag, wat variabel was, en wat je van je inkomen overhoudt als de vaste lasten eraf
zijn. De balk eronder laat in één oogopslag zien hoeveel van elke euro vastligt.

Daaronder staat het belangrijkste: **welke** posten dat zijn. Huur, lening, zorgverzekering, energie,
telefoon — met bedrag per maand, hoe vaak ze komen, en een melding als het bedrag veranderd is. Naast
die lijst zie je waar het variabele geld heen ging, per categorie.

### Wanneer telt iets als vast?

Niet elke terugkerende betaling is een vaste last. De supermarkt komt ook elke week terug, maar die
kun je overslaan. Een kost telt als vast wanneer:

- er een **incassomachtiging** op zit — dan wordt het hoe dan ook afgeschreven, ook als het bedrag
  schommelt zoals bij een verzekeringspremie of een aflossing; of
- het **elke keer hetzelfde bedrag** is (binnen 15%), wat abonnementen op je creditcard vangt zoals
  YouTube Premium.

Alles wat wel terugkeert maar wisselt en niet geïncasseerd wordt — tankbeurten, thuisbezorgd,
motorkleding — staat aan de variabele kant. Onderaan het blok zie je hoeveel posten dat zijn.

## Salarisdag: de échte datum, niet een vaste dag

Een werkgever betaalt op een vaste datum, maar schuift die als hij in het weekend valt of rond de
feestdagen. Bij een vaste grens op de 25e belandt het salaris in al die maanden in de *vorige*
periode — en dat is vaker dan je denkt. In deze gegevens gebeurde dat in 12 van de 26 maanden.

Kies je **Salarisdag**, dan begint elke maand op de dag dat je salaris werkelijk geboekt is.

Daarvoor moet de app weten welke betaling je salaris is. Dat gaat op **naam van de betaler**, niet op
bedrag: een drempel als "boven €1.000" pikt ook leningen en teruggaves op, en die komen op
willekeurige dagen binnen. De app doet zelf een voorstel op basis van terugkerende grote inkomsten —
meestal is één klik genoeg.

Onder **Grenzen per maand** zie je precies wat elke maand geworden is en waarom: *salarisdatum*,
*vaste dag* (geen salaris gevonden die maand) of *handmatig*. Klopt een maand niet, dan pas je de
datum daar aan; die correctie wint altijd. Met *Herstel* laat je hem weer los.

## Privacy

- Alle gegevens staan in `/data` binnen de add-on. Er is geen internetverbinding
  nodig en er wordt niets verstuurd.
- In de logboeken van de add-on worden rekeningnummers afgekort tot
  `NL96…1953`.
- De naam van de kaarthouder in de creditcard-export wordt niet opgeslagen.
