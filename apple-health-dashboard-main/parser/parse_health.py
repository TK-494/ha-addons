#!/usr/bin/env python3
"""
parse_health.py — Apple Health export.zip → compacte JSON-aggregaten.

Input : ./data/export.zip
Output: ./data/parsed/
        ├── health-data.json     (per-dag metrieken)
        ├── health-summary.json  (totalen + bronnen + beschikbaarheid)
        ├── workouts.json        (alle workouts platte lijst)
        └── sleep.json           (slaapsessies)

Veilig:
  - leest alleen export.xml binnen de zip (geen extract op disk)
  - schrijft via .tmp + atomic rename (geen halve files)
  - verwijdert niets

Watch-voorkeur:
  Voor steps / distance / flights wordt per dag de Apple Watch-bron gekozen
  als die iets logde, anders iPhone — voorkomt dubbeltelling.
  Voor active_kcal / exercise_minutes / stand_hours wordt ActivitySummary
  gebruikt (Apple aggregeert die al correct per dag).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from xml.etree.ElementTree import iterparse

DEFAULT_EXPORT = Path(os.environ.get("HEALTH_EXPORT_ZIP", "./data/export.zip"))
DEFAULT_OUT = Path(os.environ.get("HEALTH_DATA_DIR", "./data/parsed"))

QUANTITY_TYPES = {
    "HKQuantityTypeIdentifierStepCount": "steps",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "distance_km",
    "HKQuantityTypeIdentifierFlightsClimbed": "flights",
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_hr",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv_ms",
    "HKQuantityTypeIdentifierVO2Max": "vo2_max",
    "HKQuantityTypeIdentifierBodyMass": "weight_kg",
    "HKQuantityTypeIdentifierHeartRate": "hr",
}

SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
SLEEP_VALUES = {
    "HKCategoryValueSleepAnalysisInBed": "in_bed",
    "HKCategoryValueSleepAnalysisAsleep": "asleep_unspecified",
    "HKCategoryValueSleepAnalysisAsleepCore": "asleep_core",
    "HKCategoryValueSleepAnalysisAsleepDeep": "asleep_deep",
    "HKCategoryValueSleepAnalysisAsleepREM": "asleep_rem",
    "HKCategoryValueSleepAnalysisAwake": "awake",
}

WORKOUT_TYPE_PREFIX = "HKWorkoutActivityType"


def is_watch(source_name: str) -> bool:
    if not source_name:
        return False
    return "watch" in source_name.lower()


def parse_apple_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None


@dataclass
class DailyBucket:
    steps_watch: float = 0.0
    steps_iphone: float = 0.0
    distance_watch: float = 0.0
    distance_iphone: float = 0.0
    flights_watch: float = 0.0
    flights_iphone: float = 0.0
    hr_values: list = field(default_factory=list)
    resting_hr_values: list = field(default_factory=list)
    hrv_values: list = field(default_factory=list)
    vo2_values: list = field(default_factory=list)
    weight_values: list = field(default_factory=list)


@dataclass
class ActivitySummary:
    active_kcal: float = 0.0
    exercise_minutes: float = 0.0
    stand_hours: float = 0.0
    move_time_minutes: float = 0.0


def process_record(elem, daily, sleep_intervals):
    r_type = elem.get("type")
    source = elem.get("sourceName") or ""
    start = parse_apple_date(elem.get("startDate"))
    end = parse_apple_date(elem.get("endDate"))
    value_s = elem.get("value")

    if start is None:
        return

    if r_type == SLEEP_TYPE:
        if end is None or value_s not in SLEEP_VALUES:
            return
        sleep_intervals.append({
            "start": start,
            "end": end,
            "kind": SLEEP_VALUES[value_s],
            "source": source,
        })
        return

    short = QUANTITY_TYPES.get(r_type)
    if not short:
        return

    try:
        value = float(value_s) if value_s is not None else 0.0
    except (ValueError, TypeError):
        return

    day_key = start.date().isoformat()
    bucket = daily.setdefault(day_key, DailyBucket())

    if short == "steps":
        if is_watch(source):
            bucket.steps_watch += value
        else:
            bucket.steps_iphone += value
    elif short == "distance_km":
        if is_watch(source):
            bucket.distance_watch += value
        else:
            bucket.distance_iphone += value
    elif short == "flights":
        if is_watch(source):
            bucket.flights_watch += value
        else:
            bucket.flights_iphone += value
    elif short == "hr":
        bucket.hr_values.append(value)
    elif short == "resting_hr":
        bucket.resting_hr_values.append(value)
    elif short == "hrv_ms":
        bucket.hrv_values.append(value)
    elif short == "vo2_max":
        bucket.vo2_values.append(value)
    elif short == "weight_kg":
        bucket.weight_values.append(value)


def process_activity_summary(elem, activity):
    d = elem.get("dateComponents")
    if not d:
        return
    a = activity.setdefault(d, ActivitySummary())
    try:
        a.active_kcal = float(elem.get("activeEnergyBurned") or 0.0)
        a.exercise_minutes = float(elem.get("appleExerciseTime") or 0.0)
        a.stand_hours = float(elem.get("appleStandHours") or 0.0)
        a.move_time_minutes = float(elem.get("appleMoveTime") or 0.0)
    except ValueError:
        pass


def classify_workout(workout: dict, start: datetime, end: Optional[datetime]) -> list:
    """Geeft lijst van flag-redenen terug. Lege lijst = clean."""
    reasons = []
    dur = workout["duration_minutes"]
    if dur > 360:
        reasons.append("duration_over_6h")
    if dur <= 0:
        reasons.append("duration_non_positive")
    if end is not None and start.date() != end.date():
        reasons.append("spans_multiple_days")
    if (workout["source"] == "iphone"
            and (workout["active_kcal"] or 0) == 0
            and workout["avg_hr"] is None
            and dur > 180):
        reasons.append("iphone_idle_long")
    return reasons


def process_workout(elem, workouts, workout_summary, suspicious, suspicious_summary):
    wtype_full = elem.get("workoutActivityType") or ""
    wtype = wtype_full.replace(WORKOUT_TYPE_PREFIX, "") or "Unknown"
    start = parse_apple_date(elem.get("startDate"))
    end = parse_apple_date(elem.get("endDate"))
    if start is None:
        return

    try:
        duration = float(elem.get("duration") or 0.0)
    except ValueError:
        duration = 0.0
    duration_unit = elem.get("durationUnit") or "min"
    if duration_unit == "h":
        duration_minutes = duration * 60
    elif duration_unit == "s":
        duration_minutes = duration / 60
    else:
        duration_minutes = duration

    try:
        distance = float(elem.get("totalDistance") or 0.0)
    except ValueError:
        distance = 0.0
    distance_unit = elem.get("totalDistanceUnit") or "km"
    if distance_unit == "mi":
        distance_km = distance * 1.609344
    elif distance_unit == "m":
        distance_km = distance / 1000
    else:
        distance_km = distance

    try:
        energy = float(elem.get("totalEnergyBurned") or 0.0)
    except ValueError:
        energy = 0.0

    source = elem.get("sourceName") or ""

    avg_hr = None
    for meta in elem.findall("MetadataEntry"):
        if meta.get("key") == "HKAverageHeartRate":
            try:
                avg_hr = float(meta.get("value"))
            except (ValueError, TypeError):
                pass

    workout = {
        "date": start.date().isoformat(),
        "type": wtype,
        "start": start.isoformat(),
        "end": end.isoformat() if end else None,
        "duration_minutes": round(duration_minutes, 1),
        "distance_km": round(distance_km, 3) if distance_km else 0.0,
        "active_kcal": round(energy, 1),
        "avg_hr": avg_hr,
        "source": "watch" if is_watch(source) else "iphone",
    }

    reasons = classify_workout(workout, start, end)
    if reasons:
        workout["suspicious_reasons"] = reasons
        suspicious.append(workout)
        s = suspicious_summary.setdefault(wtype, {
            "count": 0,
            "total_duration_min": 0.0,
        })
        s["count"] += 1
        s["total_duration_min"] += duration_minutes
        return

    workouts.append(workout)

    s = workout_summary.setdefault(wtype, {
        "count": 0,
        "total_duration_min": 0.0,
        "total_distance_km": 0.0,
        "total_kcal": 0.0,
    })
    s["count"] += 1
    s["total_duration_min"] += duration_minutes
    s["total_distance_km"] += distance_km
    s["total_kcal"] += energy


def consolidate_sleep(intervals):
    if not intervals:
        return []

    intervals.sort(key=lambda i: i["start"])

    sessions_raw = []
    current = []
    gap = timedelta(minutes=30)

    for iv in intervals:
        if not current:
            current = [iv]
            continue
        last_end = max(x["end"] for x in current)
        if iv["start"] - last_end <= gap:
            current.append(iv)
        else:
            sessions_raw.append(current)
            current = [iv]
    if current:
        sessions_raw.append(current)

    sessions = []
    for group in sessions_raw:
        has_watch = any(is_watch(g["source"]) for g in group)
        use = [g for g in group if is_watch(g["source"])] if has_watch else group
        if not use:
            continue

        def mins(kind):
            return sum((g["end"] - g["start"]).total_seconds() / 60 for g in use if g["kind"] == kind)

        deep = mins("asleep_deep")
        rem = mins("asleep_rem")
        core = mins("asleep_core")
        unspec = mins("asleep_unspecified")
        awake = mins("awake")
        in_bed = mins("in_bed")

        asleep_total = deep + rem + core + unspec

        start_sess = min(g["start"] for g in use)
        end_sess = max(g["end"] for g in use)

        sessions.append({
            "wake_date": end_sess.date().isoformat(),
            "in_bed_start": start_sess.isoformat(),
            "in_bed_end": end_sess.isoformat(),
            "in_bed_minutes": round(in_bed if in_bed > 0 else (end_sess - start_sess).total_seconds() / 60, 1),
            "asleep_minutes": round(asleep_total, 1),
            "deep_minutes": round(deep, 1),
            "rem_minutes": round(rem, 1),
            "core_minutes": round(core, 1),
            "awake_minutes": round(awake, 1),
            "source": "watch" if has_watch else "iphone",
        })

    return sessions


def daily_from_bucket(bucket: DailyBucket) -> dict:
    out = {}

    if bucket.steps_watch > 0:
        out["steps"], out["steps_source"] = int(round(bucket.steps_watch)), "watch"
    elif bucket.steps_iphone > 0:
        out["steps"], out["steps_source"] = int(round(bucket.steps_iphone)), "iphone"

    if bucket.distance_watch > 0:
        out["distance_km"], out["distance_source"] = round(bucket.distance_watch, 2), "watch"
    elif bucket.distance_iphone > 0:
        out["distance_km"], out["distance_source"] = round(bucket.distance_iphone, 2), "iphone"

    if bucket.flights_watch > 0:
        out["flights"], out["flights_source"] = int(round(bucket.flights_watch)), "watch"
    elif bucket.flights_iphone > 0:
        out["flights"], out["flights_source"] = int(round(bucket.flights_iphone)), "iphone"

    if bucket.hr_values:
        out["hr"] = {
            "min": int(round(min(bucket.hr_values))),
            "avg": int(round(sum(bucket.hr_values) / len(bucket.hr_values))),
            "max": int(round(max(bucket.hr_values))),
            "samples": len(bucket.hr_values),
        }

    if bucket.resting_hr_values:
        out["resting_hr"] = int(round(sum(bucket.resting_hr_values) / len(bucket.resting_hr_values)))

    if bucket.hrv_values:
        out["hrv_ms"] = round(sum(bucket.hrv_values) / len(bucket.hrv_values), 1)

    if bucket.vo2_values:
        out["vo2_max"] = round(sum(bucket.vo2_values) / len(bucket.vo2_values), 1)

    if bucket.weight_values:
        out["weight_kg"] = round(bucket.weight_values[-1], 2)

    return out


def write_json_atomic(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def parse(export_zip: Path, out_dir: Path, progress_every: int = 250_000) -> None:
    if not export_zip.exists():
        sys.exit(f"FOUT: {export_zip} bestaat niet. Drop de Apple Health export.zip eerst.")
    out_dir.mkdir(parents=True, exist_ok=True)

    daily: dict = {}
    activity: dict = {}
    workouts: list = []
    workout_summary: dict = {}
    suspicious: list = []
    suspicious_summary: dict = {}
    sleep_intervals: list = []
    sources: set = set()
    export_date: Optional[str] = None

    print(f"[info] Open {export_zip}")
    with zipfile.ZipFile(export_zip) as zf:
        xml_name = None
        for n in zf.namelist():
            if n.endswith("export.xml") and "cda" not in n:
                xml_name = n
                break
        if not xml_name:
            sys.exit("FOUT: export.xml niet gevonden in zip.")

        print(f"[info] Streaming parse {xml_name}")
        with zf.open(xml_name) as f:
            count = 0
            for _event, elem in iterparse(f, events=("end",)):
                tag = elem.tag
                if tag == "Record":
                    src = elem.get("sourceName") or ""
                    if src:
                        sources.add(src)
                    process_record(elem, daily, sleep_intervals)
                elif tag == "ActivitySummary":
                    process_activity_summary(elem, activity)
                elif tag == "Workout":
                    src = elem.get("sourceName") or ""
                    if src:
                        sources.add(src)
                    process_workout(elem, workouts, workout_summary, suspicious, suspicious_summary)
                elif tag == "ExportDate":
                    export_date = elem.get("value")

                count += 1
                if count % progress_every == 0:
                    print(f"[info] {count:,} elementen verwerkt …", flush=True)
                elem.clear()

    print(f"[info] Klaar met parsen ({count:,} elementen).")
    print(f"[info] Bronnen gezien: {sorted(sources)}")

    sleep_sessions = consolidate_sleep(sleep_intervals)
    print(f"[info] Slaapsessies: {len(sleep_sessions)}")

    all_dates = set(daily.keys()) | set(activity.keys())
    for s in sleep_sessions:
        all_dates.add(s["wake_date"])

    days_out = {}
    for d in sorted(all_dates):
        day = {}
        if d in daily:
            day.update(daily_from_bucket(daily[d]))
        if d in activity:
            a = activity[d]
            if a.active_kcal:
                day["active_kcal"] = round(a.active_kcal, 1)
            if a.exercise_minutes:
                day["exercise_minutes"] = int(round(a.exercise_minutes))
            if a.stand_hours:
                day["stand_hours"] = int(round(a.stand_hours))
        sleep_for_day = [s for s in sleep_sessions if s["wake_date"] == d]
        if sleep_for_day:
            main = max(sleep_for_day, key=lambda s: s["asleep_minutes"])
            day["sleep"] = {
                "in_bed_minutes": main["in_bed_minutes"],
                "asleep_minutes": main["asleep_minutes"],
                "deep_minutes": main["deep_minutes"],
                "rem_minutes": main["rem_minutes"],
                "core_minutes": main["core_minutes"],
                "awake_minutes": main["awake_minutes"],
                "source": main["source"],
            }
        days_out[d] = day

    date_range = {
        "from": min(all_dates) if all_dates else None,
        "to": max(all_dates) if all_dates else None,
    }

    health_data = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "export_date": export_date,
        "date_range": date_range,
        "days": days_out,
    }

    total_steps = sum(d.get("steps", 0) for d in days_out.values())
    total_distance = sum(d.get("distance_km", 0) for d in days_out.values())
    total_flights = sum(d.get("flights", 0) for d in days_out.values())

    metric_availability = {
        "days_with_steps": sum(1 for d in days_out.values() if "steps" in d),
        "days_with_sleep": sum(1 for d in days_out.values() if "sleep" in d),
        "days_with_resting_hr": sum(1 for d in days_out.values() if "resting_hr" in d),
        "days_with_hrv": sum(1 for d in days_out.values() if "hrv_ms" in d),
        "days_with_vo2": sum(1 for d in days_out.values() if "vo2_max" in d),
        "days_with_weight": sum(1 for d in days_out.values() if "weight_kg" in d),
    }

    for v in workout_summary.values():
        v["total_duration_min"] = round(v["total_duration_min"], 1)
        v["total_distance_km"] = round(v["total_distance_km"], 2)
        v["total_kcal"] = round(v["total_kcal"], 1)

    for v in suspicious_summary.values():
        v["total_duration_min"] = round(v["total_duration_min"], 1)

    clean_total_duration = round(sum(v["total_duration_min"] for v in workout_summary.values()), 1)
    suspicious_total_duration = round(sum(v["total_duration_min"] for v in suspicious_summary.values()), 1)

    # A. Suspicious workouts examples (max 5)
    suspicious_examples = []
    for w in suspicious[:5]:
        suspicious_examples.append({
            "date": w["date"],
            "type": w["type"],
            "duration_minutes": w["duration_minutes"],
            "source": w["source"],
            "suspicious_reasons": w.get("suspicious_reasons", []),
        })

    # B. Clean workouts by year
    clean_by_year = {}
    for w in workouts:
        date_str = w["date"]  # YYYY-MM-DD
        year = date_str[:4]
        clean_by_year[year] = clean_by_year.get(year, 0) + 1

    # C. Clean workouts by type
    clean_by_type = {}
    for wtype, data in workout_summary.items():
        clean_by_type[wtype] = data["count"]

    # D. Latest data date: max over health-data.json days + clean workouts
    all_data_dates = set(days_out.keys())
    for w in workouts:
        all_data_dates.add(w["date"])
    latest_data_date = max(all_data_dates) if all_data_dates else None

    summary = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "export_date": export_date,
        "date_range": date_range,
        "totals": {
            "days_recorded": len(days_out),
            "workouts": len(workouts),
            "steps": total_steps,
            "distance_km": round(total_distance, 1),
            "flights": total_flights,
        },
        "workout_summary": workout_summary,
        "workout_quality": {
            "clean_workouts_count": len(workouts),
            "clean_workouts_total_duration_min": clean_total_duration,
            "suspicious_workouts_count": len(suspicious),
            "suspicious_workouts_total_duration_min": suspicious_total_duration,
            "suspicious_workouts_by_type": suspicious_summary,
        },
        "suspicious_workouts_examples": suspicious_examples,
        "clean_workouts_by_year": clean_by_year,
        "clean_workouts_by_type": clean_by_type,
        "latest_data_date": latest_data_date,
        "sources": sorted(sources),
        "metric_availability": metric_availability,
    }

    write_json_atomic(out_dir / "health-data.json", health_data)
    write_json_atomic(out_dir / "workouts.json", {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "workouts": workouts,
    })
    write_json_atomic(out_dir / "sleep.json", {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sessions": sleep_sessions,
    })
    write_json_atomic(out_dir / "suspicious-workouts.json", {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "filter_criteria": {
            "duration_over_6h": "duration_minutes > 360",
            "duration_non_positive": "duration_minutes <= 0",
            "spans_multiple_days": "start.date() != end.date()",
            "iphone_idle_long": "source=iphone & active_kcal=0 & avg_hr=null & duration>180min",
        },
        "workouts": suspicious,
    })
    write_json_atomic(out_dir / "health-summary.json", summary)

    print(f"[ok] Geschreven naar {out_dir}/")
    print(f"     - health-data.json         ({len(days_out)} dagen)")
    print(f"     - workouts.json            ({len(workouts)} clean workouts)")
    print(f"     - suspicious-workouts.json ({len(suspicious)} uitgesloten)")
    print(f"     - sleep.json               ({len(sleep_sessions)} sessies)")
    print(f"     - health-summary.json")


def main():
    p = argparse.ArgumentParser(description="Parse Apple Health export.zip naar compacte JSON.")
    p.add_argument("--zip", type=Path, default=DEFAULT_EXPORT,
                   help=f"Apple Health export.zip (default: {DEFAULT_EXPORT})")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT,
                   help=f"Output directory (default: {DEFAULT_OUT})")
    args = p.parse_args()
    parse(args.zip, args.out)


if __name__ == "__main__":
    main()
