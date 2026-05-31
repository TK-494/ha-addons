# data-schema.md

Contract tussen parser (`parser/parse_health.py`) en frontend (FastAPI + Chart.js).
Locatie: de geconfigureerde datamap (env `HEALTH_DATA_DIR`), buiten de webroot en met restrictieve permissies.

Gemeten in de huidige export (peildatum 2026-05-12):

| Bestand | Grootte | Records |
|---|---|---|
| `health-data.json` | ~965 KB | 2028 dagen |
| `workouts.json` | ~155 KB | 563 workouts |
| `sleep.json` | ~671 KB | 2054 sessies |
| `suspicious-workouts.json` | ~2 KB | 5 records |
| `health-summary.json` | ~2 KB | 1 object |

Alle bestanden zijn UTF-8, ASCII-safe, atomair geschreven (`.tmp` + `rename`).
Tijden in ISO-8601 met timezone-offset (Europe/Amsterdam).
Datums in `YYYY-MM-DD` (lokale wake-/calendar-datum, niet UTC).

---

## 1. `health-data.json` — dag-aggregaten

### Top-level

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-14T02:39:14",
  "export_date": "2026-05-12 22:03:09 +0200",
  "date_range": { "from": "2020-10-23", "to": "2026-05-12" },
  "days": { "<YYYY-MM-DD>": { ...dag-object... }, ... }
}
```

- `days` is een dict, **niet** een lijst. Sleutels zijn aaneengesloten kalenderdagen tussen `from` en `to`.
- Dagen zonder enige observatie worden weggelaten (gaten zijn dus mogelijk; frontend moet hier rekening mee houden bij rolling windows).

### Per-dag object

Volledige velden (alle optioneel behalve `steps`/`distance_source`):

| Veld | Type | Eenheid | Aanwezig op | Toelichting |
|---|---|---|---|---|
| `steps` | int | stappen | 2028/2028 | 0 toegestaan |
| `steps_source` | `"watch"` / `"iphone"` | — | 2028/2028 | dedup-bron na watch-voorkeur |
| `distance_km` | float | km | 2027/2028 | wandel/loop, niet workout-distance |
| `distance_source` | `"watch"` / `"iphone"` | — | 2028/2028 | |
| `flights` | int | trappen | 1632/2028 | mag 0 zijn |
| `flights_source` | `"watch"` / `"iphone"` | — | 1632/2028 | |
| `hr` | object | — | 1035/2028 | zie hieronder, alleen Watch-dagen |
| `resting_hr` | int | bpm | 985/2028 | dag-gemiddelde van Apple |
| `hrv_ms` | float | ms | 1028/2028 | SDNN-equivalent |
| `vo2_max` | float | mL/kg/min | 249/2028 | sporadisch, alleen na buitenwandelingen |
| `active_kcal` | float | kcal | 1051/2028 | uit ActivitySummary |
| `exercise_minutes` | int | min | 951/2028 | uit ActivitySummary |
| `stand_hours` | int | uren | 1021/2028 | uit ActivitySummary |
| `weight_kg` | float | kg | 35/2028 | handmatig, mag dus ontbreken |
| `sleep` | object | — | 1622/2028 | zie hieronder |

`hr` (heart-rate samples over de dag, geen workout-only):
```json
{ "min": 47, "avg": 93, "max": 137, "samples": 713 }
```

`sleep` (geaggregeerd per nacht waarvan de **wakker-datum** == deze dag):
```json
{
  "in_bed_minutes": 432.7,
  "asleep_minutes": 415.2,
  "deep_minutes": 70.1,
  "rem_minutes": 81.1,
  "core_minutes": 263.9,
  "awake_minutes": 17.5,
  "source": "watch"
}
```
- Pre-Watch-tijdperk: `asleep/deep/rem/core/awake_minutes` zijn allemaal `0`, alleen `in_bed_minutes` heeft betekenis. Frontend moet bij `source == "iphone"` slaapfasen niet tonen.

### NULL- en defaults-regels

- Velden zijn óf aanwezig met geldige waarde, óf afwezig (geen `null` of `None`).
- Een dag-object kan **alleen** `steps`/`distance_source` bevatten en verder niets.
- Frontend gebruikt `dayObj.foo ?? null` patronen, geen `dayObj.foo === undefined`-checks in chart-data.

---

## 2. `workouts.json` — individuele workouts (clean)

### Top-level

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-14T02:39:14",
  "workouts": [ {...}, {...} ]
}
```

