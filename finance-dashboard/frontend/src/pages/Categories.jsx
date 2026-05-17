import { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Legend, LineChart, Line,
} from "recharts";
import { getCategoryTrend } from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(n);

const PERIOD_OPTIONS = [
  { value: 3, label: "3 maanden" },
  { value: 6, label: "6 maanden" },
  { value: 12, label: "12 maanden" },
  { value: 24, label: "24 maanden" },
];

export default function Categories() {
  const [months, setMonths] = useState(6);
  const [data, setData] = useState(null);
  const [focusedId, setFocusedId] = useState(null);

  useEffect(() => {
    getCategoryTrend(months).then(setData);
  }, [months]);

  // One row per month, plus one column per category. Recharts wants this
  // wide shape for a stacked BarChart.
  const chartData = useMemo(() => {
    if (!data) return [];
    return data.months.map((m) => {
      const row = { label: m.label };
      for (const cat of data.categories) {
        const amt = m.by_category[cat.id] || 0;
        if (amt > 0) row[cat.name] = amt;
      }
      if (m.uncategorized > 0) row["Ongecategoriseerd"] = m.uncategorized;
      return row;
    });
  }, [data]);

  // Aggregate per category over the visible window. Filter out categories
  // with no spend; sort by total desc — biggest spend at the top.
  const summary = useMemo(() => {
    if (!data) return [];
    const rows = data.categories.map((cat) => {
      let total = 0;
      let activeMonths = 0;
      let latest = 0;
      for (let i = 0; i < data.months.length; i++) {
        const v = data.months[i].by_category[cat.id] || 0;
        if (v > 0) {
          total += v;
          activeMonths += 1;
        }
        if (i === data.months.length - 1) latest = v;
      }
      return {
        ...cat,
        total,
        avg: data.months.length ? total / data.months.length : 0,
        latest,
        activeMonths,
      };
    });
    const uncategorized = data.months.reduce((s, m) => s + (m.uncategorized || 0), 0);
    if (uncategorized > 0) {
      rows.push({
        id: null, name: "Ongecategoriseerd", color: "#475569", icon: "❔",
        total: uncategorized,
        avg: uncategorized / Math.max(data.months.length, 1),
        latest: data.months.length ? data.months[data.months.length - 1].uncategorized : 0,
        activeMonths: data.months.filter((m) => (m.uncategorized || 0) > 0).length,
      });
    }
    return rows.filter((r) => r.total > 0).sort((a, b) => b.total - a.total);
  }, [data]);

  // Top 8 categories drive the stacked bar — anything beyond that gets too
  // visually noisy. The summary table below shows all of them anyway.
  const stackedCats = useMemo(
    () => summary.filter((s) => s.id !== null).slice(0, 8),
    [summary],
  );

  // Per-category line chart shown when one row is "focused".
  const focusedSeries = useMemo(() => {
    if (!data || focusedId === null) return [];
    return data.months.map((m) => ({
      label: m.label,
      amount: focusedId === "uncategorized"
        ? (m.uncategorized || 0)
        : (m.by_category[focusedId] || 0),
    }));
  }, [data, focusedId]);

  const focusedMeta = useMemo(() => {
    if (focusedId === null) return null;
    return summary.find((s) => s.id === focusedId || (focusedId === "uncategorized" && s.id === null));
  }, [focusedId, summary]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Categorieën</h2>
          <p className="text-slate-500 text-sm">Uitgaven per categorie over de tijd</p>
        </div>
        <select
          className="select w-40"
          value={months}
          onChange={(e) => setMonths(Number(e.target.value))}
        >
          {PERIOD_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Stacked bar — top 8 categories per month. */}
      <div className="card">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">
          Uitgaven per maand (top 8 categorieën, gestapeld)
        </h3>
        {chartData.length === 0 ? (
          <p className="text-slate-600 text-sm text-center py-12">
            Nog geen data. Importeer eerst een bankafschrift.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="label" tick={{ fill: "#64748b", fontSize: 11 }} />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 11 }}
                tickFormatter={(v) => `€${(v / 1000).toFixed(1)}k`}
              />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
                formatter={(v) => fmt(v)}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {stackedCats.map((cat) => (
                <Bar key={cat.id} dataKey={cat.name} stackId="a" fill={cat.color} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Per-category drill-down line chart, appears when a row is focused. */}
      {focusedMeta && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: focusedMeta.color }} />
              {focusedMeta.icon} {focusedMeta.name} — verloop over {data?.months.length} maanden
            </h3>
            <button
              className="btn-ghost text-xs"
              onClick={() => setFocusedId(null)}
            >
              Sluiten
            </button>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={focusedSeries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="label" tick={{ fill: "#64748b", fontSize: 11 }} />
              <YAxis
                tick={{ fill: "#64748b", fontSize: 11 }}
                tickFormatter={(v) => `€${(v / 1000).toFixed(1)}k`}
              />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
                formatter={(v) => [fmt(v), focusedMeta.name]}
              />
              <Line
                type="monotone"
                dataKey="amount"
                stroke={focusedMeta.color}
                strokeWidth={2.5}
                dot={{ r: 3, fill: focusedMeta.color }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Summary table — sorted by total desc. */}
      <div className="card p-0 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800">
          <h3 className="text-sm font-semibold text-slate-300">
            Overzicht over {data?.months.length ?? months} {data?.months.length === 1 ? "maand" : "maanden"}
          </h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-800/30">
            <tr>
              <th className="text-left px-5 py-3 text-slate-400 font-medium">Categorie</th>
              <th className="text-right px-5 py-3 text-slate-400 font-medium">Totaal</th>
              <th className="text-right px-5 py-3 text-slate-400 font-medium">Gemiddeld/maand</th>
              <th className="text-right px-5 py-3 text-slate-400 font-medium">Afgelopen maand</th>
              <th className="text-right px-5 py-3 text-slate-400 font-medium">Actieve maanden</th>
              <th className="text-right px-5 py-3 text-slate-400 font-medium">Acties</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {summary.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-slate-600">
                  Geen uitgaven in deze periode.
                </td>
              </tr>
            ) : (
              summary.map((c) => {
                const focusKey = c.id === null ? "uncategorized" : c.id;
                const isFocused = focusedId === focusKey;
                return (
                  <tr
                    key={focusKey}
                    className={`hover:bg-slate-800/20 cursor-pointer ${
                      isFocused ? "bg-indigo-950/30" : ""
                    }`}
                    onClick={() => setFocusedId(isFocused ? null : focusKey)}
                  >
                    <td className="px-5 py-3">
                      <span className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full" style={{ background: c.color }} />
                        <span className="text-slate-200">{c.icon} {c.name}</span>
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right font-mono text-slate-200">{fmt(c.total)}</td>
                    <td className="px-5 py-3 text-right font-mono text-slate-400">{fmt(c.avg)}</td>
                    <td className="px-5 py-3 text-right font-mono text-slate-400">{fmt(c.latest)}</td>
                    <td className="px-5 py-3 text-right text-slate-500">
                      {c.activeMonths}/{data?.months.length}
                    </td>
                    <td className="px-5 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      {c.id !== null ? (
                        <Link
                          to={`/transactions?category_id=${c.id}`}
                          className="text-indigo-400 text-xs hover:text-indigo-300"
                        >
                          Transacties →
                        </Link>
                      ) : (
                        <span className="text-slate-700 text-xs">—</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-600">
        Klik op een rij voor een verloop-grafiek van die categorie. Overboekingen tussen eigen rekeningen worden niet meegeteld.
      </p>
    </div>
  );
}
