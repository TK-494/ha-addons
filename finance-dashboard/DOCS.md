# Finance Dashboard — Documentation

## How it works

Single FastAPI container that serves both the React frontend (built as static files) and the JSON API. SQLite database persisted in `/data/finance.db` (HA-managed volume, included in HA backups).

## Configuration

This add-on currently has no configurable options in `config.yaml` — defaults work out of the box. Per-user preferences (salary day, known own accounts, CAO scale, etc.) are stored in the SQLite DB and edited from the UI.

## Importing a CSV

Both **Rabobank** and **ASN Bank** are supported. The add-on peeks at the CSV header and dispatches to the right parser — you just drop the file on **Importeren** and the result banner tells you which bank was detected.

### Rabobank
1. Log in to Mijn Rabobank → Overzicht → Downloaden → **CSV**
2. Three Rabobank export layouts are recognised: current (`Datum` + `Bedrag` + `Omschrijving-1/2/3`), `Valutadatum` variant, and the legacy `Bedrag (EUR)` / `Af Bij` format

### ASN Bank
1. Log in to Mijn ASN → Afschriften / Transacties downloaden → **CSV**
2. The export uses `Datum`, `Je rekening`, `Van / naar`, `Naam`, `Bedrag bij / af` (signed, comma decimal), `Omschrijving`, `Betalingskenmerk` — these are mapped to the same internal record as Rabobank
3. ASN ships its own `Categorie` column, but the add-on ignores it and runs its own keyword-based categorization so the buckets stay consistent across banks

### Shared behavior
- Duplicate transactions are detected via SHA-256 hash of `(date, amount, description, counter_iban)`, so re-importing the same period (or overlapping CSVs from different banks) is safe — duplicates are reported as `skipped`
- The encoding is auto-detected: UTF-8 with BOM is tried first, then Windows-1252 (cp1252) which older exports use
- The upload response includes the detected `bank` (`"rabobank"` or `"asn"`) and a `transfers_flagged_in_batch` count so you can confirm what happened

## Transfers between your own accounts

The add-on auto-detects transfers between accounts you own so they don't pollute your income/expense totals.

**How it works:** every IBAN that appears as the *own* side of an imported CSV is remembered as one of your accounts. Any transaction whose counterparty IBAN is in that set is flagged as a transfer (badge `Overboeking` in the transactions list) and excluded from dashboard stats, trends, the category pie, and the balance line.

The detection is **bank-agnostic** — it keys on IBAN, not bank. As soon as you've imported a Rabobank statement *and* an ASN statement once each, transfers in both directions (Rabobank → ASN and ASN → Rabobank) start getting flagged on every subsequent import. A retroactive pass also re-flags historical rows: if account A was imported first and account B later, the A→B moves that were already in the database get flagged the moment account B arrives.

**Manual override** via the API if needed:
- `GET  /api/transactions/own-accounts` — list known IBANs
- `POST /api/transactions/own-accounts?iban=…` — add one manually
- `DELETE /api/transactions/own-accounts?iban=…` — remove one

## Salary-aligned month (Maand start)

If your salary arrives on, say, the 24th of every month, set **Maand start = 24** in the input next to the month/year pickers on the Dashboard. From then on:

- "Mei 2025" with `start = 24` means **24 May 2025 → 23 Jun 2025** (labeled by the start month)
- All dashboard endpoints — stats, trend, category pie — use this window
- The day is clamped per-month, so 31 in a 30-day month becomes 30
- The setting is persisted in `user_settings.month_start_day` (default: 1)

Budgets still use calendar months (Jan 1–31, etc.) — that's intentional.

## Categorizing transactions

**On import**, the parser auto-categorizes rows by keyword matching across description and counterparty. The full Dutch ruleset lives in `app/parsers/rabobank.py::CATEGORY_RULES`. Specific buckets (Afbetaling, Verzekeringen, Leningen) are evaluated before generic ones so a Klarna line lands in **Afbetaling**, not Online Shopping.

**Default categories** ship out of the box: Boodschappen, Inkomen, Wonen, Energie, Zorgverzekering, Telefoon/Internet, Transport, Restaurant & Café, Sport & Fitness, Kleding, Online Shopping, Zorg & Apotheek, Abonnementen, Bank & Verzekering, **Verzekeringen**, **Leningen**, **Afbetaling**, Overig. New defaults are added automatically on update — existing categories you've edited are left alone.

**Bulk categorize** in the Transactions page:

1. Tick the checkbox on one or more rows (or the header checkbox to toggle all visible rows)
2. A blue action bar appears with the selection count, a category dropdown, and **Toepassen op selectie**
3. With a search or category filter active, also use **Selecteer alles wat aan filter voldoet** — this calls `GET /api/transactions/ids` to pull the full matching ID set (not just the 300 visible rows), so you can recategorize an entire filtered slice in one click
4. Pick a category (or "geen categorie" to clear it) and apply

Manual single-row re-categorization is still available via the dropdown in each row.

## VGN CAO salary projection

The add-on ships with the **VGN CAO Gehandicaptenzorg salarisschalen per 01-12-2024** for FWG 5 t/m 80, baked in from the official salaristabellen PDF.

1. Open **CAO Groei**
2. Pick your FWG schaal and huidige periodiek — the dropdown only shows trede waardes die voor jouw schaal bestaan (FG 35 start bij trede 1, FG 40/45 bij trede 2, etc.)
3. Click **Instellingen opslaan**
4. The projection chart starts at **the current year**, projects 10 years forward (+1 periodiek per year, capped at the maximum trede for your scale), and shows monthly gross, ~72% net estimate, and annual gross including 8% vakantiegeld

**Net estimate is a flat 72% heuristic**, not a real Dutch tax calculation — use as a ballpark only.

To override the seeded values: **CAO Groei → ✏️ Schalen bewerken**, edit any periodiek, save. Edits are persisted to the SQLite DB.

When a new CAO is signed and we ship updated default values, an existing install will be wiped & re-seeded automatically (tracked via `cao_seed_version` in `user_settings`). Your `cao_scale` / `cao_step` selection is preserved.

## Data backup

Your SQLite DB lives in the add-on's `/data` directory. It's included in Home Assistant's full backups automatically.
