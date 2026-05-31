# dashboard-spec.md

Visuele specificatie voor de 9 dashboardsecties. Bepaalt welke metrics waar staan, welk chart-type, welke kleur. Geen layout-mockup; geen CSS-implementatiedetails.

## Designtaal (kort)

- **Basis:** donker thema (donkere achtergrond `#0e1116`-achtig, kaarten iets lichter, witte tekst, monospaced cijfers).
- **Accenten** (gereserveerd, niet decoratief inzetten):
  - blauw `#4aa8ff` — neutrale trend / activiteit
  - groen `#4ade80` — positief / herstel / op-koers
  - oranje `#f59e0b` — let op / onder-target / vermoeidheid
  - rood — **niet gebruiken** (geen ziekenhuis-look)
- Eén accent per metric-card. Charts default-lijn neutraal-blauw, fill 8% opacity.
- Geen iconen-overload (max 1 icoon per card, lijn-stijl).
- Getallen groot, eenheden klein en grijs ernaast.

## Versiebeleid

- **v1 (must-have):** secties 1, 2, 3, 7 + de "stappen 30d"-chart die als minimum-lovable geldt.
- **v2 (na export-validatie):** secties 4, 5, 6, 8, 9.

---

## Sectie 1 — Vandaag / laatste beschikbare dag — **v1**

**Doel:** snel "hoe sta ik ervoor vandaag?" — bovenste blok op de pagina, altijd zichtbaar.

**Bron:** laatste key in `health-data.json.days` (NIET `today()` — kan ontbreken).

**Stale-data-waarschuwing:** gebaseerd op `latest_data_date` vs vandaag:
- Ouder dan **7 dagen** → milde melding: *"Data is niet helemaal actueel"*
- Ouder dan **30 dagen** → duidelijke melding: *"Nieuwe Apple Health export aanbevolen"*
- Reden: export is periodiek, geen dagelijkse drempel.

**Inhoud (tegels naast elkaar, één rij):**

| Tegel | Veld | Formaat | Accent-regel |
|---|---|---|---|
| Datum-badge | de gebruikte dag-key | `"vandaag"` als `==today`, anders `"x dagen geleden"` | grijs |
| Stappen | `steps` | int, duizendtal-separator | groen ≥10000, blauw ≥5000, oranje <5000 |
| Afstand | `distance_km` | 1 decimaal + " km" | blauw |
| Trappen | `flights` | int | blauw |
| Actieve kcal | `active_kcal` | int afronden | blauw |
| Beweegminuten | `exercise_minutes` | int + " min" | groen ≥30 anders blauw |
| Rust-HR | `resting_hr` | int + " bpm" | blauw, oranje als ≥10 bpm hoger dan 30d-mediaan (v2) |
| Slaap | `sleep.asleep_minutes` | `Hu Mm` formaat (bv. `6u 29m`) | groen ≥7u, blauw 6–7u, oranje <6u |

**Chart:** geen.
**Edge:** als veld ontbreekt → toon `"—"` in grijs, geen `0`.

---

## Sectie 2 — Weektrend (laatste 7 dagen) — **v1**

**Doel:** korte-termijn-context onder Vandaag.

**Bron:** laatste 7 dag-keys.

**Layout:** 2 kaarten naast elkaar.

| Kaart | Chart-type | X | Y | Kleur |
|---|---|---|---|---|
| Stappen per dag | bar | datum (Ma–Zo) | `steps` | blauw, balken op of boven 10k worden groen |
| Slaap per nacht | stacked bar | wake-datum | `deep_minutes`, `rem_minutes`, `core_minutes`, `awake_minutes` | deep=donkerblauw, rem=blauw, core=lichtblauw, awake=oranje |

Onder elke kaart: gemiddelde over 7d in cijfers + delta vs voorgaande 7d (groen omhoog voor stappen, omhoog/omlaag is context-afhankelijk voor slaap — geen oordeel in v1, alleen het getal).

---

## Sectie 3 — Maandtrend (laatste 30 dagen) — **v1**

**Doel:** "klopt mijn beweegniveau gemiddeld?". Dit is óók de minimum-lovable-chart (zie FastAPI-design §v1-view).

**Bron:** laatste 30 dag-keys.

**Charts:**

| Chart | Type | X | Y | Kleur |
|---|---|---|---|---|
| Stappen 30d | line + area | datum | `steps` | blauw lijn 2px, 8% fill, 7d-rolling-mean als tweede dunne lijn in groen |
| Beweegminuten 30d | bar | datum | `exercise_minutes` | groen ≥30, blauw <30 |

Geen tooltip-extravaganza; Chart.js default tooltip met datum + waarde.

---

## Sectie 4 — Trainingstrend sinds januari 2026 — **v2**

**Doel:** "ben ik vooruit gegaan sinds ik trainen ben opgepakt?".

**Bron:** filter `workouts.json.workouts` op `date >= "2026-01-01"`.

**Charts:**

| Chart | Type | X | Y |
|---|---|---|---|
| Workouts per week | stacked bar | weeknummer | `count` per `type` (alleen top-5 types deze periode) |
| Totale duur per week | bar | weeknummer | `sum(duration_minutes)` |
| Gemiddelde HR per workout | scatter | `date` | `avg_hr` (null filteren), kleur op `type` |

Sectie-titel toont peilperiode "1 jan 2026 – vandaag" en aantal workouts in die periode.

---

## Sectie 5 — Conditie: VO2max, rusthartslag, HRV — **v2**

**Doel:** lange-termijn-kerngetallen voor cardiovasculaire conditie.

