import { Link } from "react-router-dom";
import { periodLabel, usePeriod } from "../period.js";

const SHORT_MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];

/** "25 aug – 24 sep": the real span of a period, for when the month does not
    start on the 1st. `end` is exclusive, so the last day shown is the day before. */
function span(start, end) {
  // Built from parts: `new Date("2026-08-25")` is UTC midnight, which west of
  // Greenwich is still the 24th locally.
  const local = (iso) => new Date(...iso.slice(0, 10).split("-").map((v, i) => Number(v) - (i === 1 ? 1 : 0)));
  const s = local(start);
  const e = local(end);
  e.setDate(e.getDate() - 1);
  return `${s.getDate()} ${SHORT_MONTHS[s.getMonth()]} – ${e.getDate()} ${SHORT_MONTHS[e.getMonth()]}`;
}

/**
 * From–to month selection, with the presets people reach for most.
 *
 * Two plain <select>s rather than <input type="month">: Safari on the Mac
 * still renders that as a text box, and the Home Assistant app is a WebView.
 * A select works everywhere and gets the native wheel on a phone.
 *
 * ‹ › shift the whole window by its own length, so browsing quarters steps
 * by a quarter. Presets end at the month you are looking at, not at today.
 */
const PRESETS = [
  { name: "current", label: "Deze maand" },
  { name: "3", label: "3 mnd" },
  { name: "6", label: "6 mnd" },
  { name: "12", label: "12 mnd" },
  { name: "year", label: "Dit jaar" },
  { name: "all", label: "Alles" },
];

export default function PeriodPicker({ compact = false }) {
  const period = usePeriod();
  if (!period.range) return null;

  const { range, options, single, count, setRange, shift, preset } = period;

  // With the boundary on a salary day, "augustus" runs into late September.
  // Without the dates next to it, the list reads as if September were missing.
  const shifted = options?.boundary && options.boundary.day !== 1;
  const choices = options?.options
    ? options.options.map((o) => ({
        value: o.value,
        label: shifted ? `${o.label} (${span(o.start, o.end)})` : o.label,
      }))
    : [
        { value: range.from, label: range.from },
        ...(single ? [] : [{ value: range.to, label: range.to }]),
      ];

  const selected = options?.options?.find((o) => o.value === range.to);

  const canGoForward = !options || range.to < options.current;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex items-center gap-1">
        <button className="btn-ghost px-2" onClick={() => shift(-1)} title={single ? "Vorige maand" : `${count} maanden terug`}>
          ‹
        </button>
        <select
          className="input w-auto py-1"
          value={range.from}
          onChange={(e) => setRange(e.target.value, range.to)}
          aria-label="Van"
          title="Begin van de periode"
        >
          {choices.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <span className="text-xs text-slate-500 dark:text-slate-400">t/m</span>
        <select
          className="input w-auto py-1"
          value={range.to}
          onChange={(e) => setRange(range.from, e.target.value)}
          aria-label="Tot en met"
          title="Einde van de periode"
        >
          {choices.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <button
          className="btn-ghost px-2"
          onClick={() => shift(1)}
          disabled={!canGoForward}
          title={canGoForward ? (single ? "Volgende maand" : `${count} maanden vooruit`) : "Dit is de huidige maand"}
        >
          ›
        </button>
      </div>

      {!compact && (
        <div className="flex flex-wrap gap-1">
          {PRESETS.map((p) => (
            <button key={p.name} className="btn-ghost px-2 py-1 text-xs" onClick={() => preset(p.name)}>
              {p.label}
            </button>
          ))}
        </div>
      )}

      {shifted && selected && (
        <p className="basis-full text-xs text-slate-500 dark:text-slate-400">
          Je maand begint op {options.boundary.mode === "salary" ? "je salarisdag" : `de ${options.boundary.day}e`}, dus{" "}
          <strong>{selected.label}</strong> loopt t/m {span(selected.start, selected.end).split(" – ")[1]}.
          Wil je kalendermaanden, zet de maandgrens dan op de 1e bij{" "}
          <Link className="underline" to="/instellingen">Instellingen</Link>.
        </p>
      )}
    </div>
  );
}

/** "maart 2026" or "januari 2026 t/m maart 2026", for a subtitle. */
export function PeriodTitle() {
  const { range, options, single } = usePeriod();
  if (!range) return null;
  return single
    ? periodLabel(range.from, options)
    : `${periodLabel(range.from, options)} t/m ${periodLabel(range.to, options)}`;
}
