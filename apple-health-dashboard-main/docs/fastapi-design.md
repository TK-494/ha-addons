# fastapi-design.md

Ontwerp van het lokale FastAPI-dashboard voor het Health Dashboard.
**Scope:** een lokaal werkend dashboard. Beveiliging voor breder gebruik (eigen reverse proxy, TLS, eigen toegangsbeveiliging) valt buiten dit document.

## Doelen

- Eén proces, één Python-venv, één `uvicorn`-commando om dev te draaien.
- JSON-files zijn de enige datastore (geen SQLite, geen DB).
- Frontend = vanilla HTML + JS + Chart.js. Geen build-step, geen TypeScript, geen React.
- Bestand-watcher voor live-reload tijdens dev (`uvicorn --reload`), niet voor data-refresh (data wordt na parser-run handmatig herladen via service-restart of `/api/reload`).

---

## Project-layout

### Tijdens dev (lokaal)

```
<PROJECT_DIR>/
├── README.md
├── parser/
│   └── parse_health.py            # parser
├── docs/
│   ├── data-schema.md
│   ├── dashboard-spec.md
│   └── fastapi-design.md          # dit document
└── app/
    ├── main.py                    # FastAPI app + endpoints
    ├── data.py                    # JSON-loader + cache + helpers
    ├── analytics.py               # rolling means, deltas, aggregations
    ├── requirements.txt           # fastapi, uvicorn[standard] — niets meer
    └── static/
        ├── index.html
        ├── app.js
        ├── styles.css
        └── vendor/
            └── chart.umd.min.js   # vendored, geen CDN (zie §Static)
```

Het datapad ligt bij voorkeur buiten de projectmap en buiten de webroot.
Het pad wordt geconfigureerd via env `HEALTH_DATA_DIR`, default `./data/parsed`.

---

## Dependencies

```
fastapi
uvicorn[standard]
```

Niets meer. Geen `pandas`, geen `numpy` — alle aggregaties met stdlib (lijsten en `statistics`). De dataset is klein (2028 dagen, ~1MB JSON); dat is geen issue.

---

## Caching-strategie

**Beslissing:** alle drie JSON-bestanden bij startup volledig in-memory laden, in een module-level singleton (`data.STORE`). Totaal ~1.8 MB in-memory — verwaarloosbaar.

Argumenten:
- Bestanden zijn klein genoeg voor full-load.
- Per-request laden = ~10ms json-parse * elke request = onnodige IO.
- Geen invalidatie-complexiteit; herladen gebeurt expliciet.

**Refresh-mechanisme:**
- `POST /api/reload` herleest de drie files (idempotent, tien-regels-functie). Beschermd met simpele check op `X-Reload-Token` header (waarde uit env-var `RELOAD_TOKEN`). Voor breder gebruik zet je je eigen toegangsbeveiliging ervoor.
- **Geen automatische mtime-watcher** (`watchfiles` is afgewezen). Reden: Apple Health export is periodiek en gebruiker triggert reload bewust na nieuwe export. Dagelijkse auto-sync niet nodig.

**Schema-versie-check bij startup:** als `schema_version != 1` in één van de files → log fatal, exit 1. Geen graceful degradation.

---

## API-endpoints

Alle responses zijn JSON. Datums altijd `YYYY-MM-DD`. Tijden ISO-8601+tz.
Geen pagination nodig op deze dataset-grootte.

### `GET /api/summary`

Doel: bovenste blok "Vandaag" + sectie 7 "Workouts per type" defaultweergave.

Response:
```json
{
  "today": {
    "date": "2026-05-12",
    "is_today": true,
    "days_ago": 0,
    "steps": 12962,
    "distance_km": 10.27,
    "flights": 7,
    "active_kcal": 922,
    "exercise_minutes": 51,
    "stand_hours": 16,
    "resting_hr": 61,
    "hrv_ms": 75.5,
    "sleep": { "asleep_minutes": 389.6, "in_bed_minutes": 398.6, "source": "watch" }
  },
  "totals": { /* uit health-summary.json.totals */ },
  "workout_summary": { /* uit health-summary.json.workout_summary */ },
  "metric_availability": { /* idem */ },
  "date_range": { "from": "2020-10-23", "to": "2026-05-12" }
}
```

### `GET /api/day/{date}`

Doel: dag-detail (modaal of deep-link). `{date}` = `YYYY-MM-DD`.

Response: het dag-object uit `health-data.json.days[date]` met aanvulling:
```json
{
  "date": "2026-05-12",
  "steps": 12962,
  ...alle velden uit data-schema §1...,
  "workouts": [ /* records uit workouts.json met date == this date */ ],
  "sleep_sessions": [ /* records uit sleep.json met wake_date == this date */ ]
}
```

`404` als dag niet bestaat in `health-data.json`.

### `GET /api/week?end=YYYY-MM-DD`

Doel: sectie 2 (laatste 7 dagen). `end` optioneel, default = laatste dag in dataset.

Response:
```json
{
  "start": "2026-05-06",
  "end": "2026-05-12",
  "days": [
    { "date": "2026-05-06", "steps": ..., "exercise_minutes": ..., "sleep": {...} },
    ...
  ],
  "averages": { "steps": 9234, "asleep_minutes": 412.0, "exercise_minutes": 28 },
  "deltas_vs_previous_week": { "steps": +812, "asleep_minutes": -14.3 }
}
```

