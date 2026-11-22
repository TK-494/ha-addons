import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { amountClass, axisMoney, maskAccount, money } from "../format.js";

/**
 * Saldoverloop: closing balance per month, per account and for the household.
 *
 * One large chart to compare accounts, plus one small chart per account with
 * its own scale. A savings account of €20k and a checking account hovering
 * around €500 share no useful y-axis — on the shared chart the checking line
 * is flat; on its own it shows every payday.
 */

const TOTAL_COLOR = "#0ea5e9";
const PALETTE = ["#a78bfa", "#fbbf24", "#34d399", "#fb7185", "#f97316", "#22d3ee", "#e879f9", "#94a3b8"];
const MONTH_OPTIONS = [6, 12, 24, 60, 120];
const MONTHS_KEY = "financials.balance.months";

const KIND_LABEL = { checking: "Betaalrekening", savings: "Spaarrekening", credit_card: "Creditcard" };

function savedMonths() {
  try {
    const value = Number(localStorage.getItem(MONTHS_KEY));
    return MONTH_OPTIONS.includes(value) ? value : 12;
  } catch {
    return 12;
  }
}

const tooltipStyle = {
  contentStyle: { background: "rgba(15, 23, 42, 0.92)", border: "none", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#cbd5e1" },
  itemStyle: { padding: 0 },
};

/** First and last non-empty value of a series, for "how much did it change". */
function span(values) {
  const known = values.filter((v) => v !== null && v !== undefined);
  if (known.length === 0) return null;
  return { first: known[0], last: known[known.length - 1] };
}

function Change({ values }) {
  const s = span(values);
  if (!s || values.length < 2) return null;
  const diff = Math.round((s.last - s.first) * 100) / 100;
  return (
    <span className={`text-xs ${amountClass(diff)}`}>
      {diff > 0 ? "+" : ""}{money(diff)}
    </span>
  );
}

function AccountCard({ series, periods, color }) {
  const data = periods.map((label, index) => ({ label, value: series.values[index] }));
  const s = span(series.values);
  const gradient = `fill-${series.account_id}`;
  return (
    <article className="card">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 truncate font-semibold">
            <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: color }} />
            <span className="truncate">{maskAccount(series.label)}</span>
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {KIND_LABEL[series.kind] || series.kind}
            {!series.include_in_networth && " · telt niet mee in totaal"}
          </p>
        </div>
        <div className="text-right">
          <p className="whitespace-nowrap font-semibold">{s ? money(s.last) : "—"}</p>
          <Change values={series.values} />
        </div>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="label" hide />
          <YAxis hide domain={["auto", "auto"]} />
          <ReferenceLine y={0} stroke="#64748b" strokeOpacity={0.3} />
          <Tooltip formatter={(v) => [money(v), "Saldo"]} {...tooltipStyle} />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            fill={`url(#${gradient})`}
            connectNulls={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </article>
  );
}

