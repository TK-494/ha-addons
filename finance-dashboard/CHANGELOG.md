# Changelog

All notable changes to the Finance Dashboard add-on. Newest version on top. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## 1.0.9 — 2026-05-17

### Added
- New category **Vakantie** (✈️) — keywords voor booking.com, airbnb, KLM, Transavia, Ryanair, TUI, Sunweb, Corendon, Schiphol, hotels en campings.
- New sidebar tab **Categorieën** — uitgaven per categorie over 3, 6, 12 of 24 maanden:
  - Stacked-bar grafiek met de top 8 categorieën per maand
  - Overzichtstabel met totaal, gemiddelde per maand, afgelopen maand, en aantal actieve maanden — klik op een rij om een verloop-grafiek van die categorie te openen
  - "Transacties →" link gaat naar de Transacties-pagina, vooraf gefilterd op die categorie
- De Transacties-pagina onthoudt nu zoek- en categoriefilters in de URL, dus deep-links uit de Categorieën-tab werken en de browser-back-knop herstelt de juiste view.

## 1.0.8 — 2026-05-17

### Fixed
- ASN-uploads werden niet herkend en stilletjes als 0 transacties geïmporteerd. ASN-exports bevatten meestal **geen kopregel**, dus de detectie kon de eerste regel niet matchen op kolomnamen. De parser herkent nu zowel ASN-bestanden mét als zonder kopregel (gebaseerd op 20 velden + IBAN in de tweede kolom), en accepteert zowel komma- als puntkomma-separator.

## 1.0.7 — 2026-05-17

### Added
- **ASN Bank CSV support.** Drop an ASN export on the Importeren-pagina and it just works — het formaat (`Datum`, `Je rekening`, `Van / naar`, `Naam`, `Bedrag bij / af`, `Omschrijving`) wordt automatisch herkend naast de bestaande Rabobank-layouts.
- The upload result banner now shows the detected bank (Rabobank/ASN) and, when applicable, the count of inter-account transfers flagged in this batch.
- **Cross-bank transfer detection works out of the box.** Once you've imported one statement from each account (regardless of bank), any subsequent transfer between them is flagged with the existing `Overboeking` badge and excluded from income/expense totals.

### Changed
- The parser ASN ignores ASN's own `Categorie` column intentionally — the add-on's keyword-based categorization is used so buckets stay consistent across banks.

## 1.0.6 — 2026-05-17

### Added
- Three extra default categories: **Verzekeringen**, **Leningen**, **Afbetaling**. New rules match before the generic ones, so e.g. Klarna lands in Afbetaling instead of Online Shopping.
- **Bulk categoriseren** on the Transactions page — row checkboxes, a header "select visible" checkbox, and a sticky action bar to apply a category to the whole selection in one click.
- When a search or filter is active, an extra **Selecteer alles wat aan filter voldoet** button selects every transaction matching the filter (not just the 300 visible rows).
- **Maand start** input on the Dashboard — set the day your salary lands and every month-view (stats, trend, category pie) uses that as the start of the financial month. With `start = 24`, "Mei 2025" means 24 May → 23 Jun.

### Changed
- Existing installs pick up the new default categories automatically on update; your own edits to existing categories' colours/icons/keywords are preserved.

## 1.0.5 — 2026-05-17

### Added
- **Detection of transfers between your own accounts.** Every IBAN that appears as your own account in an imported CSV is remembered; transactions whose counterparty IBAN matches one of those is shown with an "Overboeking" badge and excluded from income/expense totals, trends, and the category pie.
- Backfill: when you later import a second account, A→B transfers already in the database get re-flagged automatically.
- Manual control via `GET/POST/DELETE /api/transactions/own-accounts` (API only — no UI yet).

### Changed
- **CAO Gehandicaptenzorg salarisschalen vervangen** door de officiële tabel **per 01-12-2024** (FWG 5 t/m 80), met de juiste tredebereiken per schaal (FG 35 vanaf trede 1, FG 40/45 vanaf trede 2, enz.).
- Loongroei-projectie start nu vanaf het **huidige jaar** in plaats van hard-coded 2024, en het periodiek-menu toont alleen waardes die voor jouw schaal bestaan.
- Existing installs are migrated automatically — the old approximated scale values are wiped and replaced on the next boot.

## 1.0.4 — 2026-05-17

### Fixed
- CSV upload succeeded but imported 0 rijen op moderne Rabobank exports. The current Rabobank layout (`Datum`, signed `Bedrag`, `Tegenrekening IBAN/BBAN`, `Omschrijving-1/2/3`) is now recognised alongside the older `Valutadatum` and legacy `Bedrag (EUR)` / `Af Bij` formats.
- The three `Omschrijving-*` columns are joined into one description so auto-categorization keywords match.

## 1.0.3 — 2026-05-17

### Fixed
- CSV upload crashed met `UNIQUE constraint failed: transactions.import_hash` zodra een bestand twee identieke rijen bevatte. Duplicaten binnen één upload worden nu gedetecteerd en overgeslagen (in plaats van de hele import te laten omvallen).
- Filler-rijen (bedrag 0 zonder omschrijving of tegenpartij) worden niet meer geïmporteerd.

## 1.0.2 — 2026-05-17

### Fixed
- Upload van oudere Rabobank-exports faalde met `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xeb` (de Nederlandse `ë`). De parser probeert nu eerst UTF-8 (met BOM) en valt terug op Windows-1252 (cp1252), wat oudere exports gebruiken.

## 1.0.1 — 2026-05-17

### Fixed
- Add-on crashte direct na de start met `sqlalchemy.exc.OperationalError: unable to open database file`. De parent-directory van de SQLite database wordt nu defensief aangemaakt voordat SQLAlchemy de connectie opent, en `run.sh` controleert bij de start of `/data` schrijfbaar is en geeft een duidelijke foutmelding als dat niet zo is.

## 1.0.0 — 2026-05-16

### Added
- Eerste release.
- Rabobank CSV import met automatische categorisatie (Nederlandse winkels, ov, energie, telecom, zorg, abonnementen).
- Budget per categorie met live voortgang.
- VGN CAO loongroei-projectie (FWG schalen).
- Dashboard met maand-overzicht, 6-maands trend, uitgaven per categorie, en saldoverloop.
- Volledig lokaal — SQLite database in `/data/finance.db`, geen externe calls.