Dagen zonder data komen wél in de array maar met `{ "date": "...", "missing": true }` zodat de bar-chart een gat krijgt.

### `GET /api/range?days=30&fields=steps,exercise_minutes`

Doel: generieke time-series ophaler voor secties 3, 5, 6.

Query-params:
- `days` (default 30, max 365) — aantal dagen tot en met laatste beschikbare dag.
- `fields` — komma-gescheiden velden uit dag-object. Geneste velden via dotpath: `sleep.asleep_minutes`, `hr.avg`.

Response:
```json
{
  "start": "2026-04-13",
  "end": "2026-05-12",
  "series": {
    "steps": [ { "date": "2026-04-13", "v": 8123 }, ... ],
    "exercise_minutes": [ ... ]
  },
  "rolling_means": {
    "steps_7d": [ { "date": "2026-04-19", "v": 8950 }, ... ]
  }
}
```

Server berekent 7d-rolling-mean voor numerieke series automatisch. Frontend hoeft geen statistiek te doen.

### `GET /api/workouts?since=YYYY-MM-DD&type=Walking`

Doel: sectie 4 en sectie 7-periode-filter.

Beide query-params optioneel. Zonder params: alle 563 records (klein genoeg).

Response:
```json
{
  "count": 142,
  "workouts": [ {...record uit workouts.json...} ],
  "aggregates": {
    "by_type": { "Walking": { "count": 112, "duration_min": 2840.5 }, ... },
    "by_week": [ { "week": "2026-W18", "count": 6, "duration_min": 184.0 }, ... ]
  }
}
```

### `GET /api/sleep?days=30`

Doel: sectie 6.

Response:
```json
{
  "days": [
    { "wake_date": "...", "asleep_minutes": ..., "deep_minutes": ..., ... },
    ...
  ],
  "average_asleep_minutes": 412.0,
  "consistency_minutes_stddev": 47.2
}
```

### `GET /api/health`

Doel: liveness + diagnostiek.

Response:
```json
{
  "status": "ok",
  "schema_version": 1,
  "loaded_at": "2026-05-14T03:01:00",
  "files": {
    "health-data.json": { "days": 2028, "mtime": "..." },
    "workouts.json": { "count": 563, "mtime": "..." },
    "sleep.json": { "sessions": 2054, "mtime": "..." }
  }
}
```

### `POST /api/reload`

Doel: handmatig herladen na parser-run. Token-protected (header `X-Reload-Token`).
Response: zelfde shape als `/api/health` na reload.

### `GET /`

Serveert `static/index.html`. Alle andere static assets onder `/static/*`.

---

## Static serving — vendored vs CDN

**Beslissing: vendored.** Chart.js wordt eenmalig gedownload en in `app/static/vendor/chart.umd.min.js` gezet (~210KB). Redenen:

- Dashboard moet werken zonder internet (lokaal netwerk).
- Geen externe afhankelijkheid in CSP, ook niet achter een eventuele eigen reverse proxy.
- Reproduceerbaar — geen "Chart.js heeft een breaking change in v5" verrassingen.

Versie pinnen in `static/vendor/VERSION.txt`. Updates handmatig.

CSS is custom & klein; geen Tailwind, geen externe framework.

---

## Dev-workflow

```bash
cd <PROJECT_DIR>/app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
HEALTH_DATA_DIR=./data/parsed \
  uvicorn main:app --host 127.0.0.1 --port 8095 --reload
```

Browser: `http://127.0.0.1:8095/`.

`--reload` triggert op `app/**/*.py` én `app/static/**`. Data wordt **niet** automatisch herladen bij mtime-change van JSON — gebruik `POST /api/reload` of restart-process.

---

## v1 minimum-lovable view

Eén HTML-pagina `static/index.html`, één `app.js`, één `styles.css`. Layout van boven naar beneden:

1. **Header-strook** — "Health Dashboard" links, datum-badge rechts (laatste beschikbare dag, "vandaag" of "x dagen geleden").
2. **Vandaag-blok** (sectie 1 uit dashboard-spec) — horizontale rij met 8 tegels. Eén `fetch('/api/summary')` vult dit blok.
3. **Stappen 30 dagen** (sectie 3, eerste chart) — Chart.js line+area chart. Eén `fetch('/api/range?days=30&fields=steps')` vult dit. Inclusief 7d-rolling-mean lijn.

Daarmee is v1 functioneel "live": je kunt zien hoe het vandaag staat, en of de afgelopen maand gemiddeld klopt. Dat is genoeg voor een bruikbare eerste versie.

Sectie 2 (week) en sectie 7 (workouts-donut) komen direct daarna, maar zijn niet nodig om v1 als "lovable" te aanvaarden.

---

## Niet in dit document

- Authenticatie, cookies, CORS-policy (CORS staat default uit; alleen same-origin) — via je eigen toegangsbeveiliging.
- TLS, certificaten, hostnames — via je eigen reverse proxy.
- Docker-compose, healthchecks, restart-policy — afhankelijk van je eigen omgeving.
- Netwerkconfiguratie (DNS, firewall) — afhankelijk van je eigen omgeving.
- Logging-aggregatie — buiten scope.
- Backup van JSON-files — valt onder je eigen backup-oplossing voor de data-map.