export default function BalanceHistory() {
  const [months, setMonths] = useState(savedMonths);
  const [history, setHistory] = useState(null);
  const [error, setError] = useState(null);
  const [hidden, setHidden] = useState(() => new Set());

  useEffect(() => {
    try { localStorage.setItem(MONTHS_KEY, String(months)); } catch { /* private window */ }
    setHistory(null);
    api.balanceHistory(months).then(setHistory).catch((e) => setError(e.message));
  }, [months]);

  // Accounts without any known balance (added by hand, never imported) have
  // nothing to draw; they are listed in a footnote instead of as empty charts.
  const { withData, withoutData, colors } = useMemo(() => {
    const all = history?.series || [];
    const colorMap = Object.fromEntries(all.map((s, i) => [s.account_id, PALETTE[i % PALETTE.length]]));
    return {
      withData: all.filter((s) => s.values.some((v) => v !== null)),
      withoutData: all.filter((s) => s.values.every((v) => v === null)),
      colors: colorMap,
    };
  }, [history]);

  const chartData = useMemo(() => {
    if (!history) return [];
    return history.periods.map((label, index) => ({
      label,
      total: history.total[index],
      ...Object.fromEntries(withData.map((s) => [`a${s.account_id}`, s.values[index]])),
    }));
  }, [history, withData]);

  function toggle(key) {
    setHidden((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  const totalSpan = history ? span(history.total) : null;

  return (
    <>
      <PageHeader
        title="Saldoverloop"
        subtitle="Saldo aan het eind van elke periode, per rekening en voor het huishouden."
      >
        <select className="input w-auto" value={months} onChange={(e) => setMonths(Number(e.target.value))}>
          {MONTH_OPTIONS.map((m) => (
            <option key={m} value={m}>{m >= 24 ? `${m / 12} jaar` : `${m} maanden`}</option>
          ))}
        </select>
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}

      {!history && !error && <Spinner />}

      {history && withData.length === 0 && (
        <Empty>
          Nog geen saldo's bekend. <Link className="text-sky-600 dark:text-sky-400" to="/importeren">Importeer</Link> een
          CSV van je bank — die stuurt per transactie het saldo mee.
        </Empty>
      )}

      {history && withData.length > 0 && (
        <>
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <div className="card">
              <p className="text-xs text-slate-500 dark:text-slate-400">Totaal nu</p>
              <p className="text-lg font-semibold">{totalSpan ? money(totalSpan.last) : "—"}</p>
            </div>
            <div className="card">
              <p className="text-xs text-slate-500 dark:text-slate-400">Verschil in deze periode</p>
              <p className={`text-lg font-semibold ${totalSpan ? amountClass(totalSpan.last - totalSpan.first) : ""}`}>
                {totalSpan
                  ? `${totalSpan.last - totalSpan.first > 0 ? "+" : ""}${money(totalSpan.last - totalSpan.first)}`
                  : "—"}
              </p>
            </div>
            <div className="card">
              <p className="text-xs text-slate-500 dark:text-slate-400">Rekeningen</p>
              <p className="text-lg font-semibold">{withData.length}</p>
            </div>
          </div>

          <section className="card">
            <div className="mb-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => toggle("total")}
                className={`btn btn-row bg-slate-500/10 ${hidden.has("total") ? "opacity-40" : ""}`}
                aria-pressed={!hidden.has("total")}
              >
                <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full" style={{ background: TOTAL_COLOR }} />
                Totaal
              </button>
              {withData.map((s) => {
                const key = `a${s.account_id}`;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => toggle(key)}
                    className={`btn btn-row bg-slate-500/10 ${hidden.has(key) ? "opacity-40" : ""}`}
                    aria-pressed={!hidden.has(key)}
                  >
                    <span
                      className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full"
                      style={{ background: colors[s.account_id] }}
                    />
                    {maskAccount(s.label)}
                  </button>
                );
              })}
            </div>
            <ResponsiveContainer width="100%" height={360}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="label" fontSize={11} minTickGap={16} />
                <YAxis fontSize={11} tickFormatter={axisMoney} width={56} />
                <ReferenceLine y={0} stroke="#64748b" strokeOpacity={0.4} />
                <Tooltip formatter={(v) => money(v)} {...tooltipStyle} />
                {!hidden.has("total") && (
                  <Line
                    type="monotone" dataKey="total" name="Totaal"
                    stroke={TOTAL_COLOR} strokeWidth={3} dot={false} isAnimationActive={false}
                  />
                )}
                {withData.filter((s) => !hidden.has(`a${s.account_id}`)).map((s) => (
                  <Line
                    key={s.account_id}
                    type="monotone"
                    dataKey={`a${s.account_id}`}
                    name={maskAccount(s.label)}
                    stroke={colors[s.account_id]}
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Uit het saldo dat de bank zelf per transactie meestuurt, dus gelijk aan je afschrift. Een rekening
              zonder mutaties houdt zijn laatst bekende stand vast. Het totaal telt alleen rekeningen met
              "Meetellen in totaalvermogen" aan; dat zet je op <Link className="text-sky-600 dark:text-sky-400" to="/rekeningen">Rekeningen</Link>.
            </p>
          </section>

          <h3 className="mb-2 mt-6 font-semibold">Per rekening</h3>
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
            Elke grafiek heeft een eigen schaal, zodat ook een rekening met een klein saldo zijn verloop laat zien.
          </p>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {withData.map((s) => (
              <AccountCard key={s.account_id} series={s} periods={history.periods} color={colors[s.account_id]} />
            ))}
          </div>

          {withoutData.length > 0 && (
            <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
              Zonder bekend saldo (geen import): {withoutData.map((s) => maskAccount(s.label)).join(", ")}.
            </p>
          )}
        </>
      )}
    </>
  );
}
