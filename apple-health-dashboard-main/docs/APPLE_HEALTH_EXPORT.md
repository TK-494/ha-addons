# Apple Health export maken

Het dashboard werkt op basis van een export uit de Apple Health-app op je
iPhone. Deze handleiding legt uit hoe je die export maakt en uploadt.

## Waarschuwing

Een Apple Health-export bevat **persoonlijke en gevoelige gezondheidsdata**.
Deel deze export niet met anderen en commit hem **nooit** naar Git of een andere
openbare plek. Bewaar hem alleen zo lang als nodig.

## Export maken op je iPhone

1. Open de **Gezondheid**-app.
2. Tik rechtsboven op je **profiel of foto**.
3. Scroll naar beneden.
4. Kies **Exporteer alle gezondheidsgegevens**.
5. Bevestig de export.
6. Wacht tot iOS het zipbestand heeft gemaakt. Bij veel data kan dit even duren.
7. Deel of bewaar het bestand op een veilige manier, bijvoorbeeld via de
   **Bestanden**-app, **AirDrop** of een andere vertrouwde methode.

### Bestandsnaam

Het geëxporteerde bestand heet meestal **`export.zip`**.

## De export uploaden

1. Open de uploadpagina van de app: `/upload`
   (bijvoorbeeld `http://127.0.0.1:8095/upload`).
2. Kies je **`export.zip`**.
3. Start de upload.
4. Wacht tot de parser klaar is met verwerken.
5. Ga terug naar het dashboard; de grafieken vullen zich met je gegevens.

## Wat je niet moet uploaden

Upload alleen de complete `export.zip`. Dus niet:

- een los `.xml`-bestand;
- een uitgepakte map;
- screenshots;
- andere zipbestanden dan de Apple Health-export.

## Privacy

- Bewaar `export.zip` alleen **tijdelijk**.
- Verwijder lokale kopieën na de import als je ze niet meer nodig hebt.
- De ruwe export hoort **niet** in GitHub of een andere openbare opslag.

## Problemen oplossen

**De export duurt lang.**
Bij veel gezondheidsgegevens kan iOS er even over doen om het zipbestand te
maken. Houd de Gezondheid-app op de voorgrond en wacht tot het klaar is.

**Het bestand is groot.**
Dat is normaal bij een lange historie. Gebruik een snelle, betrouwbare
verbinding en wacht geduldig tot de upload en de verwerking klaar zijn.

**De upload mislukt.**
Controleer of je echt de `export.zip` koos (geen los `.xml` of een map), of het
bestand volledig op je computer staat, en probeer het opnieuw.

**Het dashboard blijft leeg.**
De import is mogelijk nog bezig of er ging iets mis. Wacht even, ververs het
dashboard en controleer de importstatus via `/api/import/status`.
