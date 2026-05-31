// Health Dashboard — v4 dashboard
// Lokaal-only, vanilla JS + Chart.js (vendored).

const COLORS = {
  blue: "#4aa8ff",
  blueFill: "rgba(74, 168, 255, 0.12)",
  green: "#4ade80",
  greenFill: "rgba(74, 222, 128, 0.12)",
  orange: "#f59e0b",
  orangeFill: "rgba(245, 158, 11, 0.14)",
  purple: "#a78bfa",
  purpleFill: "rgba(167, 139, 250, 0.14)",
  teal: "#2dd4bf",
  tealFill: "rgba(45, 212, 191, 0.14)",
  text: "#e6e8eb",
  textDim: "#8a93a3",
  border: "#232a36",
  card: "#161a22",
  red: "#f87171",
  ringMove: "#ff375f",
  ringExercise: "#a6ff43",
  ringStand: "#00c7d6",
};

const DONUT_PALETTE = [
  "#4aa8ff", "#4ade80", "#2dd4bf", "#a78bfa",
  "#60a5fa", "#34d399", "#22d3ee", "#f59e0b",
];

// ---------- Targets ----------
const TARGETS = {
  move: 500,
  exercise: 30,
  stand: 12,
  hikingGoalDate: "2026-06-29", // pas aan naar je eigen bergtocht-datum (YYYY-MM-DD)
  hikeSteps7dAvg: 10000,
  hikeFlights7dAvg: 10,
  hikeExerciseMin7dTotal: 210,
  hikeWorkouts7d: 5,
  hikeRelevantTypes: ["Walking", "Elliptical", "Rowing"],
  hikeWorkouts14d: 10,
  weekFlights: 70,
  weekExerciseMin: 210,
  weekSleepAvgMin: 420,
  hrTarget: 60,
  hrvTarget: 50,
};

// ---------- State ----------
const STATE = {
  summary: null,
  ranges: {},
  charts: {},
};

const RANGE_FIELDS = "steps,distance_km,flights,active_kcal,exercise_minutes,stand_hours,resting_hr,hrv_ms,sleep.asleep_minutes";

// ---------- SVG icons ----------
const ICONS = {
  footprints: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 16v-2.38c0-.32.07-.64.21-.92l1.78-3.57A2 2 0 0 1 7.78 8h.44a2 2 0 0 1 1.79 1.11l1.78 3.57c.14.28.21.6.21.92V16a2 2 0 0 1-4 0v-1H8v1a2 2 0 0 1-4 0Z"/><path d="M14 12v-2.38c0-.32.07-.64.21-.92l1.78-3.57A2 2 0 0 1 17.78 4h.44a2 2 0 0 1 1.79 1.11l1.78 3.57c.14.28.21.6.21.92V12a2 2 0 0 1-4 0v-1H18v1a2 2 0 0 1-4 0Z"/></svg>`,
  route: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/></svg>`,
  stairs: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 4h-4v4h-4v4H8v4H4v4h16Z"/></svg>`,
  flame: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>`,
  timer: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="10" y1="2" x2="14" y2="2"/><line x1="12" y1="14" x2="15" y2="11"/><circle cx="12" cy="14" r="8"/></svg>`,
  stand: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="4" r="2"/><path d="M12 22V8"/><path d="M8 12l4-4 4 4"/><path d="M9 22h6"/></svg>`,
  heart: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`,
  moon: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
  activity: `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
  trophy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>`,
  flame2: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>`,
  zap: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
  trending: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>`,
  trendingDown: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/></svg>`,
  mountain: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 3 4 8 5-5 5 15H2L8 3Z"/></svg>`,
  alert: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  calendar: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
  star: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  bike: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="15" r="4"/><circle cx="18" cy="15" r="4"/><path d="M6 15 9 6h4l3 9"/><path d="M9 6h2"/></svg>`,
  walk: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13" cy="4" r="2"/><path d="m15 22-3-8 3-4 1 3 4 1"/><path d="M11 14 9 22"/><path d="m9 11 3-3 3 3"/></svg>`,
  dumbbell: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6.5 6.5 11 11"/><path d="m21 21-1-1"/><path d="m3 3 1 1"/><path d="m18 22 4-4"/><path d="m2 6 4-4"/><path d="m3 10 7-7"/><path d="m14 21 7-7"/></svg>`,
};

const WORKOUT_TYPE_ICONS = {
  Walking: "walk",
  Hiking: "mountain",
  Running: "activity",
  Cycling: "bike",
  Elliptical: "activity",
  Rowing: "activity",
  Other: "dumbbell",
};

// ---------- Formatters ----------
function fmtNumber(n) {
  if (n == null || Number.isNaN(n)) return null;
  return new Intl.NumberFormat("nl-NL").format(Math.round(n));
}
function fmtSleep(min) {
  if (min == null) return null;
  const h = Math.floor(min / 60);
  const m = Math.round(min - h * 60);
  return `${h}u ${m}m`;
}
function fmtDate(iso, opts = {}) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("nl-NL", opts.long ? { day: "numeric", month: "short", year: "numeric" } : { day: "numeric", month: "short" });
}
function diffDays(targetIso, fromIso) {
  const a = new Date(targetIso + "T00:00:00");
  const b = new Date(fromIso + "T00:00:00");
  return Math.round((a - b) / 86400000);
}

// ---------- Tiles ----------
function tile({ label, value, unit, accent, iconKey, trendHtml, sparkValues, drill }) {
  const valHtml = value == null
    ? `<span class="value empty">—</span>`
    : `<span class="value">${value}${unit ? `<span class="unit">${unit}</span>` : ""}</span>`;
  const cls = accent ? `tile accent-${accent}` : "tile";
  const icon = iconKey ? ICONS[iconKey] : "";
  const spark = sparkValues && sparkValues.length ? sparkline(sparkValues) : "";
  const drillAttr = drill ? ` data-drill="${drill}" role="button" tabindex="0"` : "";
  return `<div class="${cls}"${drillAttr}>
    <div class="tile-head">${icon}<span class="label">${label}</span></div>
    <div class="value-row">${valHtml}${trendHtml || ""}</div>
    ${spark}
  </div>`;
}

function sparkline(values) {
  const clean = values.filter(v => typeof v === "number");
  if (clean.length < 2) return "";
  const W = 100, H = 28, pad = 2;
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min || 1;
  const points = values.map((v, i) => {
    if (typeof v !== "number") return null;
    const x = pad + (i / Math.max(values.length - 1, 1)) * (W - 2 * pad);
    const y = H - pad - ((v - min) / span) * (H - 2 * pad);
    return [x, y];
  }).filter(Boolean);
  if (points.length < 2) return "";
  const linePath = "M" + points.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" L");
  const areaPath = linePath + ` L${points[points.length - 1][0].toFixed(1)},${H - pad} L${points[0][0].toFixed(1)},${H - pad} Z`;
  return `<svg class="tile-spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><path class="area" d="${areaPath}"/><path class="line" d="${linePath}"/></svg>`;
}

function stepsAccent(steps) {
  if (steps == null) return "blue";
  if (steps >= 10000) return "green";
  if (steps >= 5000) return "blue";
  return "orange";
}
function exerciseAccent(min) { if (min == null) return "blue"; return min >= 30 ? "green" : "blue"; }
function sleepAccent(min) {
  if (min == null) return "teal";
  const h = min / 60;
  if (h >= 7) return "green";
  if (h >= 6) return "teal";
  return "orange";
}

// ---------- Trends ----------
function avgRecent(series, n, excludeLast = true) {
  if (!series || !series.length) return null;
  const arr = excludeLast ? series.slice(0, -1) : series.slice();
  const recent = arr.slice(-n).map(p => p.v).filter(v => typeof v === "number");
  if (recent.length < 3) return null;
  return recent.reduce((a, b) => a + b, 0) / recent.length;
}

function sumSeries(series, lastN) {
  if (!series) return 0;
  const slice = lastN ? series.slice(-lastN) : series;
  return slice.map(p => p.v).filter(v => typeof v === "number").reduce((a, b) => a + b, 0);
}

function sumRecent(series, n) { return sumSeries(series, n); }

