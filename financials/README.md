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

**Labels are a second dimension, not a second category.** A transaction has
exactly one category, so category totals remain a partition of the spend and
cannot double-count; labels are an orthogonal many-to-many for cross-cutting
questions ("what did that trip cost across fuel, hotels and restaurants").
Splitting the amount across two categories would understate each part; counting
it twice would overstate the total. Neither is acceptable, so neither is
offered.

**Categorisation rules are database rows.** Editing one is a form submission,
not a rebuild. The seed set is inserted once on first boot and is yours to
change afterwards.

**No pandas.** Stdlib `csv` streams, quotes correctly and has no opinion about
`NaN`; the dependency was 50 MB for reading 10k rows.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt pytest httpx
.venv/bin/python -m pytest                 # 201 tests, synthetic fixtures
./scripts/audit.sh                         # dependency advisories
./scripts/check-no-personal-data.sh        # refuses IBANs, exports, databases
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

## Security posture

Verified by probing, not by inspection — the notes below say what was actually
attempted.

| Concern | Where | Verified |
|---|---|---|
| Path traversal | `security.contained_path`, used by the SPA fallback and every upload read | 5 payload shapes (`../`, `..%2F`, `....//`, nested, double-encoded) all served the SPA shell |
| Upload abuse | `services/importer.store_upload` | 33 MB refused with 413 and nothing left on disk; non-CSV extension and empty file refused; `../../evil.csv` never escaped `/data` |
| Response-header injection | `FileResponse(filename=...)` with the original name | crafted `"\r\nX-Injected:` name came back percent-encoded, no header appeared |
| SQL injection | SQLAlchemy throughout | no string-built SQL; the only f-string SQL is `_add_column_if_missing`, whose inputs are literals in this file |
| Resource exhaustion | every list and bulk endpoint | page size, bulk ids, tag ids, split parts and rule imports all bounded and 422 past the limit |
| Formula injection | `security.csv_safe` on export | `=HYPERLINK(...)` in a merchant name comes out prefixed with `'`. Amount cells are not escaped: they are generated from an integer and can only ever match `-?\d+,\d\d`, and quoting them would break numeric parsing |
| PII in logs | `RedactingFormatter` | IBANs masked to `NL96…1953` |
| Schema exposure | `docs_url`/`openapi_url` disabled | `/openapi.json`, `/docs`, `/redoc` return the SPA shell, no schema |
| Dependency CVEs | `scripts/audit.sh` | clean as of 2026-08-09; run before every release |

Deliberate choices worth knowing:

- **`frame-ancestors *`** is required — Home Assistant serves add-on panels in
  an iframe, so a stricter value breaks Ingress. `X-Frame-Options` is absent
  for the same reason.
- **No CSRF tokens.** Authentication is HA's Ingress layer and the URL carries
  a per-session token; JSON endpoints are preflighted and blocked cross-origin
  by the absence of CORS. The multipart upload endpoint is a simple request
  and would be forgeable by anyone who already knows the Ingress URL — which
  is the same thing as already having access.
- **`%` and `_` in a search box act as SQL wildcards.** The value is bound as a
  parameter, so this is a quirk rather than an injection.

## Known limitations

- `frontend/package-lock.json` is absent, so the Docker build uses
  `npm install`. Generate and commit a lock file for reproducible builds.
- Non-root operation depends on `su-exec` and on `/data` being chown-able. When
  it is not, the app logs a warning and continues as root rather than
  crash-looping.
- The Docker image and the React bundle have never been built on the
  development machine (no Docker, no Node); they are exercised for the first
  time by Home Assistant's own build.
