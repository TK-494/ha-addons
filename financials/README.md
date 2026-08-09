# Financials — Home Assistant add-on

Self-hosted huishoudboekje. Imports Dutch bank CSV exports, keeps every account
separate, and nets out the money you move between your own accounts so income
and expenses mean what they say.

Developer documentation. The end-user page is [DOCS.md](DOCS.md) (Dutch).

## Supported formats

| Format | Export | Notes |
|---|---|---|
| `rabobank_current` | Rabobank betaal/spaar, "CSV_A_accounts_*" | 26 columns, CP1252, comma decimals. One file may hold several accounts. |
| `rabobank_creditcard` | Rabobank creditcard, "RA_CC_*" | 13 columns. Carries foreign-currency fields. Cardholder name is dropped at parse time. |
| `asn` | ASN Bank transactiehistorie | 20 columns, UTF-8, `DD-MM-YYYY` dates, dot decimals. Header-less exports supported. |

Detection reads the header and *proposes* a format; the user confirms or
overrides it in the UI before anything is written. An explicit choice always
wins, and a mismatch is a hard 422 naming the missing columns — never a silent
fallback.

## Architecture

```
backend/app/
  parsers/     one module per layout → ParsedRow, plus the registry
  services/    importer · categorize (rules engine) · transfers · periods
  routers/     imports · accounts · transactions · categories+rules · settings
  models.py    accounts, transactions, categories, rules, import_batches, budgets
  security.py  headers, path containment, log redaction, CSV-export escaping
frontend/src/  React 18 + Vite + Tailwind, Dutch UI, HashRouter for Ingress
tests/         pytest, synthetic fixtures only
```

One container: FastAPI serves the API under `/api` and the built SPA at the
root. No nginx, no second service, no CORS middleware — same origin either way.

### Decisions worth knowing

**Money is integer cents everywhere.** Transfer matching compares amounts for
exact equality, and floats make that unreliable after enough summing.

**Both legs of a transfer are kept.** Marking them internal excludes them from
household income/expense while the per-account balance still reconciles against
the bank's own `Saldo na trn`. Deleting a leg would break that.

**Matching re-runs over the whole table after every import.** An IBAN only
becomes "yours" once its own CSV is imported, so earlier transfers to it pair up
retroactively.

**Categorisation rules are database rows.** Editing one is a form submission,
not a rebuild. The seed set is inserted once on first boot and is yours to
change afterwards.

**No pandas.** Stdlib `csv` streams, quotes correctly and has no opinion about
`NaN`; the dependency was 50 MB for reading 10k rows.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt pytest httpx
.venv/bin/python -m pytest                 # 64 tests, synthetic fixtures
```

Run the backend against a scratch database:

```bash
DATA_DIR=/tmp/fin DATABASE_URL=sqlite:////tmp/fin/financials.db \
  .venv/bin/uvicorn app.main:app --app-dir backend --reload
```

Frontend dev server (proxies `/api` to port 8000):

```bash
cd frontend && npm install && npm run dev
```

## Privacy and repository hygiene

- No IBAN, name, card number, CSV export or database is committed. Test
  fixtures are synthetic — invented IBANs, invented merchants.
- `scripts/check-no-personal-data.sh` greps the tree for IBAN patterns and
  bank-export filenames; wire it up as a pre-commit hook.
- Account identifiers are stored in the SQLite database inside HA's `/data`
  only. Logs mask IBANs to `NL96…1953`.
- The cardholder name in `Creditcard Regel1` is read to detect the column and
  then discarded.

## Known limitations

- `frontend/package-lock.json` is absent, so the Docker build uses
  `npm install`. Generate and commit a lock file for reproducible builds.
- Non-root operation depends on `su-exec` and on `/data` being chown-able. When
  it is not, the app logs a warning and continues as root rather than
  crash-looping.
