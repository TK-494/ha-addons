# Finance Dashboard

Persoonlijk financieel dashboard:

- 📄 CSV import van **Rabobank én ASN Bank** — formaat wordt automatisch herkend (alle bekende Rabobank-exporten: Datum/Bedrag, Valutadatum, en de oudere "Af Bij")
- 🛒 Automatische categorisatie (Nederlandse winkels, banken, verzekeraars, BNPL)
- 🔁 **Overboekingen tussen eigen rekeningen** worden automatisch herkend en uit je inkomsten/uitgaven gefilterd
- 🎯 Budget per categorie met live voortgang
- 📈 VGN CAO loongroei projectie (FWG schalen per 01-12-2024, projectie vanaf het huidige jaar)
- 📊 Maand-overzicht, trends, saldoverloop
- 🗂️ **Categorieën-tab** — uitgaven per categorie over 3, 6, 12 of 24 maanden, met drill-down per categorie
- 🗓️ **Salarisdag instelbaar** — laat je financiële maand op je salarisdag beginnen i.p.v. de 1e
- ✅ **Bulk categoriseren** — selecteer meerdere transacties (of alles wat aan een filter voldoet) en zet ze in één klik in de juiste categorie

Alle data blijft lokaal opgeslagen in `/data/finance.db`. Niets gaat naar externe servers.

## Gebruik

1. Ga naar **Importeren** en upload je Rabobank CSV
2. Bekijk je **Dashboard** voor het maand-overzicht (stel je salarisdag in via "Maand start" rechtsboven)
3. Stel je **Budget** per categorie in
4. Categoriseer in **Transacties** — los of in bulk via de checkboxen
5. Vul je FWG schaal en periodiek in onder **CAO Groei** voor je salarisprojectie