function avgWindow(series, startIdx, endIdx) {
  const sl = series.slice(startIdx, endIdx);
  const nums = sl.map(p => p.v).filter(v => typeof v === "number");
  if (!nums.length) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function lastValues(series, n) {
  return series.slice(-n).map(p => p.v);
}

function trendBadge(todayVal, avg, opts = {}) {
  if (todayVal == null || avg == null || avg === 0) return "";
  const pct = ((todayVal - avg) / avg) * 100;
  if (Math.abs(pct) < 3) return `<span class="trend flat">·</span>`;
  const up = pct > 0;
  const cls = `trend ${up ? "up" : "down"}${opts.invert ? " invert" : ""}`;
  const arrow = up ? "↑" : "↓";
  return `<span class="${cls}">${arrow} ${Math.abs(Math.round(pct))}%</span>`;
}

// ---------- Date badge / stale ----------
function renderDateBadge(stale) {
  const el = document.getElementById("date-badge");
  el.classList.remove("is-today", "is-mild", "is-warn");
  if (!stale) { el.textContent = "—"; return; }
  if (stale.is_today) { el.textContent = `vandaag · ${stale.latest_data_date}`; el.classList.add("is-today"); }
  else if (stale.level === "mild") { el.textContent = `${stale.days_ago} dagen geleden · ${stale.latest_data_date}`; el.classList.add("is-mild"); }
  else if (stale.level === "warn") { el.textContent = `${stale.days_ago} dagen geleden · ${stale.latest_data_date}`; el.classList.add("is-warn"); }
  else { el.textContent = `${stale.days_ago} dagen geleden · ${stale.latest_data_date}`; }
}
function renderStaleBanner(stale) {
  const el = document.getElementById("stale-banner");
  if (!stale || stale.level === "ok") return;
  el.textContent = stale.message;
  el.classList.remove("hidden");
  el.classList.add(stale.level);
}

// ---------- Activity rings (with animation) ----------
function renderRings(today) {
  const svg = document.getElementById("activity-rings");
  const cx = 100, cy = 100;
  const radii = [78, 60, 42];
  const widths = [14, 14, 14];
  const colors = [COLORS.ringMove, COLORS.ringExercise, COLORS.ringStand];
  const targets = [TARGETS.move, TARGETS.exercise, TARGETS.stand];
  const vals = [today.active_kcal || 0, today.exercise_minutes || 0, today.stand_hours || 0];
  const pcts = vals.map((v, i) => Math.min(v / targets[i], 1.1));

  const Cs = radii.map(r => 2 * Math.PI * r);

  svg.innerHTML = radii.map((r, i) => `
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${colors[i]}" stroke-opacity="0.15" stroke-width="${widths[i]}" />
    <circle id="ring-${i}" cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${colors[i]}" stroke-width="${widths[i]}"
            stroke-dasharray="0 ${Cs[i]}" stroke-linecap="round"
            transform="rotate(-90 ${cx} ${cy})" />
  `).join("");

  // Animate from 0 → target
  const start = performance.now();
  const dur = 1100;
  function step(t) {
    const e = Math.min(1, (t - start) / dur);
    const eased = 1 - Math.pow(1 - e, 3);
    radii.forEach((r, i) => {
      const dash = Cs[i] * pcts[i] * eased;
      document.getElementById(`ring-${i}`).setAttribute("stroke-dasharray", `${dash} ${Cs[i]}`);
    });
    if (e < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);

  document.getElementById("ring-move").textContent     = vals[0] ? `${fmtNumber(vals[0])} / ${TARGETS.move}` : "—";
  document.getElementById("ring-exercise").textContent = vals[1] != null ? `${fmtNumber(vals[1])} / ${TARGETS.exercise} min` : "—";
  document.getElementById("ring-stand").textContent    = vals[2] != null ? `${fmtNumber(vals[2])} / ${TARGETS.stand} u` : "—";
  document.getElementById("rings-date").textContent    = fmtDate(today.date, { long: true });
}

// ---------- Bergtocht hero card ----------
function renderHikingGoal(today, range30) {
  const days = diffDays(TARGETS.hikingGoalDate, today.date);
  document.getElementById("hike-days").textContent = days >= 0 ? days : "—";

  const stepsAvg = avgRecent(range30.series.steps, 7, false);
  const flightsAvg = avgRecent(range30.series.flights, 7, false);
  const exerciseSum7 = sumRecent(range30.series.exercise_minutes, 7);

  const goalRow = (name, current, target, fmt) => {
    const pct = target > 0 ? Math.min(100, Math.round((current / target) * 100)) : 0;
    const currentStr = current != null ? fmt(current) : "—";
    return `<div class="hike-goal">
      <div class="hike-goal-head">
        <span class="name">${name}</span>
        <span class="val">${currentStr} / ${fmt(target)}</span>
      </div>
      <div class="bar"><div class="fill" style="width: ${pct}%;"></div></div>
    </div>`;
  };

  const fmtInt = (v) => fmtNumber(v) ?? "—";
  document.getElementById("hike-goals").innerHTML = [
    goalRow("Stappen 7d-gem.",     stepsAvg,      TARGETS.hikeSteps7dAvg,         fmtInt),
    goalRow("Trappen 7d-gem.",     flightsAvg,    TARGETS.hikeFlights7dAvg,       fmtInt),
    goalRow("Beweegmin. 7d-totaal", exerciseSum7, TARGETS.hikeExerciseMin7dTotal, fmtInt),
  ].join("");
}

// ---------- Hike-relevant workout counting ----------
function isHikeRelevant(type) {
  return TARGETS.hikeRelevantTypes.includes(type);
}

function countHikeWorkoutsInLastDays(byDate, endIso, days) {
  const end = new Date(endIso + "T00:00:00");
  let n = 0;
  for (let i = 0; i < days; i++) {
    const d = new Date(end);
    d.setDate(end.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    const list = byDate[iso] || [];
    n += list.filter(w => isHikeRelevant(w.type)).length;
  }
  return n;
}

function countWorkoutsInLastDays(byDate, endIso, days) {
  const end = new Date(endIso + "T00:00:00");
  let n = 0;
  for (let i = 0; i < days; i++) {
    const d = new Date(end);
    d.setDate(end.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    n += (byDate[iso] || []).length;
  }
  return n;
}

// ---------- Bergtocht Coach: readiness + todos ----------
function calculateReadiness(summary, range30) {
  const endIso = summary.today.date;
  const byDate = summary.workouts_by_date_90d || {};

  // Workout component (50%)
  const hike14d = countHikeWorkoutsInLastDays(byDate, endIso, 14);
  const exerciseAvg7 = avgRecent(range30.series.exercise_minutes, 7, false) ?? 0;
  const flightsTot7 = sumRecent(range30.series.flights, 7);

  const wHike = Math.min(hike14d / TARGETS.hikeWorkouts14d, 1);
  const wExer = Math.min(exerciseAvg7 / TARGETS.exercise, 1);
  const wFlig = Math.min(flightsTot7 / TARGETS.weekFlights, 1);
  const workout = wHike * 0.5 + wExer * 0.25 + wFlig * 0.25;

  // Recovery component (50%)
  const hrAvg7 = avgRecent(range30.series.resting_hr, 7, false);
  const hrvAvg7 = avgRecent(range30.series.hrv_ms, 7, false);
  const sleepAvg7 = avgRecent(range30.series["sleep.asleep_minutes"], 7, false);

  const rHr = hrAvg7 ? Math.min(TARGETS.hrTarget / hrAvg7, 1) : 0.5;
  const rHrv = hrvAvg7 ? Math.min(hrvAvg7 / TARGETS.hrvTarget, 1) : 0.5;
  const rSlp = sleepAvg7 ? Math.min(sleepAvg7 / TARGETS.weekSleepAvgMin, 1) : 0.5;
  // If HRV missing, redistribute its weight to HR/sleep
  const recovery = hrvAvg7 != null
    ? (rHr * 0.35 + rHrv * 0.35 + rSlp * 0.30)
    : (rHr * 0.55 + rSlp * 0.45);

  const total = ((workout + recovery) / 2) * 100;
  return {
    score: Math.round(total),
    workoutPct: Math.round(workout * 100),
    recoveryPct: Math.round(recovery * 100),
    breakdown: {
      hike: { val: hike14d, target: TARGETS.hikeWorkouts14d, pct: Math.round(wHike * 100) },
      exercise: { val: Math.round(exerciseAvg7), target: TARGETS.exercise, pct: Math.round(wExer * 100) },
      flights: { val: Math.round(flightsTot7), target: TARGETS.weekFlights, pct: Math.round(wFlig * 100) },
      hr: { val: hrAvg7 ? Math.round(hrAvg7) : null, target: TARGETS.hrTarget, pct: Math.round(rHr * 100) },
      hrv: { val: hrvAvg7 ? Math.round(hrvAvg7) : null, target: TARGETS.hrvTarget, pct: Math.round(rHrv * 100) },
      sleep: { val: sleepAvg7, target: TARGETS.weekSleepAvgMin, pct: Math.round(rSlp * 100) },
    },
  };
}

function miniRing(pct, color) {
  const r = 11, cx = 14, cy = 14, C = 2 * Math.PI * r;
  const p = Math.max(0, Math.min(100, pct));
  const dash = (p / 100) * C;
  return `<svg class="mini-ring" viewBox="0 0 28 28" aria-hidden="true">
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${COLORS.border}" stroke-width="3"/>
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="3"
      stroke-linecap="round" stroke-dasharray="${dash.toFixed(1)} ${(C - dash).toFixed(1)}"
      transform="rotate(-90 ${cx} ${cy})"/>
    <text x="${cx}" y="${cy + 3}" text-anchor="middle" font-size="9" fill="${COLORS.textDim}" font-family="ui-sans-serif,system-ui,sans-serif">${Math.round(p)}</text>
  </svg>`;
}

function renderReadiness(rd) {
  // Gauge: circular arc from -135° to +135° (270° total)
  const svg = document.getElementById("readiness-gauge");
  const cx = 80, cy = 80, r = 64;
  const startAngle = -225;
  const endAngle = 45;
  const sweep = endAngle - startAngle;

  function arc(angleStart, angleEnd, color, width, opacity = 1) {
    const rad = (a) => (a * Math.PI) / 180;
    const x1 = cx + r * Math.cos(rad(angleStart));
    const y1 = cy + r * Math.sin(rad(angleStart));
    const x2 = cx + r * Math.cos(rad(angleEnd));
    const y2 = cy + r * Math.sin(rad(angleEnd));
    const large = (angleEnd - angleStart) > 180 ? 1 : 0;
    return `<path d="M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}" stroke="${color}" stroke-width="${width}" stroke-linecap="round" fill="none" opacity="${opacity}"/>`;
  }

  const pct = Math.max(0, Math.min(rd.score, 100)) / 100;
  const valueEnd = startAngle + sweep * pct;
  const color = rd.score >= 75 ? COLORS.green : rd.score >= 50 ? COLORS.teal : rd.score >= 30 ? COLORS.orange : "#f87171";

  svg.innerHTML =
    arc(startAngle, endAngle, COLORS.border, 12, 1) +
    arc(startAngle, valueEnd, color, 12, 1);

  // Animate score number
  animateNumber("gauge-score", 0, rd.score, 1100);

  // Breakdown bars
  const bd = rd.breakdown;
  const rows = [
    { name: "Hike-workouts 14d", val: `${bd.hike.val} / ${bd.hike.target}`, pct: bd.hike.pct, cls: "fill-workout" },
    { name: "Beweegmin. 7d-gem.", val: `${bd.exercise.val} / ${bd.exercise.target} min`, pct: bd.exercise.pct, cls: "fill-workout" },
    { name: "Trappen 7d-totaal", val: `${bd.flights.val} / ${bd.flights.target}`, pct: bd.flights.pct, cls: "fill-workout" },
    { name: "Rust-HR 7d-gem.", val: bd.hr.val ? `${bd.hr.val} bpm` : "—", pct: bd.hr.pct, cls: "fill-recovery" },
    bd.hrv.val ? { name: "HRV 7d-gem.", val: `${bd.hrv.val} ms`, pct: bd.hrv.pct, cls: "fill-recovery" } : null,
    { name: "Slaap 7d-gem.", val: bd.sleep.val ? fmtSleep(bd.sleep.val) : "—", pct: bd.sleep.pct, cls: "fill-recovery" },
  ].filter(Boolean);

  document.getElementById("readiness-breakdown").innerHTML = rows.map(r => `
    <div class="bd-row">
      <div class="bd-head"><span class="name">${r.name}</span><span class="val">${r.val}</span></div>
      <div class="bd-bar"><div class="bd-fill ${r.cls}" style="width: ${r.pct}%;"></div></div>
    </div>`).join("");

  // Wat gaat goed / Aandacht — top-3 + top-2 op basis van pct
  const factors = rows.map(r => ({ name: r.name, val: r.val, pct: r.pct }));
  const good = factors.filter(f => f.pct >= 75).sort((a, b) => b.pct - a.pct).slice(0, 3);
  const attention = factors.filter(f => f.pct < 75).sort((a, b) => a.pct - b.pct).slice(0, 2);

  const ringColor = (p) => p >= 75 ? COLORS.green : p >= 50 ? COLORS.teal : p >= 30 ? COLORS.orange : COLORS.red || "#f87171";
  const renderList = (items, emptyText) => items.length
    ? items.map(f => `<li>${miniRing(f.pct, ringColor(f.pct))}<span class="factor-text">${shortFactorName(f.name)} <span class="qty">${f.val}</span></span></li>`).join("")
    : `<li style="color: var(--text-faint);">${emptyText}</li>`;

  document.getElementById("readiness-good").innerHTML = renderList(good, "Nog niets boven 75%");
  document.getElementById("readiness-attention").innerHTML = renderList(attention, "Alles op niveau");
}

function shortFactorName(name) {
  return name
    .replace("7d-gem.", "").replace("7d-totaal", "(week)").replace("14d", "(2w)")
    .replace("Hike-workouts ", "Hike-workouts ").trim();
}

function animateNumber(id, from, to, dur) {
  const el = document.getElementById(id);
  const start = performance.now();
  function step(t) {
    const e = Math.min(1, (t - start) / dur);
    const eased = 1 - Math.pow(1 - e, 3);
    el.textContent = Math.round(from + (to - from) * eased);
    if (e < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function renderWeekTodos(summary, range30) {
  const endIso = summary.today.date;
  const byDate = summary.workouts_by_date_90d || {};
  const hikeThis = countHikeWorkoutsInLastDays(byDate, endIso, 7);
  const flightsThis = sumRecent(range30.series.flights, 7);
  const sleepAvg7 = avgRecent(range30.series["sleep.asleep_minutes"], 7, false);
  const hrAvg7 = avgRecent(range30.series.resting_hr, 7, false);

  // Focus richting Bergtocht: hiking, trappen, slaap, herstel
  const todos = [
    { name: "Hike-workouts",   val: hikeThis,                              target: TARGETS.hikeWorkouts7d,    fmt: (v) => `${v}`,          critical: true },
    { name: "Trappen",         val: Math.round(flightsThis),               target: TARGETS.weekFlights,        fmt: (v) => `${v}`,          critical: true },
    { name: "Slaap (7d-gem.)", val: sleepAvg7 ? Math.round(sleepAvg7) : 0, target: TARGETS.weekSleepAvgMin,    fmt: (v) => fmtSleep(v),     critical: true },
    { name: "Rust-HR (7d-gem.)", val: hrAvg7 ? Math.round(hrAvg7) : 0,     target: TARGETS.hrTarget,           fmt: (v) => `${v} bpm`,      critical: false, lowerIsBetter: true },
  ];

  const sevenAgo = new Date(endIso + "T00:00:00");
  sevenAgo.setDate(sevenAgo.getDate() - 6);
  document.getElementById("todos-window").textContent = `${fmtDate(sevenAgo.toISOString().slice(0, 10))} → ${fmtDate(endIso)}`;

  function priorityFor(t) {
    const pct = t.lowerIsBetter
      ? (t.val > 0 ? Math.min(100, Math.round((t.target / t.val) * 100)) : 0)
      : Math.min(100, Math.round((t.val / t.target) * 100));
    if (pct >= 100) return { tag: "done", label: "Gehaald", pct };
    if (pct >= 85)  return { tag: "low",  label: "Laag",    pct };
    if (pct >= 50)  return { tag: "mid",  label: "Middel",  pct };
    return { tag: t.critical ? "high" : "mid", label: t.critical ? "Hoog" : "Middel", pct };
  }

  // Sorteer: hoog → middel → laag → gehaald
  const order = { high: 0, mid: 1, low: 2, done: 3 };
  const annotated = todos.map(t => ({ t, p: priorityFor(t) }));
  annotated.sort((a, b) => order[a.p.tag] - order[b.p.tag]);

  document.getElementById("todos-list").innerHTML = annotated.map(({ t, p }) => {
    const done = p.tag === "done";
    return `<li class="todo-item ${done ? "done" : ""}">
      <span class="todo-check"></span>
      <span class="todo-text">${t.name}</span>
      <span class="todo-progress">${t.fmt(t.val)} / ${t.fmt(t.target)} · ${p.pct}%</span>
      <span class="todo-priority ${p.tag}">${p.label}</span>
    </li>`;
  }).join("");
}

// ---------- Insights "Dit valt op" ----------
function generateInsights(summary, range30, range90) {
  const out = [];
  const today = summary.today;
  const series = range30.series;
  const byDate = summary.workouts_by_date_90d || {};

  // 1. Rust-HR trend (eerste 7d vs laatste 7d in 30d window)
  const hrFirst = avgWindow(series.resting_hr, 0, 7);
  const hrLast = avgWindow(series.resting_hr, -7);
  if (hrFirst && hrLast) {
    const delta = hrLast - hrFirst;
    if (Math.abs(delta) >= 2) {
      const down = delta < 0;
      out.push({
        tone: down ? "positive" : "negative",
        iconKey: down ? "heart" : "alert",
        title: `Rust-HR ${down ? "gedaald" : "gestegen"} met ${Math.abs(delta).toFixed(1)} bpm`,
        detail: `Over 30 dagen: ${Math.round(hrFirst)} → ${Math.round(hrLast)} bpm. ${down ? "Conditie verbetert." : "Mogelijk vermoeidheid of stress."}`,
        impact: Math.abs(delta),
      });
    }
  }

  // 2. HRV trend
  const hrvFirst = avgWindow(series.hrv_ms, 0, 7);
  const hrvLast = avgWindow(series.hrv_ms, -7);
  if (hrvFirst && hrvLast) {
    const delta = hrvLast - hrvFirst;
    if (Math.abs(delta) >= 3) {
      const up = delta > 0;
      out.push({
        tone: up ? "positive" : "negative",
        iconKey: up ? "trending" : "trendingDown",
        title: `HRV ${up ? "verbeterd" : "gedaald"} met ${Math.abs(delta).toFixed(0)} ms`,
        detail: `Over 30 dagen: ${Math.round(hrvFirst)} → ${Math.round(hrvLast)} ms. ${up ? "Goede herstelcapaciteit." : "Mogelijk overbelasting."}`,
        impact: Math.abs(delta),
      });
    }
  }

  // 3. Stappen vs Bergtocht-doel
  const stepsAvg7 = avgRecent(series.steps, 7, false);
  if (stepsAvg7) {
    const ratio = stepsAvg7 / TARGETS.hikeSteps7dAvg;
    if (ratio >= 1.1) {
      out.push({
        tone: "positive", iconKey: "mountain",
        title: `Stappen-gem. ligt ${Math.round((ratio - 1) * 100)}% boven Bergtocht-doel`,
        detail: `${fmtNumber(stepsAvg7)} stappen/dag (doel ${fmtNumber(TARGETS.hikeSteps7dAvg)}). Goede basis voor lange dagen op pad.`,
        impact: (ratio - 1) * 100,
      });
    } else if (ratio < 0.7) {
      out.push({
        tone: "negative", iconKey: "alert",
        title: `Stappen-gem. ligt ${Math.round((1 - ratio) * 100)}% onder doel`,
        detail: `${fmtNumber(stepsAvg7)} stappen/dag (doel ${fmtNumber(TARGETS.hikeSteps7dAvg)}). Tijd om volume op te bouwen.`,
        impact: (1 - ratio) * 100,
      });
    }
  }

  // 4. Workout-pauze laatste 30d
  const endIso = today.date;
  const end = new Date(endIso + "T00:00:00");
  let lastWorkoutDate = null;
  for (let i = 0; i <= 30; i++) {
    const d = new Date(end);
    d.setDate(end.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    if ((byDate[iso] || []).length > 0) { lastWorkoutDate = iso; break; }
  }
  if (lastWorkoutDate) {
    const gap = diffDays(endIso, lastWorkoutDate);
    if (gap >= 3) {
      out.push({
        tone: gap >= 5 ? "negative" : "neutral",
        iconKey: "calendar",
        title: `${gap} dagen geen workout`,
        detail: `Laatste sessie op ${fmtDate(lastWorkoutDate)}. Tip: een lichte walk of elliptical houdt momentum vast.`,
        impact: gap * 5,
      });
    }
  }

  // 5. Best weekday vs worst (90d)
  const wdBuckets = [[], [], [], [], [], [], []];
  for (const p of range90.series.steps) {
    if (typeof p.v !== "number") continue;
    const d = new Date(p.date + "T00:00:00");
    wdBuckets[(d.getDay() + 6) % 7].push(p.v);
  }
  const wdAvg = wdBuckets.map(b => b.length ? b.reduce((a, x) => a + x, 0) / b.length : 0);
  const wdNames = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"];
  let bestI = 0, worstI = 0;
  for (let i = 1; i < 7; i++) { if (wdAvg[i] > wdAvg[bestI]) bestI = i; if (wdAvg[i] < wdAvg[worstI]) worstI = i; }
  if (wdAvg[bestI] > 0 && wdAvg[worstI] > 0) {
    const ratio = wdAvg[bestI] / wdAvg[worstI];
    if (ratio >= 1.4) {
      out.push({
        tone: "info", iconKey: "calendar",
        title: `${capitalize(wdNames[bestI])} is je sterkste dag`,
        detail: `${fmtNumber(wdAvg[bestI])} stappen gem. (${Math.round((ratio - 1) * 100)}% meer dan ${wdNames[worstI]}).`,
        impact: (ratio - 1) * 50,
      });
    }
  }

  // 6. Recente 10k-streak
  const stepsSeries = range30.series.steps;
  let curStreak = 0;
  for (let i = stepsSeries.length - 1; i >= 0; i--) {
    if (typeof stepsSeries[i].v === "number" && stepsSeries[i].v >= 10000) curStreak++;
    else break;
  }
  if (curStreak >= 3) {
    out.push({
      tone: "positive", iconKey: "zap",
      title: `${curStreak} dagen ≥ 10.000 stappen op rij`,
      detail: `Lekker bezig. Houd dit tempo vast richting Bergtocht.`,
      impact: curStreak * 8,
    });
  }

  // 7. Slaap consistency (std dev last 7d sleep)
  const sleepLast7 = lastValues(series["sleep.asleep_minutes"], 7).filter(v => typeof v === "number");
  if (sleepLast7.length >= 5) {
    const mean = sleepLast7.reduce((a, b) => a + b, 0) / sleepLast7.length;
    const variance = sleepLast7.reduce((a, b) => a + (b - mean) ** 2, 0) / sleepLast7.length;
    const std = Math.sqrt(variance);
    if (std <= 30 && mean >= 360) {
      out.push({
        tone: "positive", iconKey: "moon",
        title: "Slaap is heel consistent",
        detail: `Spreiding < 30 min over 7 dagen, gem. ${fmtSleep(mean)}. Goede basis voor herstel.`,
        impact: 20,
      });
    } else if (std >= 75) {
      out.push({
        tone: "neutral", iconKey: "moon",
        title: "Slaap is wisselend",
        detail: `Spreiding ${Math.round(std)} min over 7 dagen. Vaste bedtijden helpen je herstel.`,
        impact: 15,
      });
    }
  }

  // 8. Hike-workouts deze week vs vorige week
  const hike7 = countHikeWorkoutsInLastDays(byDate, today.date, 7);
  const hike14 = countHikeWorkoutsInLastDays(byDate, today.date, 14);
  const hikePrev = hike14 - hike7;
  if (hike7 > hikePrev && hike7 >= 3) {
    out.push({
      tone: "positive", iconKey: "mountain",
      title: `${hike7} hike-workouts deze week (+${hike7 - hikePrev})`,
      detail: `Walking/Elliptical/Rowing trekt aan — precies de mix voor Bergtocht.`,
      impact: hike7 * 7,
    });
  }

  // Sort by impact and take top 5
  out.sort((a, b) => b.impact - a.impact);
  return out.slice(0, 5);
}

function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

function renderInsights(insights) {
  if (!insights.length) {
    document.getElementById("insights-section").style.display = "none";
    return;
  }
  document.getElementById("insights-grid").innerHTML = insights.map(ins => `
    <div class="insight-card tone-${ins.tone}">
      <div class="icon-wrap">${ICONS[ins.iconKey] || ICONS.activity}</div>
      <div class="body">
        <span class="title">${ins.title}</span>
        <span class="detail">${ins.detail}</span>
      </div>
    </div>`).join("");
}

// ---------- Today tiles (with sparklines) ----------
function renderToday(today, trends, range30) {
  const s = range30.series;
  const lastN = (key, n) => lastValues(s[key], n);
  const t = trends || {};
  const sleepMin = today.sleep ? today.sleep.asleep_minutes : null;
  const hrvVal = today.hrv_ms;

  const beweging = [
    tile({ label: "Stappen", value: fmtNumber(today.steps), accent: stepsAccent(today.steps), iconKey: "footprints",
      trendHtml: trendBadge(today.steps, t.steps), sparkValues: lastN("steps", 14), drill: "steps" }),
    tile({ label: "Afstand", value: today.distance_km != null ? today.distance_km.toFixed(1) : null, unit: " km", accent: "blue", iconKey: "route",
      trendHtml: trendBadge(today.distance_km, t.distance_km), sparkValues: lastN("distance_km", 14), drill: "distance_km" }),
    tile({ label: "Trappen", value: fmtNumber(today.flights), accent: "blue", iconKey: "stairs",
      trendHtml: trendBadge(today.flights, t.flights), sparkValues: lastN("flights", 14), drill: "flights" }),
  ].join("");

  const training = [
    tile({ label: "Actieve kcal", value: fmtNumber(today.active_kcal), accent: "orange", iconKey: "flame",
      trendHtml: trendBadge(today.active_kcal, t.active_kcal), sparkValues: lastN("active_kcal", 14), drill: "active_kcal" }),
    tile({ label: "Beweegmin.", value: fmtNumber(today.exercise_minutes), unit: " min", accent: exerciseAccent(today.exercise_minutes), iconKey: "timer",
      trendHtml: trendBadge(today.exercise_minutes, t.exercise_minutes), sparkValues: lastN("exercise_minutes", 14), drill: "exercise_minutes" }),
    tile({ label: "Sta-uren", value: fmtNumber(today.stand_hours), accent: "blue", iconKey: "stand",
      trendHtml: trendBadge(today.stand_hours, t.stand_hours), sparkValues: lastN("stand_hours", 14), drill: "stand_hours" }),
  ].join("");

  const herstel = [
    tile({ label: "Rust-HR", value: fmtNumber(today.resting_hr), unit: " bpm", accent: "purple", iconKey: "heart",
      trendHtml: trendBadge(today.resting_hr, t.resting_hr, { invert: true }), sparkValues: lastN("resting_hr", 14), drill: "resting_hr" }),
    tile({ label: "HRV", value: hrvVal != null ? Math.round(hrvVal) : null, unit: " ms", accent: "purple", iconKey: "activity",
      trendHtml: trendBadge(hrvVal, t.hrv), sparkValues: lastN("hrv_ms", 14), drill: "hrv_ms" }),
    tile({ label: "Slaap", value: fmtSleep(sleepMin), accent: sleepAccent(sleepMin), iconKey: "moon",
      trendHtml: trendBadge(sleepMin, t.sleep), sparkValues: lastN("sleep.asleep_minutes", 14), drill: "sleep.asleep_minutes" }),
  ].join("");

  document.getElementById("tiles-beweging").innerHTML = beweging;
  document.getElementById("tiles-training").innerHTML = training;
  document.getElementById("tiles-herstel").innerHTML = herstel;
}

// ---------- Overview (7/30 totals) ----------
function renderOverview(summary, range30) {
  const endIso = summary.today.date;
  const byDate = summary.workouts_by_date_90d || {};

  const stats = [
    { label: "Stappen 7d",   value: sumSeries(range30.series.steps, 7),               prev: sumSeries(range30.series.steps.slice(0, -7), 7),               fmt: fmtNumber },
    { label: "Stappen 30d",  value: sumSeries(range30.series.steps),                  prev: null, fmt: fmtNumber },
    { label: "Afstand 7d",   value: sumSeries(range30.series.distance_km, 7),         prev: sumSeries(range30.series.distance_km.slice(0, -7), 7),         fmt: (v) => v.toFixed(1) + " km" },
    { label: "Afstand 30d",  value: sumSeries(range30.series.distance_km),            prev: null, fmt: (v) => v.toFixed(1) + " km" },
    { label: "Kcal 7d",      value: sumSeries(range30.series.active_kcal, 7),         prev: sumSeries(range30.series.active_kcal.slice(0, -7), 7),         fmt: fmtNumber },
    { label: "Beweegmin. 7d", value: sumSeries(range30.series.exercise_minutes, 7),   prev: sumSeries(range30.series.exercise_minutes.slice(0, -7), 7),    fmt: (v) => fmtNumber(v) + " min" },
    { label: "Workouts 7d",  value: countWorkoutsInLastDays(byDate, endIso, 7),       prev: countWorkoutsInLastDays(byDate, endIso, 14) - countWorkoutsInLastDays(byDate, endIso, 7), fmt: (v) => v.toString() },
    { label: "Workouts 30d", value: countWorkoutsInLastDays(byDate, endIso, 30),      prev: null, fmt: (v) => v.toString() },
  ];

  const html = stats.map(s => {
    let subHtml = "";
    if (s.prev != null && s.prev > 0) {
      const pct = ((s.value - s.prev) / s.prev) * 100;
      const cls = pct >= 0 ? "up" : "down";
      const arrow = pct >= 0 ? "↑" : "↓";
      subHtml = `<div class="ov-sub"><span>vorige periode</span><span class="delta ${cls}">${arrow} ${Math.abs(Math.round(pct))}%</span></div>`;
    }
    return `<div class="ov-card">
      <div class="ov-label">${s.label}</div>
      <div class="ov-value">${s.fmt(s.value)}</div>
      ${subHtml}
    </div>`;
  }).join("");
  document.getElementById("overview-grid").innerHTML = html;
}

// ---------- Year-over-year ----------
function renderYoY(summary, range365) {
  // last 30 days vs same 30 days a year ago (first 30 entries of 365d range)
  const now30 = (key) => range365.series[key].slice(-30);
  const then30 = (key) => range365.series[key].slice(0, 30);
  const sumKey = (key, slice) => slice.map(p => p.v).filter(v => typeof v === "number").reduce((a, b) => a + b, 0);

  const byDate365 = summary.workouts_by_date_365d || {};
  const endIso = summary.today.date;
  const oneYearAgoIso = new Date(new Date(endIso + "T00:00:00").getTime() - 364 * 86400000).toISOString().slice(0, 10);

  function countWorkoutsInWindow(byDate, startIso, days) {
    const start = new Date(startIso + "T00:00:00");
    let n = 0;
    for (let i = 0; i < days; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      const iso = d.toISOString().slice(0, 10);
      n += (byDate[iso] || []).length;
    }
    return n;
  }

  const items = [
    { label: "Stappen 30d", now: sumKey("steps", now30("steps")), then: sumKey("steps", then30("steps")), fmt: fmtNumber },
    { label: "Afstand 30d", now: sumKey("distance_km", now30("distance_km")), then: sumKey("distance_km", then30("distance_km")), fmt: (v) => v.toFixed(0) + " km" },
    { label: "Kcal 30d", now: sumKey("active_kcal", now30("active_kcal")), then: sumKey("active_kcal", then30("active_kcal")), fmt: fmtNumber },
    { label: "Beweegmin. 30d", now: sumKey("exercise_minutes", now30("exercise_minutes")), then: sumKey("exercise_minutes", then30("exercise_minutes")), fmt: (v) => fmtNumber(v) + " min" },
    { label: "Trappen 30d", now: sumKey("flights", now30("flights")), then: sumKey("flights", then30("flights")), fmt: fmtNumber },
    { label: "Workouts 30d",
      now: countWorkoutsInWindow(byDate365, new Date(new Date(endIso + "T00:00:00").getTime() - 29 * 86400000).toISOString().slice(0, 10), 30),
      then: countWorkoutsInWindow(byDate365, oneYearAgoIso, 30),
      fmt: (v) => v.toString() },
  ];

  const html = items.map(it => {
    let deltaHtml = `<span class="yoy-delta flat">·</span>`;
    if (it.then > 0) {
      const pct = ((it.now - it.then) / it.then) * 100;
      const cls = Math.abs(pct) < 3 ? "flat" : (pct >= 0 ? "up" : "down");
      const arrow = pct >= 0 ? "↑" : "↓";
      deltaHtml = `<span class="yoy-delta ${cls}">${arrow} ${Math.abs(Math.round(pct))}%</span>`;
    } else if (it.now > 0) {
      deltaHtml = `<span class="yoy-delta up">nieuw</span>`;
    }
    return `<div class="yoy-card">
      <div class="yoy-label">${it.label}</div>
      <div class="yoy-now">${it.fmt(it.now)}</div>
      <div class="yoy-then">vorig jaar: ${it.fmt(it.then)}</div>
      ${deltaHtml}
    </div>`;
  }).join("");
  document.getElementById("yoy-grid").innerHTML = html;
}

// ---------- Records & streaks ----------
function findMax(series) {
  let best = null;
  for (const p of series) {
    if (typeof p.v === "number" && (!best || p.v > best.v)) best = p;
  }
  return best;
}
function longestStreakAtLeast(series, threshold) {
  let cur = 0, best = 0, endDate = null, curEnd = null;
  for (const p of series) {
    if (typeof p.v === "number" && p.v >= threshold) {
      cur++; curEnd = p.date;
      if (cur > best) { best = cur; endDate = curEnd; }
    } else cur = 0;
  }
  return { length: best, endDate };
}

function renderRecords(range365, summary) {
  const stepsBest = findMax(range365.series.steps);
  const distBest = findMax(range365.series.distance_km);
  const kcalBest = findMax(range365.series.active_kcal);
  const flightsBest = findMax(range365.series.flights);
  const streak10k = longestStreakAtLeast(range365.series.steps, 10000);

  const totalKm = sumSeries(range365.series.distance_km);
  const totalSteps = sumSeries(range365.series.steps);
  const totalWorkouts = Object.values(summary.workouts_by_date_365d || {}).reduce((a, l) => a + l.length, 0);

  const card = (accent, iconKey, name, value, sub) => `
    <div class="record-card accent-${accent}">
      <div class="icon-wrap">${ICONS[iconKey]}</div>
      <div class="meta">
        <span class="name">${name}</span>
        <span class="value">${value}</span>
        ${sub ? `<span class="sub">${sub}</span>` : ""}
      </div>
    </div>`;

  document.getElementById("records-grid").innerHTML = [
    card("green",  "trophy",   "Beste stappendag",   stepsBest ? fmtNumber(stepsBest.v) : "—", stepsBest ? fmtDate(stepsBest.date) : ""),
    card("blue",   "zap",      "Langste 10k-streak", streak10k.length ? `${streak10k.length} dagen` : "—", streak10k.endDate ? `t/m ${fmtDate(streak10k.endDate)}` : ""),
    card("teal",   "route",    "Verste dag",         distBest ? distBest.v.toFixed(1) + " km" : "—", distBest ? fmtDate(distBest.date) : ""),
    card("orange", "flame2",   "Heetste dag (kcal)", kcalBest ? fmtNumber(kcalBest.v) + " kcal" : "—", kcalBest ? fmtDate(kcalBest.date) : ""),
    card("purple", "mountain", "Hoogste klim",       flightsBest ? fmtNumber(flightsBest.v) + " trappen" : "—", flightsBest ? fmtDate(flightsBest.date) : ""),
    card("blue",   "trending", "Totaal jaar",        `${fmtNumber(totalKm)} km`, `${fmtNumber(totalSteps)} stappen · ${totalWorkouts} workouts`),
  ].join("");
}

// ---------- Heatmap with hike-tint + click popover ----------
function renderHeatmap(summary) {
  const byDate = summary.workouts_by_date_365d || {};
  const endIso = summary.today.date;
  const end = new Date(endIso + "T00:00:00");
  const days = 364;

  const cells = [];
  for (let i = days; i >= 0; i--) {
    const d = new Date(end);
    d.setDate(end.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    const list = byDate[iso] || [];
    const hikeCount = list.filter(w => isHikeRelevant(w.type)).length;
    cells.push({ date: iso, count: list.length, hike: hikeCount, weekday: d.getDay() });
  }

  const dayIndex = (jsDay) => (jsDay + 6) % 7;
  const leading = dayIndex(new Date(cells[0].date + "T00:00:00").getDay());

  const html = [];
  for (let i = 0; i < leading; i++) html.push(`<div class="cell spacer"></div>`);
  for (const c of cells) {
    let lvl = 0;
    if (c.count >= 4) lvl = 4; else if (c.count === 3) lvl = 3; else if (c.count === 2) lvl = 2; else if (c.count === 1) lvl = 1;
    // Hike-tinted if hike-workouts make up majority
    const hikeTint = c.hike > 0 && c.hike >= c.count / 2 ? ` hike-tinted-${lvl}` : "";
    const cls = lvl === 0 ? "lvl-0" : `lvl-${lvl}${hikeTint}`;
    html.push(`<div class="cell ${cls}" data-date="${c.date}" data-count="${c.count}" data-hike="${c.hike}"></div>`);
  }
  document.getElementById("heatmap").innerHTML = html.join("");

  // Click handler for popover
  const heatmapEl = document.getElementById("heatmap");
  const popoverEl = document.getElementById("heatmap-popover");
  heatmapEl.addEventListener("click", (e) => {
    const cell = e.target.closest(".cell");
    if (!cell || cell.classList.contains("spacer")) { hidePopover(); return; }
    const date = cell.dataset.date;
    if (!date) return;
    const list = byDate[date] || [];
    if (list.length === 0) {
      popoverEl.innerHTML = `<div class="hp-date">${fmtDate(date, { long: true })}</div><div style="color: var(--text-dim);">Geen workouts</div>`;
    } else {
      popoverEl.innerHTML = `
        <div class="hp-date">${fmtDate(date, { long: true })}</div>
        <ul>${list.map(w => `<li>
          <span class="hp-type">${isHikeRelevant(w.type) ? "▸ " : ""}${w.type}</span>
          <span class="hp-meta">${w.duration_min.toFixed(0)} min${w.distance_km > 0 ? ` · ${w.distance_km.toFixed(1)} km` : ""}</span>
        </li>`).join("")}</ul>`;
    }
    const rect = cell.getBoundingClientRect();
    const containerRect = heatmapEl.parentElement.getBoundingClientRect();
    const top = rect.top - containerRect.top + 20;
    const left = Math.min(rect.left - containerRect.left, containerRect.width - 240);
    popoverEl.style.top = top + "px";
    popoverEl.style.left = Math.max(8, left) + "px";
    popoverEl.classList.remove("hidden");
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#heatmap") && !e.target.closest("#heatmap-popover")) hidePopover();
  });
  function hidePopover() { popoverEl.classList.add("hidden"); }
}

// ---------- Chart defaults ----------
function commonScales() {
  return {
    x: { ticks: { color: COLORS.textDim, maxRotation: 0, autoSkipPadding: 16, font: { size: 11 } }, grid: { color: COLORS.border, drawBorder: false } },
    y: { beginAtZero: true, ticks: { color: COLORS.textDim, font: { size: 11 } }, grid: { color: COLORS.border, drawBorder: false } },
  };
}
function commonPlugins(labelFormatter) {
  return {
    legend: { labels: { color: COLORS.textDim, boxWidth: 12, font: { size: 11 } } },
    tooltip: { backgroundColor: COLORS.card, borderColor: COLORS.border, borderWidth: 1, titleColor: COLORS.text, bodyColor: COLORS.text, padding: 10, cornerRadius: 8,
      callbacks: labelFormatter ? { label: labelFormatter } : undefined },
  };
}
function destroyChart(name) { if (STATE.charts[name]) { STATE.charts[name].destroy(); STATE.charts[name] = null; } }

// ---------- Charts ----------
function makeStepsChart(rangePayload) {
  destroyChart("steps");
  const ctx = document.getElementById("steps-chart").getContext("2d");
  const labels = rangePayload.series.steps.map(p => p.date.slice(5));
  const values = rangePayload.series.steps.map(p => p.v);
  const rolling = rangePayload.rolling_means.steps_7d || [];
  const rollingByDate = new Map(rolling.map(p => [p.date, p.v]));
  const rollingValues = rangePayload.series.steps.map(p => rollingByDate.get(p.date) ?? null);
  // Bergtocht goal line
  const goalValues = values.map(() => TARGETS.hikeSteps7dAvg);

  STATE.charts.steps = new Chart(ctx, {
    type: "line",
    data: { labels, datasets: [
      { label: "Stappen", data: values, borderColor: COLORS.blue, backgroundColor: COLORS.blueFill, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 5 },
      { label: "7d-gemiddelde", data: rollingValues, borderColor: COLORS.green, borderWidth: 1.5, borderDash: [4, 3], fill: false, tension: 0.3, pointRadius: 0, spanGaps: true },
      { label: `Doel ${fmtNumber(TARGETS.hikeSteps7dAvg)}`, data: goalValues, borderColor: "rgba(167, 139, 250, 0.6)", borderWidth: 1, borderDash: [2, 4], fill: false, pointRadius: 0 },
    ] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, scales: commonScales(),
      plugins: commonPlugins((c) => `${c.dataset.label}: ${fmtNumber(c.parsed.y) ?? "—"}`) },
  });
}

function makeDistanceChart(rangePayload) {
  destroyChart("distance");
  const ctx = document.getElementById("distance-chart").getContext("2d");
  const labels = rangePayload.series.distance_km.map(p => p.date.slice(5));
  const values = rangePayload.series.distance_km.map(p => p.v);
  STATE.charts.distance = new Chart(ctx, {
    type: "line",
    data: { labels, datasets: [{ label: "Afstand", data: values, borderColor: COLORS.teal, backgroundColor: COLORS.tealFill, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 5 }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, scales: commonScales(),
      plugins: commonPlugins((c) => c.parsed.y != null ? `${c.dataset.label}: ${c.parsed.y.toFixed(1)} km` : `${c.dataset.label}: —`) },
  });
}

function makeFlightsChart(rangePayload) {
  destroyChart("flights");
  const ctx = document.getElementById("flights-chart").getContext("2d");
  const labels = rangePayload.series.flights.map(p => p.date.slice(5));
  const values = rangePayload.series.flights.map(p => p.v ?? 0);
  STATE.charts.flights = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ label: "Trappen", data: values, backgroundColor: "rgba(167, 139, 250, 0.45)", borderColor: COLORS.purple, borderWidth: 1.5, borderRadius: 4, borderSkipped: false }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, scales: commonScales(),
      plugins: commonPlugins((c) => `${c.dataset.label}: ${fmtNumber(c.parsed.y) ?? "—"}`) },
  });
}

function makeKcalChart(rangePayload) {
  destroyChart("kcal");
  const ctx = document.getElementById("kcal-chart").getContext("2d");
  const labels = rangePayload.series.active_kcal.map(p => p.date.slice(5));
  const values = rangePayload.series.active_kcal.map(p => p.v ?? 0);
  STATE.charts.kcal = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ label: "Actieve kcal", data: values, backgroundColor: COLORS.orangeFill, borderColor: COLORS.orange, borderWidth: 1.5, borderRadius: 4, borderSkipped: false }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, scales: commonScales(),
      plugins: commonPlugins((c) => `${c.dataset.label}: ${fmtNumber(c.parsed.y) ?? "—"} kcal`) },
  });
}

function makeHrChart(rangePayload) {
  destroyChart("hr");
  const ctx = document.getElementById("hr-chart").getContext("2d");
  const series = rangePayload.series.resting_hr || [];
  const labels = series.map(p => p.date.slice(5));
  const values = series.map(p => p.v);
  const nums = values.filter(v => typeof v === "number");
  const yMin = nums.length ? Math.max(40, Math.floor(Math.min(...nums) - 5)) : 50;
  const yMax = nums.length ? Math.ceil(Math.max(...nums) + 5) : 80;
  const scales = commonScales();
  scales.y.beginAtZero = false; scales.y.min = yMin; scales.y.max = yMax;
  STATE.charts.hr = new Chart(ctx, {
    type: "line",
    data: { labels, datasets: [{ label: "Rust-hartslag", data: values, borderColor: COLORS.purple, backgroundColor: COLORS.purpleFill, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 5, spanGaps: true }] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, scales,
      plugins: commonPlugins((c) => `${c.dataset.label}: ${c.parsed.y != null ? c.parsed.y.toFixed(0) + " bpm" : "—"}`) },
  });
}

function makeSleepChart(rangePayload) {
  destroyChart("sleep");
  const ctx = document.getElementById("sleep-chart").getContext("2d");
  const series = rangePayload.series["sleep.asleep_minutes"] || [];
  const labels = series.map(p => p.date.slice(5));
  const values = series.map(p => (typeof p.v === "number" ? p.v / 60 : null));
  const scales = commonScales();
  scales.y.suggestedMin = 4; scales.y.suggestedMax = 10; scales.y.beginAtZero = false;
  scales.y.ticks.callback = (val) => val + "u";
  STATE.charts.sleep = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [
      { label: "Slaap", data: values, backgroundColor: COLORS.tealFill, borderColor: COLORS.teal, borderWidth: 1.5, borderRadius: 4, borderSkipped: false },
      { label: "Doel (7u)", type: "line", data: values.map(() => 7), borderColor: COLORS.green, borderWidth: 1.2, borderDash: [4, 3], pointRadius: 0, fill: false },
    ] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, scales,
      plugins: commonPlugins((c) => {
        if (c.dataset.label === "Doel (7u)") return null;
        return c.parsed.y != null ? `${c.dataset.label}: ${fmtSleep(c.parsed.y * 60)}` : `${c.dataset.label}: —`;
      }) },
  });
}

