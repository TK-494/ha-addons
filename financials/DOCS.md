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

Op **Rekeningen** zet je per rekening het soort. Zet een spaarrekening op
*Spaarrekening*: geld dat daarheen gaat telt dan als gespaard.

## Categorieën

Transacties worden automatisch ingedeeld op basis van regels — de add-on begint
met een set Nederlandse winkels en incassanten, en die mag je zelf aanpassen op
**Categorieën & regels**.

Sneller werkt het via **Transacties → Regel maken**: je ziet dan meteen hoeveel
transacties de nieuwe regel raakt, vóórdat je hem opslaat. Categorieën die je
zelf met de hand hebt gezet worden nooit door een regel overschreven.

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