- `workouts` is een **lijst**, gesorteerd op `start` oplopend.
- Alleen "clean" records (suspicious gefilterd → eigen bestand, zie §5).

### Per-record

| Veld | Type | Eenheid | Notitie |
|---|---|---|---|
| `date` | str | `YYYY-MM-DD` | lokale start-datum |
| `type` | str | Apple-enum | bv. `Walking`, `Cycling`, `Rowing`, `Hiking`, `Elliptical`, `FunctionalStrengthTraining`, `Swimming`, `StairClimbing`, `Other` |
| `start` | str | ISO-8601+tz | |
| `end` | str | ISO-8601+tz | |
| `duration_minutes` | float | min | |
| `distance_km` | float | km | mag `0.0` zijn |
| `active_kcal` | float | kcal | mag `0.0` zijn (iPhone-only workouts) |
| `avg_hr` | int / `null` | bpm | **kan `null`** als geen HR-bron |
| `source` | `"watch"` / `"iphone"` | — | |

`avg_hr` is het enige veld dat expliciet `null` mag zijn (oude iPhone-workouts). Andere "missing" waardes zijn `0`/`0.0`.

---

## 3. `sleep.json` — slaap-sessies (raw, niet per-dag geaggregeerd)

### Top-level

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-14T02:39:14",
  "sessions": [ {...}, {...} ]
}
```

- `sessions` is een **lijst**, gesorteerd op `in_bed_start` oplopend.

### Per-record

| Veld | Type | Notitie |
|---|---|---|
| `wake_date` | str (`YYYY-MM-DD`) | lokale datum waarop deze sessie eindigt — sleutel voor join met `health-data.json` |
| `in_bed_start` | str ISO-8601+tz | |
| `in_bed_end` | str ISO-8601+tz | |
| `in_bed_minutes` | float | totale tijd in bed |
| `asleep_minutes` | float | mag `0` zijn op iPhone-only nachten |
| `deep_minutes` | float | idem |
| `rem_minutes` | float | idem |
| `core_minutes` | float | idem |
| `awake_minutes` | float | idem |
| `source` | `"watch"` / `"iphone"` | |

**Relatie tot `health-data.json`:** het `sleep`-object onder een dag in `health-data.json` is de geaggregeerde versie van álle sessies met die `wake_date`. Frontend kiest:
- voor day-view & 7-dag-trend → `health-data.json[date].sleep` (gemakkelijk).
- voor detail-modal of nap-detectie → filter `sleep.json.sessions` op `wake_date`.

---

## 4. `health-summary.json` — totalen + diagnostiek

Statisch overzichts-object. Bron voor: workouts-per-type donut, metric-availability-banner, "sinds-wanneer-watch"-detectie.

Velden: `schema_version`, `generated_at`, `export_date`, `date_range`, `totals`, `workout_summary` (per type: `count`, `total_duration_min`, `total_distance_km`, `total_kcal`), `workout_quality` (clean vs suspicious split), `sources` (lijst device-namen), `metric_availability` (`days_with_steps`, `days_with_sleep`, `days_with_resting_hr`, `days_with_hrv`, `days_with_vo2`, `days_with_weight`).

Zie het bestand zelf voor exacte waardes.

---

## 5. `suspicious-workouts.json` — uitgesloten records

Niet voor frontend-rendering; alleen debugging.

```json
{
  "schema_version": 1,
  "filter_criteria": {...},
  "workouts": [ { ...zelfde shape als workouts.json...,
                  "suspicious_reasons": ["duration_over_6h", ...] } ]
}
```

De frontend leest dit bestand **niet** in v1. Eventueel later voor een "data-kwaliteit" admin-paneel.

---

## Schema-versionering

- `schema_version: 1` in alle bestanden. Bij breaking changes verhoogt de parser dit getal én documenteert hier wat anders is.
- FastAPI-backend faalt fast bij `schema_version != verwachte versie` (startup-check, geen runtime-degraderen).