function makeWeekdayChart(range90) {
  destroyChart("weekday");
  const ctx = document.getElementById("weekday-chart").getContext("2d");
  const buckets = [[], [], [], [], [], [], []];
  for (const p of range90.series.steps) {
    if (typeof p.v !== "number") continue;
    const d = new Date(p.date + "T00:00:00");
    buckets[(d.getDay() + 6) % 7].push(p.v);
  }
  const avg = buckets.map(b => b.length ? Math.round(b.reduce((a, x) => a + x, 0) / b.length) : 0);
  const labels = ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"];
  STATE.charts.weekday = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ label: "Stappen / weekdag", data: avg, backgroundColor: COLORS.blueFill, borderColor: COLORS.blue, borderWidth: 1.5, borderRadius: 6, borderSkipped: false }] },
    options: { responsive: true, maintainAspectRatio: false, scales: commonScales(),
      plugins: commonPlugins((c) => `${c.label}: ${fmtNumber(c.parsed.y)} gem.`) },
  });
}

function makeWorkoutFreqChart(summary) {
  destroyChart("freq");
  const ctx = document.getElementById("workout-freq-chart").getContext("2d");
  const byDate = summary.workouts_by_date_90d || {};
  const endIso = summary.today.date;
  const end = new Date(endIso + "T00:00:00");
  const weeks = 12;
  const allCounts = new Array(weeks).fill(0);
  const hikeCounts = new Array(weeks).fill(0);
  const labels = new Array(weeks);
  for (let w = weeks - 1; w >= 0; w--) {
    const weekStart = new Date(end); weekStart.setDate(end.getDate() - (w * 7) - 6);
    labels[weeks - 1 - w] = `${weekStart.getDate()}/${weekStart.getMonth() + 1}`;
    let total = 0, hike = 0;
    for (let i = 0; i < 7; i++) {
      const d = new Date(weekStart); d.setDate(weekStart.getDate() + i);
      const iso = d.toISOString().slice(0, 10);
      const list = byDate[iso] || [];
      total += list.length;
      hike += list.filter(w => isHikeRelevant(w.type)).length;
    }
    allCounts[weeks - 1 - w] = total;
    hikeCounts[weeks - 1 - w] = hike;
  }
  STATE.charts.freq = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [
      { label: "Hike-relevant", data: hikeCounts, backgroundColor: "rgba(74, 222, 128, 0.5)", borderColor: COLORS.green, borderWidth: 1.5, borderRadius: 6, borderSkipped: false, stack: "w" },
      { label: "Overig", data: allCounts.map((t, i) => t - hikeCounts[i]), backgroundColor: "rgba(138, 147, 163, 0.25)", borderColor: COLORS.textDim, borderWidth: 1, borderRadius: 6, borderSkipped: false, stack: "w" },
    ] },
    options: { responsive: true, maintainAspectRatio: false,
      scales: { x: { ...commonScales().x, stacked: true }, y: { ...commonScales().y, stacked: true } },
      plugins: commonPlugins((c) => `${c.dataset.label}: ${c.parsed.y}`) },
  });
}