**Bron:** `health-data.json.days`, velden `vo2_max`, `resting_hr`, `hrv_ms`. Sparse; vo2 maar 249/2028 dagen — interpoleer NIET, plot alleen meetpunten.

**Charts:**

| Chart | Type | X | Y | Kleur | Gat-regel |
|---|---|---|---|---|---|
| VO2max trend | line met markers | datum | `vo2_max` | blauw, marker per meetpunt | **onderbreek lijn bij gaten >14 dagen** (geen interpolatie) |
| Rusthartslag (90d) | line | datum (laatste 90d) | `resting_hr` | blauw, 14d-rolling-mean in groen | — |
| HRV (90d) | line | datum (laatste 90d) | `hrv_ms` | blauw, 14d-rolling-mean in groen | — |

Boven elke chart: huidige waarde (laatste meetpunt) + delta vs 90d-mediaan.

---

## Sectie 6 — Slaap / herstel — **v2**

**Doel:** uitgebreider dan sectie 2; toont slaap-fase-balans en consistency.

**Bron:** `health-data.json.days[*].sleep` voor laatste 30d; voor detail eventueel `sleep.json.sessions`.

**Charts:**

| Chart | Type | X | Y | Notitie |
|---|---|---|---|---|
| Slaapduur 30d | line + area | wake-datum | `asleep_minutes / 60` | doel-lijn op 7u (gestippeld, groen); **altijd tonen** |
| Slaapfase-verdeling | stacked bar | wake-datum (30d) | deep/rem/core/awake | **alleen als echte fase-data** (Watch); bij iPhone-only: placeholder *"slaapfasen niet beschikbaar"* |
| Bedtijd-spreiding | scatter / horizontal box | wake-datum | `in_bed_start` op uurschaal (18:00–02:00) | consistency-indicator |

KPI-tegel: "gem. slaap 30d" met groen/oranje accent.
**Slaapduur tonen** `source == "iphone"` óf `source == "watch"` (beide betrouwbaar). **Slaapfasen** (`deep/rem/core/awake`) alleen renderen als `source == "watch"`.

---

## Sectie 7 — Workouts per type — **v1**

**Doel:** waar besteed ik mijn trainingstijd aan? (bijvoorbeeld voorbereiding op een geplande bergtocht).

**Bron:** `health-summary.json.workout_summary` (v1 default) + `workouts.json` voor periode-filter (v2).

**UI — v1 (standaard):**

| Component | Type | Inhoud |
|---|---|---|
| Periode-toggle | knopjes `90d` / `30d` / `1 jaar` / `all-time` | filtert client-side op `start_date` |
| Donut | donut | count per `type`, gesorteerd, top-7 + "overig" |
| Tabel onder donut | rows | type, count, totale duur (uren), totale afstand (km) |

**v1 default:** `90d` (niet all-time, past beter bij huidge trainingspatroon). Dit vereist client-side filtering van `workouts.json` op `start_date >= today-90d`.

Kleuren: één palet van 7 onderscheidende tinten blauw/groen/teal; oranje gereserveerd voor "overig" als attentie-categorie.

---

## Sectie 8 — Hiking-readiness (meerdaagse bergtocht) — **v2**

**Doel:** countdown + go/no-go-indicator richting een zelf gekozen geplande bergtocht.

**Bron:** `workouts.json` (type `Walking`/`Hiking`, met `distance_km > 0` of `duration_minutes > 60`) + flights/elevation-proxy uit `health-data.json.days[*].flights`.

**Inhoud:**

| Element | Beschrijving |
|---|---|
| Countdown-tegel | dagen tot de geplande tochtdatum |
| Volume-grafiek | bar per week: aantal wandelingen ≥60min |
| Klim-proxy | line: 7d-som van `flights` (Watch is hier accurater) |
| Readiness-score | enkel cijfer 0–100, formule later vast te leggen (niet hier) |

Sectie verbergt zichzelf zodra de geplande tochtdatum meer dan 7 dagen verstreken is.

---

## Sectie 9 — Signalenblok — **v2**

**Doel:** plain-text "hoe gaat het deze week?" — geen advies, alleen patronen.

**Bron:** afgeleid uit dezelfde data; logica later vast te leggen.

**Mogelijke signalen** (max 3 tegelijk getoond, gesorteerd op urgentie):

| Signaal | Trigger-schets | Kleur |
|---|---|---|
| Te weinig beweging | 7d-gem stappen <5000 én vorige 7d ≥5000 | oranje |
| Goede week | 7d-gem stappen ≥10000 én exercise_minutes ≥30/dag op ≥5 dagen | groen |
| Herstel nodig | HRV 7d-mediaan <70% van 90d-mediaan | oranje |
| Slaap laag | 7d-gem `asleep_minutes` <360 | oranje |
| Conditie ↑ | resting_hr 30d-mediaan ≥3 bpm lager dan 90d-mediaan | groen |
| Conditie ↓ | resting_hr 30d-mediaan ≥5 bpm hoger dan 90d-mediaan | oranje |

Formules zijn placeholders — definitieve drempels stel je later in op basis van je eigen baseline uit je export.

---

## Out-of-scope (expliciet niet in dashboard)

- Cycle tracking, bloeddruk, mindful minutes.
- GPS-routes / kaarten (GPX niet geparsed, privacy).
- Settings-pagina, export-knop, account-beheer — geen authenticatie hier (zet je eigen toegangsbeveiliging ervoor).
- Mobile-first responsive layout — desktop primair, single-column-fallback acceptabel.
- Animaties, transitions, parallax — Chart.js defaults.
