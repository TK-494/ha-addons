# Apple Health Parser

Compacte JSON-aggregaten uit een Apple Health `export.zip`.
Geen dashboard, geen netwerk, geen Docker — alleen data.

## Locaties

| Wat | Pad (default) |
|---|---|
| Input  | `./data/export.zip` |
| Output | `./data/parsed/*.json` |
| Code   | `parser/parse_health.py` |

De paden zijn instelbaar via env-vars (`HEALTH_EXPORT_ZIP`, `HEALTH_DATA_DIR`) of
via de CLI-opties `--zip` en `--out`. Zet de datamap bij voorkeur buiten de
webroot en met restrictieve permissies; ruwe exports horen niet in version control.

## Apple Health exporteren

1. iPhone → Health-app → profielfoto rechtsboven → "Gegevens exporteren".
2. Wacht (kan 1–5 min). Resultaat: `export.zip`.
3. Zet `export.zip` op de plek die de parser leest (default `./data/export.zip`).

## Draaien

```bash
python3 parser/parse_health.py
```

Optioneel een ander pad:

```bash
python3 parser/parse_health.py \
  --zip /pad/naar/export.zip \
  --out /pad/naar/out/
```

Alleen stdlib — geen `pip install` nodig. Werkt op de systeem-`python3`.

## Output

| Bestand | Inhoud |
|---|---|
| `health-data.json`    | Per dag: stappen, afstand, trappen, kcal, beweegminuten, sta-uren, hartslag (min/avg/max), rust-HR, HRV, VO2max, gewicht, slaap-samenvatting |
| `health-summary.json` | Totalen + workout-samenvatting per type + databronnen + beschikbaarheid per metric |
| `workouts.json`       | Platte lijst van alle workouts (datum, type, duur, afstand, kcal, avg HR, bron) |
| `sleep.json`          | Slaapsessies met fasen (deep/REM/core/awake) |

## Watch-voorkeur (dubbeltelling-fix)

Voor **stappen**, **afstand**, **trappen** en **slaap** kiest de parser per dag/sessie de
Apple Watch-bron als die iets logde, anders iPhone. Dat voorkomt dubbeltelling als
beide apparaten dezelfde activiteit registreerden.

Voor **actieve kcal**, **beweegminuten** en **sta-uren** gebruikt de parser
`ActivitySummary` — Apple aggregeert die al correct per dag.

## Privacy

- Routes (`workout-routes/*.gpx`) worden **niet** geparsed of opgeslagen.
- Clinical CDA (`export_cda.xml`) wordt **niet** geparsed.
- Locaties komen niet in de JSON.
- De ruwe `export.zip` blijft op disk staan; verwijder zelf wanneer je 'm niet meer nodig hebt.

## Refresh-werkwijze

1. Nieuwe `export.zip` droppen → overschrijft de oude.
2. Parser opnieuw draaien.
3. JSON in `parsed/` wordt atomair vervangen.

## Smoke-test (zonder export)

```bash
python3 parser/parse_health.py --zip /tmp/bestaat-niet.zip
# Verwacht: nette foutmelding, exit-code != 0
```