// ---------- Workouts ----------
function aggregateForDonut(byType) {
  const entries = Object.entries(byType).map(([t, v]) => ({ type: t, ...v }));
  entries.sort((a, b) => b.count - a.count);
  if (entries.length <= 7) return entries;
  const top = entries.slice(0, 6);
  const rest = entries.slice(6);
  const overig = rest.reduce((acc, w) => ({ type: "Overig", count: acc.count + w.count, duration_min: acc.duration_min + w.duration_min, distance_km: acc.distance_km + w.distance_km }), { type: "Overig", count: 0, duration_min: 0, distance_km: 0 });
  return [...top, overig];
}

function colorForWorkoutType(type, idx) {
  if (type === "Overig") return COLORS.orange;
  if (isHikeRelevant(type)) return DONUT_PALETTE[idx % DONUT_PALETTE.length];
  return "rgba(138, 147, 163, 0.45)";
}

function makeWorkoutsDonut(workouts90d) {
  destroyChart("donut");
  const ctx = document.getElementById("workouts-donut").getContext("2d");
  const items = aggregateForDonut(workouts90d.by_type);
  if (items.length === 0) {
    document.getElementById("workouts-donut").replaceWith(Object.assign(document.createElement("div"), { textContent: "Geen workouts in de laatste 90 dagen", className: "tile" }));
    return;
  }
  const colors = items.map((it, i) => colorForWorkoutType(it.type, i));
  STATE.charts.donut = new Chart(ctx, {
    type: "doughnut",
    data: { labels: items.map(it => `${it.type}${isHikeRelevant(it.type) ? " ▸" : ""}`), datasets: [{ data: items.map(it => it.count), backgroundColor: colors, borderColor: COLORS.card, borderWidth: 3, hoverOffset: 6 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: "62%",
      plugins: { legend: { position: "right", labels: { color: COLORS.text, boxWidth: 12, font: { size: 12 }, padding: 10 } },
        tooltip: { backgroundColor: "#0e1116", borderColor: COLORS.border, borderWidth: 1, padding: 10, cornerRadius: 8,
          callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.parsed} workouts` } } } },
  });
}

function renderWorkoutsTable(workouts90d) {
  const items = aggregateForDonut(workouts90d.by_type);
  if (items.length === 0) {
    document.getElementById("workouts-table").innerHTML = `<div style="color: var(--text-dim);">Geen records.</div>`;
    return;
  }
  const maxCount = Math.max(...items.map(it => it.count));
  const rows = items.map(it => {
    const pct = maxCount > 0 ? Math.round((it.count / maxCount) * 100) : 0;
    const rowCls = isHikeRelevant(it.type) ? "hike-rel" : "";
    return `<tr class="${rowCls}">
      <td>${it.type}</td>
      <td class="num bar-cell" style="--bar-pct: ${pct};">${it.count}</td>
      <td class="num">${(it.duration_min / 60).toFixed(1)} u</td>
      <td class="num">${it.distance_km.toFixed(1)} km</td>
    </tr>`;
  }).join("");
  document.getElementById("workouts-table").innerHTML = `
    <table>
      <thead><tr><th>Type</th><th class="num">Aantal</th><th class="num">Duur</th><th class="num">Afstand</th></tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr><td>Totaal</td><td class="num">${workouts90d.count}</td><td></td><td></td></tr></tfoot>
    </table>
    <div style="margin-top: 10px; font-size: 11px; color: var(--text-faint);">▸ = hike-relevant (${TARGETS.hikeRelevantTypes.join(" / ")})</div>`;
}

// ---------- Footer ----------
function renderFooter(today, range30) {
  const el = document.getElementById("loaded-at");
  const dot = document.getElementById("freshness-dot");
  el.textContent = `Data tot ${today.date} · range ${range30.start} → ${range30.end}`;
  dot.classList.remove("mild", "warn");
  if (today.days_ago >= 7) dot.classList.add("warn");
  else if (today.days_ago >= 1) dot.classList.add("mild");
}

// ---------- Range toggle ----------
async function getRange(days) {
  if (STATE.ranges[days]) return STATE.ranges[days];
  const r = await fetchJSON(`api/range?days=${days}&fields=${encodeURIComponent(RANGE_FIELDS)}`);
  STATE.ranges[days] = r;
  return r;
}

async function onRangeChange(target, days) {
  const range = await getRange(days);
  if (target === "steps") makeStepsChart(range);
  else if (target === "distflights") { makeDistanceChart(range); makeFlightsChart(range); }
  else if (target === "hrsleep") { makeHrChart(range); makeSleepChart(range); }
  else if (target === "kcal") makeKcalChart(range);
}

function bindRangeToggles() {
  document.querySelectorAll(".range-toggle").forEach(group => {
    group.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-days]");
      if (!btn) return;
      const days = parseInt(btn.dataset.days, 10);
      const target = group.dataset.target;
      group.querySelectorAll("button").forEach(b => b.classList.toggle("active", b === btn));
      await onRangeChange(target, days);
    });
  });
}

// ---------- Dagconclusie ----------
function renderConclusion(rd, summary, range30) {
  const bd = rd.breakdown;
  const factors = [
    { name: "hike-volume",   pct: bd.hike.pct },
    { name: "beweegminuten", pct: bd.exercise.pct },
    { name: "trapconditie",  pct: bd.flights.pct },
    { name: "rust-HR",       pct: bd.hr.pct },
    { name: "HRV",           pct: bd.hrv.val ? bd.hrv.pct : null },
    { name: "slaap",         pct: bd.sleep.pct },
  ].filter(f => f.pct != null);

  // Status (1 zin)
  let statusText;
  if (rd.score >= 75)      statusText = `Je ligt sterk op koers richting Bergtocht (readiness ${rd.score}/100).`;
  else if (rd.score >= 60) statusText = `Je ligt op koers, met ruimte voor finetuning (readiness ${rd.score}/100).`;
  else if (rd.score >= 40) statusText = `Je bouwt op, maar er is werk aan de winkel (readiness ${rd.score}/100).`;
  else                     statusText = `Je staat achter op je doelen (readiness ${rd.score}/100).`;

  // Focuspunt = sterkste factor
  const best = factors.slice().sort((a, b) => b.pct - a.pct)[0];
  // Aandachtspunt = zwakste factor
  const worst = factors.slice().sort((a, b) => a.pct - b.pct)[0];

  document.getElementById("conc-status").querySelector(".conc-text").textContent = statusText;
  document.getElementById("conc-focus").querySelector(".conc-text").textContent =
    best ? `${capitalize(best.name)} op niveau (${best.pct}%).` : "—";
  document.getElementById("conc-attention").querySelector(".conc-text").textContent =
    worst ? `${capitalize(worst.name)} blijft achter (${worst.pct}%).` : "—";
}

// ---------- Bergtocht pijlers ----------
function renderHikePillars(rd, summary, range30) {
  const bd = rd.breakdown;
  const endIso = summary.today.date;
  const byDate = summary.workouts_by_date_90d || {};

  // Consistentie: aantal dagen met workout in laatste 14 dagen (any type)
  const end = new Date(endIso + "T00:00:00");
  let activeDays = 0;
  for (let i = 0; i < 14; i++) {
    const d = new Date(end); d.setDate(end.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    if ((byDate[iso] || []).length > 0) activeDays++;
  }
  const consistencyPct = Math.round((activeDays / 14) * 100);

  function stateClass(pct) {
    if (pct >= 75) return "state-ok";
    if (pct >= 50) return "state-mid";
    return "state-low";
  }
  function stateLabel(pct) {
    if (pct >= 75) return "op niveau";
    if (pct >= 50) return "in opbouw";
    return "te laag";
  }

  const pillars = [
    { id: "hike-basis",   name: "Hike-basis",   value: `${bd.hike.val} / ${bd.hike.target} workouts (2w)`,                 pct: bd.hike.pct },
    { id: "trapconditie", name: "Trapconditie", value: `${bd.flights.val} / ${bd.flights.target} trappen (week)`,         pct: bd.flights.pct },
    { id: "herstel",      name: "Herstel",      value: bd.sleep.val ? `slaap ${fmtSleep(bd.sleep.val)}, doel 7u`         : "geen slaapdata", pct: bd.sleep.pct },
    { id: "consistentie", name: "Consistentie", value: `${activeDays} actieve dagen van 14`,                              pct: consistencyPct },
  ];

  document.getElementById("hike-pillars").innerHTML = pillars.map(p => `
    <div class="pillar ${stateClass(p.pct)}" data-drill="pillar:${p.id}" role="button" tabindex="0">
      <span class="pillar-name">${p.name}</span>
      <span class="pillar-value">${p.value}</span>
      <span class="pillar-state">${stateLabel(p.pct)} · ${p.pct}%</span>
    </div>`).join("");

  return pillars;
}

// ---------- Bergtocht acties (max 3) ----------
function renderHikeActions(rd, summary, range30) {
  const bd = rd.breakdown;
  const candidates = [];

  if (bd.hike.pct < 100) {
    const missing = Math.max(0, bd.hike.target - bd.hike.val);
    candidates.push({ pct: bd.hike.pct, text: missing > 0
      ? `Plan ${missing} extra hike-workout${missing === 1 ? "" : "s"} in de komende 2 weken (Walking, Elliptical of Rowing).`
      : `Houd je hike-frequentie op niveau.` });
  }
  if (bd.flights.pct < 100) {
    const missing = Math.max(0, bd.flights.target - bd.flights.val);
    candidates.push({ pct: bd.flights.pct, text: `Voeg een trappen-sessie toe — nog ${missing} trappen te gaan deze week.` });
  }
  if (bd.sleep.val && bd.sleep.pct < 100) {
    candidates.push({ pct: bd.sleep.pct, text: `Mik op een 7d-slaap-gem. boven 7u; nu ${fmtSleep(bd.sleep.val)}.` });
  }
  if (bd.hr.val && bd.hr.pct < 90) {
    candidates.push({ pct: bd.hr.pct, text: `Houd rust-HR in de gaten (nu ${bd.hr.val} bpm, doel ≤ 60).` });
  }
  if (bd.exercise.pct < 80) {
    candidates.push({ pct: bd.exercise.pct, text: `Maak elke dag minstens 30 actieve minuten — nu gem. ${bd.exercise.val} min.` });
  }

  candidates.sort((a, b) => a.pct - b.pct);
  const top = candidates.slice(0, 3);

  if (top.length === 0) {
    document.getElementById("hike-actions").innerHTML = `<li class="tone-good">Alle pijlers op niveau — houd dit ritme vast.</li>`;
    return;
  }
  document.getElementById("hike-actions").innerHTML = top.map(a => `<li>${a.text}</li>`).join("");
}

// ---------- Import status + datakwaliteit ----------
function renderImportStatus(summary) {
  const im = summary.import_status || {};
  const fmtIso = (iso) => {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString("nl-NL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    } catch { return iso; }
  };
  const items = [
    { key: "JSON laatst geladen", val: fmtIso(im.json_loaded_at) },
    { key: "Parser-run",          val: fmtIso(im.parsed_at) },
    { key: "Export gemaakt",      val: fmtIso(im.export_made_at) },
    { key: "Data t/m",            val: im.latest_data_date || "—" },
    { key: "Workouts (clean)",    val: fmtNumber(im.clean_workouts) || "—" },
    { key: "Parser-status",       val: "succesvol", cls: "ok" },
  ];
  document.getElementById("import-status").innerHTML = items.map(it =>
    `<li><span class="key">${it.key}</span><span class="val ${it.cls || ""}">${it.val}</span></li>`
  ).join("");
}

function renderDataQuality(summary) {
  const im = summary.import_status || {};
  const items = [
    { key: "Gebruikte workouts",    val: fmtNumber(im.clean_workouts) || "—" },
    { key: "Uitgesloten verdacht", val: im.suspicious_workouts != null ? String(im.suspicious_workouts) : "—",
      cls: (im.suspicious_workouts || 0) > 0 ? "warn" : "muted" },
    { key: "GPS-routes",            val: "niet opgeslagen", cls: "muted" },
    { key: "Dagen vastgelegd",      val: fmtNumber(im.days_recorded) || "—" },
    { key: "Filter-criteria",       val: (im.filter_criteria || []).length + " regels", cls: "muted" },
  ];
  document.getElementById("data-quality").innerHTML = items.map(it =>
    `<li><span class="key">${it.key}</span><span class="val ${it.cls || ""}">${it.val}</span></li>`
  ).join("");
}

// ---------- Chart captions (korte duidingszinnen) ----------
function setCaption(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

function renderCaptions(summary, range30) {
  const today = summary.today;
  const s = range30.series;
  const stepsAvg7 = avgRecent(s.steps, 7, false);
  const stepsToday = today.steps;
  if (stepsAvg7 && stepsToday != null) {
    const dir = stepsToday >= stepsAvg7 ? "boven" : "onder";
    const cls = stepsToday >= stepsAvg7 ? "up" : "down";
    setCaption("cap-steps",
      `Vandaag <strong>${fmtNumber(stepsToday)}</strong> stappen, <span class="${cls}">${dir}</span> het 7-daags gemiddelde van ${fmtNumber(stepsAvg7)}.`);
  } else {
    setCaption("cap-steps", "");
  }

  const flightsAvg7 = avgRecent(s.flights, 7, false);
  const flightsWeek = sumRecent(s.flights, 7);
  if (flightsAvg7 != null) {
    setCaption("cap-flights",
      `Deze week <strong>${fmtNumber(flightsWeek)}</strong> trappen totaal, gemiddeld ${fmtNumber(flightsAvg7)} per dag.`);
  }

  const sleepAvg7Min = avgRecent(s["sleep.asleep_minutes"], 7, false);
  if (sleepAvg7Min) {
    const cls = sleepAvg7Min >= 420 ? "up" : "down";
    const cmp = sleepAvg7Min >= 420 ? "op of boven" : "onder";
    setCaption("cap-sleep",
      `7-daags slaapgemiddelde: <strong>${fmtSleep(sleepAvg7Min)}</strong>, <span class="${cls}">${cmp}</span> het doel van 7u.`);
  }

  const byDate = summary.workouts_by_date_90d || {};
  const hikeWeek = countHikeWorkoutsInLastDays(byDate, today.date, 7);
  const totalWeek = countWorkoutsInLastDays(byDate, today.date, 7);
  const others = totalWeek - hikeWeek;
  setCaption("cap-workouts",
    `Deze week <strong>${totalWeek}</strong> workouts — waarvan <strong>${hikeWeek}</strong> hike-relevant${others ? ` en ${others} overig` : ""}.`);
}

// ---------- Init ----------
async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
  return r.json();
}

// ---------- Fitness-profiel radar ----------
function radarValues(today, range, hikeDays) {
  // Normaliseer alle assen naar 0–100
  const s = range.series;
  const lastN = (key, n) => lastValues(s[key], n).filter(v => typeof v === "number");
  const avg = (arr) => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
  const stepsAvg = avg(lastN("steps", 30));
  const kcalAvg = avg(lastN("active_kcal", 30));
  const flightsAvg = avg(lastN("flights", 30));
  const sleepAvg = avg(lastN("sleep.asleep_minutes", 30));
  const rhrAvg = avg(lastN("resting_hr", 30));
  return [
    Math.min(100, (today.steps || stepsAvg || 0) / 100),                                  // Volume (steps/10000 → /100)
    Math.min(100, (today.active_kcal || kcalAvg || 0) / 6),                               // Intensiteit (kcal/600 → /6)
    Math.min(100, (today.flights || flightsAvg || 0) / 0.12),                             // Trapfitness (flights/12)
    Math.min(100, (((today.sleep && today.sleep.asleep_minutes) || sleepAvg || 0) / 60) / 0.08), // Slaap (h/8)
    Math.max(0, Math.min(100, ((80 - (today.resting_hr || rhrAvg || 60)) / 30) * 100)),   // Rust-HR (inverted)
    Math.min(100, (hikeDays / 14) * 100),                                                 // Consistentie
  ];
}

function radarAvg(range, hikeDays365) {
  const s = range.series;
  const arr = (key) => s[key].map(p => p.v).filter(v => typeof v === "number");
  const avg = (a) => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
  return [
    Math.min(100, avg(arr("steps")) / 100),
    Math.min(100, avg(arr("active_kcal")) / 6),
    Math.min(100, avg(arr("flights")) / 0.12),
    Math.min(100, (avg(arr("sleep.asleep_minutes")) / 60) / 0.08),
    Math.max(0, Math.min(100, ((80 - (avg(arr("resting_hr")) || 60)) / 30) * 100)),
    Math.min(100, (hikeDays365 / range.series.steps.length) * 100),
  ];
}

function countActiveDaysInRange(range) {
  return range.series.steps.filter(p => typeof p.v === "number" && p.v >= 5000).length;
}

function renderFitnessProfile(summary, range30, range365) {
  const canvas = document.getElementById("fitness-radar");
  if (!canvas) return;
  const today = summary.today;
  const byDate90 = summary.workouts_by_date_90d || {};
  const byDate365 = summary.workouts_by_date_365d || {};
  const hikeDays14 = countHikeWorkoutsInLastDays(byDate90, today.date, 14);
  const hikeDays365 = countHikeWorkoutsInLastDays(byDate365, today.date, 365);

  const labels = ["Volume", "Intensiteit", "Trapfitness", "Slaap", "Rust-HR", "Consistentie"];
  const todayData = radarValues(today, range30, hikeDays14);
  const avg30Data = radarAvg(range30, countHikeWorkoutsInLastDays(byDate90, today.date, 30));
  const avg365Data = radarAvg(range365, hikeDays365);

  destroyChart("fitnessRadar");
  STATE.charts.fitnessRadar = new Chart(canvas.getContext("2d"), {
    type: "radar",
    data: {
      labels,
      datasets: [
        { label: "Vandaag", data: todayData, backgroundColor: COLORS.blueFill, borderColor: COLORS.blue, pointBackgroundColor: COLORS.blue, borderWidth: 2 },
        { label: "30d gem", data: avg30Data, backgroundColor: "rgba(74,222,128,0.10)", borderColor: COLORS.green, pointBackgroundColor: COLORS.green, borderWidth: 1.5 },
        { label: "365d gem", data: avg365Data, backgroundColor: "rgba(167,139,250,0.08)", borderColor: COLORS.purple, pointBackgroundColor: COLORS.purple, borderWidth: 1, borderDash: [4, 3] },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { backgroundColor: COLORS.card, borderColor: COLORS.border, borderWidth: 1, titleColor: COLORS.text, bodyColor: COLORS.text } },
      scales: {
        r: {
          min: 0, max: 100,
          ticks: { display: false, stepSize: 25 },
          grid: { color: COLORS.border },
          angleLines: { color: COLORS.border },
          pointLabels: { color: COLORS.textDim, font: { size: 12 } },
        },
      },
    },
  });

  // Legend with absolute values
  const fmt = (v, d = 0) => (typeof v === "number" && isFinite(v)) ? v.toFixed(d) : "—";
  const sleepH = today.sleep ? (today.sleep.asleep_minutes / 60) : null;
  const items = [
    { name: "Volume",       today: `${fmtNumber(today.steps)} stappen`,     avg365: `~${fmtNumber(Math.round(range365.series.steps.map(p=>p.v).filter(v=>typeof v==="number").reduce((a,b)=>a+b,0) / Math.max(1, range365.series.steps.filter(p=>typeof p.v==="number").length)))}` },
    { name: "Intensiteit",  today: `${fmtNumber(today.active_kcal)} kcal`,  avg365: "" },
    { name: "Trapfitness",  today: `${fmtNumber(today.flights)} verd.`,     avg365: "" },
    { name: "Slaap",        today: `${sleepH ? fmt(sleepH,1) : "—"} u`,      avg365: "" },
    { name: "Rust-HR",      today: `${fmtNumber(today.resting_hr)} bpm`,    avg365: "" },
    { name: "Consistentie", today: `${hikeDays14}/14 hike-dagen`,            avg365: `${hikeDays365}/jaar` },
  ];
  document.getElementById("fitness-legend").innerHTML = `
    <h4>Vandaag in cijfers</h4>
    ${items.map(it => `
      <div class="axis-row">
        <span class="axis-name">${it.name}</span>
        <span class="axis-today">${it.today}</span>
        <span class="axis-365">${it.avg365}</span>
      </div>`).join("")}
    <div class="legend-key">
      <span class="lk-today">vandaag</span>
      <span class="lk-30">30d gem</span>
      <span class="lk-365">365d gem</span>
    </div>
  `;
}

// ---------- Percentile-gauges ----------
function percentileRank(value, arr) {
  if (value == null || !arr.length) return null;
  const below = arr.filter(v => typeof v === "number" && v < value).length;
  const equal = arr.filter(v => typeof v === "number" && v === value).length;
  const total = arr.filter(v => typeof v === "number").length;
  if (!total) return null;
  return Math.round(((below + 0.5 * equal) / total) * 100);
}

function percentileGaugeSvg(pct, color) {
  // 64x40 — 180° arc bottom-half
  if (pct == null) return `<svg class="pgauge-svg" viewBox="0 0 64 40"><path d="M 6 36 A 26 26 0 0 1 58 36" stroke="${COLORS.border}" stroke-width="5" fill="none" stroke-linecap="round"/></svg>`;
  const a = -180 + (pct / 100) * 180;
  const rad = (a * Math.PI) / 180;
  const x = 32 + 24 * Math.cos(rad);
  const y = 36 + 24 * Math.sin(rad);
  // Filled-arc from start to needle position
  const a0 = -180;
  const rad0 = (a0 * Math.PI) / 180;
  const x0 = 32 + 26 * Math.cos(rad0);
  const y0 = 36 + 26 * Math.sin(rad0);
  const xv = 32 + 26 * Math.cos(rad);
  const yv = 36 + 26 * Math.sin(rad);
  return `<svg class="pgauge-svg" viewBox="0 0 64 40">
    <path d="M ${x0.toFixed(1)} ${y0.toFixed(1)} A 26 26 0 0 1 58 36" stroke="${COLORS.border}" stroke-width="5" fill="none" stroke-linecap="round"/>
    <path d="M ${x0.toFixed(1)} ${y0.toFixed(1)} A 26 26 0 0 ${pct > 50 ? 1 : 0} ${xv.toFixed(1)} ${yv.toFixed(1)}" stroke="${color}" stroke-width="5" fill="none" stroke-linecap="round"/>
    <line x1="32" y1="36" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${COLORS.text}" stroke-width="2" stroke-linecap="round"/>
    <circle cx="32" cy="36" r="2.5" fill="${COLORS.text}"/>
  </svg>`;
}

function renderPercentileGauges(summary, range365) {
  const host = document.getElementById("percentile-row");
  if (!host) return;
  const today = summary.today;
  const s = range365.series;
  const arr = (k) => s[k].map(p => p.v);
  const sleepMinArr = arr("sleep.asleep_minutes");
  const sleepToday = today.sleep ? today.sleep.asleep_minutes : null;

  const items = [
    { label: "Stappen",  pct: percentileRank(today.steps, arr("steps")),       lowerBetter: false },
    { label: "Slaap",    pct: percentileRank(sleepToday, sleepMinArr),         lowerBetter: false },
    { label: "Rust-HR",  pct: percentileRank(today.resting_hr, arr("resting_hr")), lowerBetter: true },
    { label: "HRV",      pct: percentileRank(today.hrv_ms, arr("hrv_ms")),     lowerBetter: false },
  ];

  host.innerHTML = items.map(it => {
    const disp = it.pct == null ? null : (it.lowerBetter ? 100 - it.pct : it.pct);
    const color = disp == null ? COLORS.textDim : disp >= 75 ? COLORS.green : disp >= 50 ? COLORS.teal : disp >= 25 ? COLORS.orange : COLORS.red;
    return `<div class="pgauge">
      ${percentileGaugeSvg(disp, color)}
      <div class="pgauge-info">
        <span class="pgauge-label">${it.label}</span>
        <span class="pgauge-percentile">${disp == null ? "—" : "p" + disp}</span>
        <span class="pgauge-sub">vs. laatste 365d${it.lowerBetter ? " · lager = beter" : ""}</span>
      </div>
    </div>`;
  }).join("");
}

// ---------- C1: Drill-down modal ----------
const METRIC_META = {
  "steps":              { title: "Stappen",          unit: "",     target: 10000, format: (v) => fmtNumber(Math.round(v)) },
  "distance_km":        { title: "Afstand",          unit: " km",  target: 7.5,   format: (v) => v.toFixed(1) },
  "flights":            { title: "Trappen",          unit: "",     target: 10,    format: (v) => fmtNumber(Math.round(v)) },
  "active_kcal":        { title: "Actieve calorieën", unit: " kcal", target: 500,  format: (v) => fmtNumber(Math.round(v)) },
  "exercise_minutes":   { title: "Beweegminuten",     unit: " min", target: 30,    format: (v) => fmtNumber(Math.round(v)) },
  "stand_hours":        { title: "Sta-uren",          unit: "",     target: 12,    format: (v) => fmtNumber(Math.round(v)) },
  "resting_hr":         { title: "Rust-hartslag",     unit: " bpm", target: 60,    format: (v) => fmtNumber(Math.round(v)), lowerBetter: true },
  "hrv_ms":             { title: "HRV",               unit: " ms",  target: 50,    format: (v) => fmtNumber(Math.round(v)) },
  "sleep.asleep_minutes": { title: "Slaap",          unit: "",     target: 420,   format: (v) => fmtSleep(Math.round(v)) },
};

function percentile(arr, p) {
  const a = arr.filter((v) => typeof v === "number").sort((x, y) => x - y);
  if (!a.length) return null;
  const idx = (p / 100) * (a.length - 1);
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  return a[lo] + (a[hi] - a[lo]) * (idx - lo);
}

function buildHistogram(values, bins = 20) {
  const a = values.filter((v) => typeof v === "number");
  if (!a.length) return { bins: [], min: 0, max: 0 };
  const min = Math.min(...a);
  const max = Math.max(...a);
  const span = max - min || 1;
  const result = new Array(bins).fill(0);
  a.forEach((v) => {
    const i = Math.min(bins - 1, Math.floor(((v - min) / span) * bins));
    result[i]++;
  });
  return { bins: result, min, max };
}

function binIndexFor(value, min, max, bins = 20) {
  if (value == null) return -1;
  const span = max - min || 1;
  return Math.min(bins - 1, Math.max(0, Math.floor(((value - min) / span) * bins)));
}

function renderDrilldown(metricKey) {
  const meta = METRIC_META[metricKey];
  if (!meta) return;
  const dlg = document.getElementById("drilldown-modal");
  const range = STATE.ranges[365] || STATE.ranges[90] || STATE.ranges[30];
  if (!range || !range.series[metricKey]) return;

  const series = range.series[metricKey];
  const values = series.map((p) => p.v);
  const numeric = values.filter((v) => typeof v === "number");
  const todayVal = STATE.summary && STATE.summary.today
    ? (metricKey === "sleep.asleep_minutes"
        ? (STATE.summary.today.sleep ? STATE.summary.today.sleep.asleep_minutes : null)
        : STATE.summary.today[metricKey])
    : null;

  document.getElementById("drill-title").textContent = meta.title;

  // Stats
  const min = numeric.length ? Math.min(...numeric) : null;
  const max = numeric.length ? Math.max(...numeric) : null;
  const avg = numeric.length ? numeric.reduce((a, b) => a + b, 0) / numeric.length : null;
  const med = percentile(numeric, 50);
  const p10 = percentile(numeric, 10);
  const p90 = percentile(numeric, 90);
  const hit = meta.lowerBetter
    ? (numeric.filter((v) => v <= meta.target).length / Math.max(numeric.length, 1)) * 100
    : (numeric.filter((v) => v >= meta.target).length / Math.max(numeric.length, 1)) * 100;

  const stat = (k, v) => `<div class="drill-stat"><div class="k">${k}</div><div class="v">${v}</div></div>`;
  const f = meta.format;
  document.getElementById("drill-stats").innerHTML = [
    stat("Vandaag", todayVal != null ? f(todayVal) : "—"),
    stat("Min", min != null ? f(min) : "—"),
    stat("p10", p10 != null ? f(p10) : "—"),
    stat("Mediaan", med != null ? f(med) : "—"),
    stat("Gem.", avg != null ? f(avg) : "—"),
    stat("p90", p90 != null ? f(p90) : "—"),
    stat("Max", max != null ? f(max) : "—"),
    stat("Doel-hit", `${Math.round(hit)}%`),
  ].join("");

  // Histogram
  const hist = buildHistogram(values, 20);
  const todayBin = binIndexFor(todayVal, hist.min, hist.max, 20);
  const maxCount = Math.max(...hist.bins, 1);
  document.getElementById("drill-histogram").innerHTML = hist.bins.map((c, i) => {
    const h = c === 0 ? 0 : Math.max(2, (c / maxCount) * 70);
    const cls = c === 0 ? "hbar empty" : (i === todayBin ? "hbar today" : "hbar");
    return `<div class="${cls}" style="height: ${h}px;" title="${c} dagen"></div>`;
  }).join("");

  // Chart (90d trend)
  const chartRange = STATE.ranges[90] || range;
  const chartSeries = chartRange.series[metricKey] || series;
  const labels = chartSeries.map((p) => p.date.slice(5));
  const data = chartSeries.map((p) => p.v);
  destroyChart("drill");
  STATE.charts.drill = new Chart(document.getElementById("drill-chart").getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: meta.title,
          data,
          borderColor: COLORS.blue,
          backgroundColor: COLORS.blueFill,
          tension: 0.25,
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: `Doel ${f(meta.target)}`,
          data: labels.map(() => meta.target),
          borderColor: COLORS.green,
          borderDash: [4, 4],
          borderWidth: 1.2,
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: commonPlugins(),
      scales: commonScales(),
    },
  });

  document.getElementById("drill-note").textContent =
    `Beschrijvend overzicht — geen medisch advies. Doel is ${f(meta.target)}${meta.unit ? " " + meta.unit.trim() : ""}${meta.lowerBetter ? " (lager is beter)" : ""}.`;

  if (!dlg.open) dlg.showModal();
}

function renderPillarDrilldown(pillarId) {
  const dlg = document.getElementById("drilldown-modal");
  const labels = {
    "hike-basis":    { title: "Hike-basis", note: "Aantal Walking / Elliptical / Rowing workouts in laatste 14 dagen versus doel van 10. Indicator voor je hike-specifieke uithoudingsvermogen." },
    "trapconditie":  { title: "Trapconditie", note: "Totaal aantal trappen-verdiepingen deze week versus doel van 70. Bergtocht vereist veel hoogtemeters." },
    "herstel":       { title: "Herstel", note: "7-daags gemiddelde rust-HR + slaap. Lager = beter voor HR. Goede slaap (>7u) is essentieel voor herstel na trainingsdagen." },
    "consistentie":  { title: "Consistentie", note: "Aantal dagen in laatste 14 met ≥5000 stappen. Regelmatige beweging > sporadische pieken." },
  };
  const info = labels[pillarId] || { title: pillarId, note: "" };
  document.getElementById("drill-title").textContent = info.title;
  document.getElementById("drill-stats").innerHTML = "";
  document.getElementById("drill-histogram").innerHTML = "";
  destroyChart("drill");
  const ctx = document.getElementById("drill-chart").getContext("2d");
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  document.getElementById("drill-note").textContent = info.note;
  if (!dlg.open) dlg.showModal();
}

function bindDrilldown() {
  document.addEventListener("click", (e) => {
    const trig = e.target.closest("[data-drill]");
    if (!trig) return;
    const drill = trig.dataset.drill;
    if (METRIC_META[drill]) renderDrilldown(drill);
    else if (drill.startsWith("pillar:")) renderPillarDrilldown(drill.slice(7));
  });
  const dlg = document.getElementById("drilldown-modal");
  const closeBtn = document.getElementById("drill-close");
  if (closeBtn) closeBtn.addEventListener("click", () => dlg.close());
  if (dlg) {
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  }
}

// ---------- Settings (theme / density / widgets) ----------
const SETTINGS_KEY = "gezondheid.settings";
const DEFAULT_SETTINGS = { theme: "aurora-dark", density: "standaard", widgets: {} };

const THEMES = [
  { id: "aurora-dark",  name: "Aurora Dark",     desc: "Donker, kalm" },
  { id: "aurora-light", name: "Aurora Light",    desc: "Wit, overdag" },
  { id: "whoop",       name: "WHOOP Recovery", desc: "Zwart, semantisch" },
  { id: "tactical",    name: "Tactical HUD",   desc: "Monospace, neon" },
  { id: "nord",        name: "Nord",           desc: "Pastel donker" },
];

const WIDGETS = [
  { id: "conclusion",        label: "Dagconclusie",        group: "Coach" },
  { id: "insights",          label: "Dit valt op",         group: "Coach" },
  { id: "fitness-profile",   label: "Fitnessprofiel",      group: "Coach" },
  { id: "hero",              label: "Vandaag + Bergtocht", group: "Coach" },
  { id: "coach",             label: "Bergtocht-coach", group: "Coach" },
  { id: "dagstats",          label: "Dagstats",            group: "Stats" },
  { id: "overview",          label: "Overzicht 7/30/90d",  group: "Stats" },
  { id: "yoy",               label: "Dit jaar vs. vorig",  group: "Stats" },
  { id: "records",           label: "Records & streaks",   group: "Stats" },
  { id: "heatmap",           label: "Workout-kalender",    group: "Stats" },
  { id: "chart-steps",       label: "Stappen-chart",       group: "Grafieken" },
  { id: "chart-distflights", label: "Afstand & trappen",   group: "Grafieken" },
  { id: "chart-hrsleep",     label: "Hartslag & slaap",    group: "Grafieken" },
  { id: "chart-kcal",        label: "Actieve calorieën",   group: "Grafieken" },
  { id: "patterns",          label: "Patronen",            group: "Grafieken" },
  { id: "workouts-detail",   label: "Workouts (90d)",      group: "Grafieken" },
  { id: "import-data",       label: "Import & data",       group: "Data" },
];

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_SETTINGS, ...parsed, widgets: { ...DEFAULT_SETTINGS.widgets, ...(parsed.widgets || {}) } };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}
function saveSettings(s) {
  STATE.settings = s;
  try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(s)); } catch {}
}

function refreshColorsFromCSS() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n).trim();
  COLORS.blue       = v("--blue")       || COLORS.blue;
  COLORS.blueFill   = v("--blue-fill")  || COLORS.blueFill;
  COLORS.green      = v("--green")      || COLORS.green;
  COLORS.greenFill  = v("--green-fill") || COLORS.greenFill;
  COLORS.orange     = v("--orange")     || COLORS.orange;
  COLORS.orangeFill = v("--orange-fill")|| COLORS.orangeFill;
  COLORS.purple     = v("--purple")     || COLORS.purple;
  COLORS.purpleFill = v("--purple-fill")|| COLORS.purpleFill;
  COLORS.teal       = v("--teal")       || COLORS.teal;
  COLORS.tealFill   = v("--teal-fill")  || COLORS.tealFill;
  COLORS.text       = v("--text")       || COLORS.text;
  COLORS.textDim    = v("--text-dim")   || COLORS.textDim;
  COLORS.border     = v("--border")     || COLORS.border;
  COLORS.card       = v("--card")       || COLORS.card;
  COLORS.red        = v("--red")        || COLORS.red;
  if (typeof Chart !== "undefined") {
    Chart.defaults.color = COLORS.textDim;
    Chart.defaults.borderColor = COLORS.border;
  }
}

function applyTheme(name) {
  document.documentElement.dataset.theme = name;
  refreshColorsFromCSS();
}
function applyDensity(name) {
  document.documentElement.dataset.density = name;
}

function rerenderAllCharts() {
  Object.keys(STATE.charts).forEach((k) => destroyChart(k));
  const range30 = STATE.ranges[30];
  const range90 = STATE.ranges[90];
  const range365 = STATE.ranges[365];
  const summary = STATE.summary;
  if (!range30 || !summary) return;
  makeStepsChart(range30);
  makeDistanceChart(range30);
  makeFlightsChart(range30);
  makeKcalChart(range30);
  makeHrChart(range30);
  makeSleepChart(range30);
  makeWeekdayChart(range90);
  makeWorkoutFreqChart(summary);
  makeWorkoutsDonut(summary.workouts_90d);
  if (range365) renderFitnessProfile(summary, range30, range365);
  // Re-render readiness lists (mini-rings depend on COLORS)
  const readiness = calculateReadiness(summary, range30);
  renderReadiness(readiness);
  if (range365) renderPercentileGauges(summary, range365);
}

function renderThemePicker(active) {
  const host = document.getElementById("theme-picker");
  if (!host) return;
  host.innerHTML = THEMES.map((t) => `
    <button type="button" class="theme-card ${t.id === active ? "active" : ""}" data-theme-id="${t.id}">
      <div class="thumb ${t.id}"></div>
      <span class="name">${t.name}</span>
      <span class="desc">${t.desc}</span>
    </button>
  `).join("");
  host.querySelectorAll(".theme-card").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.themeId;
      applyTheme(id);
      STATE.settings.theme = id;
      saveSettings(STATE.settings);
      host.querySelectorAll(".theme-card").forEach((b) => b.classList.toggle("active", b === btn));
      if (STATE.summary) rerenderAllCharts();
    });
  });
}

function applyWidgets(visibleMap) {
  WIDGETS.forEach((w) => {
    const visible = visibleMap[w.id] !== false; // default visible
    const el = document.querySelector(`[data-widget="${w.id}"]`);
    if (el) el.classList.toggle("widget-hidden", !visible);
  });
}

function renderWidgetPicker(visibleMap) {
  const host = document.getElementById("widget-picker");
  if (!host) return;
  const groups = {};
  WIDGETS.forEach((w) => { (groups[w.group] = groups[w.group] || []).push(w); });
  host.innerHTML = Object.keys(groups).map((g) => `
    <div class="widget-group">
      <h4>${g}</h4>
      <div class="wlist">
        ${groups[g].map((w) => {
          const on = visibleMap[w.id] !== false;
          return `<label class="${on ? "" : "off"}">
            <input type="checkbox" data-widget-id="${w.id}" ${on ? "checked" : ""}>
            <span>${w.label}</span>
          </label>`;
        }).join("")}
      </div>
    </div>`).join("");
  host.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener("change", () => {
      const id = cb.dataset.widgetId;
      STATE.settings.widgets[id] = cb.checked;
      saveSettings(STATE.settings);
      cb.closest("label").classList.toggle("off", !cb.checked);
      const el = document.querySelector(`[data-widget="${id}"]`);
      if (el) el.classList.toggle("widget-hidden", !cb.checked);
    });
  });
}

function bindDensityPicker(active) {
  const inputs = document.querySelectorAll('#density-picker input[name="density"]');
  inputs.forEach((inp) => {
    inp.checked = inp.value === active;
    inp.addEventListener("change", () => {
      if (!inp.checked) return;
      applyDensity(inp.value);
      STATE.settings.density = inp.value;
      saveSettings(STATE.settings);
    });
  });
}

function openDrawer() {
  const drawer = document.getElementById("settings-drawer");
  const back = document.getElementById("settings-backdrop");
  if (!drawer || !back) return;
  drawer.hidden = false;
  back.hidden = false;
  requestAnimationFrame(() => drawer.classList.remove("closing"));
}
function closeDrawer() {
  const drawer = document.getElementById("settings-drawer");
  const back = document.getElementById("settings-backdrop");
  if (!drawer || !back) return;
  drawer.classList.add("closing");
  setTimeout(() => { drawer.hidden = true; back.hidden = true; }, 220);
}

function bindDrawer() {
  const cog = document.getElementById("settings-cog");
  const close = document.getElementById("drawer-close");
  const back = document.getElementById("settings-backdrop");
  const reset = document.getElementById("drawer-reset");
  if (cog) cog.addEventListener("click", openDrawer);
  if (close) close.addEventListener("click", closeDrawer);
  if (back) back.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      const drawer = document.getElementById("settings-drawer");
      if (drawer && !drawer.hidden) closeDrawer();
    }
  });
  if (reset) reset.addEventListener("click", () => {
    if (!confirm("Alle instellingen terugzetten naar standaard?")) return;
    localStorage.removeItem(SETTINGS_KEY);
    location.reload();
  });
}

function bootSettings() {
  const s = loadSettings();
  STATE.settings = s;
  applyTheme(s.theme);
  applyDensity(s.density);
  applyWidgets(s.widgets);
  renderThemePicker(s.theme);
  bindDensityPicker(s.density);
  renderWidgetPicker(s.widgets);
  bindDrawer();
}

async function init() {
  try {
    const [summary, range30, range90, range365] = await Promise.all([
      fetchJSON("api/summary"),
      fetchJSON(`api/range?days=30&fields=${encodeURIComponent(RANGE_FIELDS)}`),
      fetchJSON(`api/range?days=90&fields=${encodeURIComponent(RANGE_FIELDS)}`),
      fetchJSON(`api/range?days=365&fields=${encodeURIComponent(RANGE_FIELDS)}`),
    ]);
    STATE.summary = summary;
    STATE.ranges = { 30: range30, 90: range90, 365: range365 };

    const trends = {
      steps: avgRecent(range30.series.steps, 7),
      distance_km: avgRecent(range30.series.distance_km, 7),
      flights: avgRecent(range30.series.flights, 7),
      active_kcal: avgRecent(range30.series.active_kcal, 7),
      exercise_minutes: avgRecent(range30.series.exercise_minutes, 7),
      stand_hours: avgRecent(range30.series.stand_hours, 7),
      resting_hr: avgRecent(range30.series.resting_hr, 7),
      hrv: avgRecent(range30.series.hrv_ms, 7),
      sleep: avgRecent(range30.series["sleep.asleep_minutes"] || [], 7),
    };

    renderDateBadge(summary.stale);
    renderStaleBanner(summary.stale);

    // Insights first (Spoor B)
    const insights = generateInsights(summary, range30, range90);
    renderInsights(insights);

    renderRings(summary.today);
    renderHikingGoal(summary.today, range30);

    // Fitnessprofiel radar (A2)
    renderFitnessProfile(summary, range30, range365);

    // Coach (Spoor C)
    const readiness = calculateReadiness(summary, range30);
    renderConclusion(readiness, summary, range30);
    renderPercentileGauges(summary, range365);
    renderReadiness(readiness);
    renderHikePillars(readiness, summary, range30);
    renderHikeActions(readiness, summary, range30);
    renderWeekTodos(summary, range30);

    renderToday(summary.today, trends, range30);
    renderOverview(summary, range30);
    renderYoY(summary, range365);
    renderRecords(range365, summary);
    renderHeatmap(summary);

    makeStepsChart(range30);
    makeDistanceChart(range30);
    makeFlightsChart(range30);
    makeKcalChart(range30);
    makeHrChart(range30);
    makeSleepChart(range30);
    makeWeekdayChart(range90);
    makeWorkoutFreqChart(summary);
    makeWorkoutsDonut(summary.workouts_90d);
    renderWorkoutsTable(summary.workouts_90d);

    renderCaptions(summary, range30);
    renderImportStatus(summary);
    renderDataQuality(summary);

    bindRangeToggles();
    bindDrilldown();
    renderFooter(summary.today, range30);
  } catch (err) {
    console.error(err);
    document.body.insertAdjacentHTML("afterbegin", `<div class="stale-banner warn" style="margin:16px 28px;">Fout bij laden: ${err.message}</div>`);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bootSettings();
  init();
});


/* gm-empty-state (appended) */
(function () {
  function showEmptyState() {
    if (document.getElementById('gm-empty-state')) return;
    document.querySelectorAll('.stale-banner.warn').forEach(function (el) { el.remove(); });
    var card = document.createElement('div');
    card.id = 'gm-empty-state';
    card.setAttribute('style', 'margin:16px 28px;padding:20px 24px;border-radius:12px;background:rgba(80,140,255,.10);border:1px solid rgba(80,140,255,.35);');
    card.innerHTML =
      '<h2 style="margin:0 0 6px;font-size:1.15rem;">Nog geen gezondheidsdata ge&iuml;mporteerd</h2>' +
      '<p style="margin:0 0 14px;opacity:.85;">Upload eerst je Apple Health-export (<code>export.zip</code>) via <code>upload</code>. Daarna vullen het dashboard en de grafieken zich vanzelf.</p>' +
      '<a href="upload" style="display:inline-block;padding:9px 16px;border-radius:8px;background:#2d6cdf;color:#fff;text-decoration:none;font-weight:600;">Data uploaden</a>';
    document.body.insertAdjacentElement('afterbegin', card);
  }
  function check() {
    fetch('api/import/status').then(function (r) { return r.ok ? r.json() : null; }).then(function (s) {
      if (s && s.has_import === false) showEmptyState();
    }).catch(function () {});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', check);
  else check();
})();
