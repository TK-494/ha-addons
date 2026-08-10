import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import CategoryDonut from "../components/CategoryDonut.jsx";
import { axisMoney, money, shortDate } from "../format.js";

/**
 * One page, two tabs: fixed expenses and variable expenses.
 *
 * They ask the same question from opposite sides — what lies fixed, and what
 * is yours to steer — so they share a component and stay directly comparable.
 * A category rendered blue on one page and green on the other would make the
 * reader do work the chart is meant to do.
 *
 * The range selector matters more here than on the overview: one month of
 * variable spending is mostly noise, and "what does this actually cost me"
 * only has an answer across several.
 */
const RANGES = [
  { value: 1, label: "Deze periode" },
  { value: 3, label: "3 maanden" },
  { value: 6, label: "6 maanden" },
  { value: 12, label: "12 maanden" },
  { value: 0, label: "Alles" },
];

const COPY = {
  fixed: {
    title: "Vaste lasten",
    subtitle: "Wat er hoe dan ook afgaat — incasso's en abonnementen met een vast bedrag",
    empty: "Geen vaste lasten in deze periode.",
    accent: "text-indigo-600 dark:text-indigo-400",
    bar: "#6366f1",
    note: (
      <>
        Een uitgave telt als vast wanneer er een <strong>incassomachtiging</strong> op zit — ook als
        het bedrag schommelt, zoals bij een verzekeringspremie — of wanneer het{" "}
        <strong>elke keer hetzelfde bedrag</strong> is, wat abonnementen op je creditcard vangt.
      </>
    ),
  },
  variable: {
    title: "Variabele uitgaven",
    subtitle: "Wat je zelf stuurt — boodschappen, tanken, uit eten, aankopen",
    empty: "Geen variabele uitgaven in deze periode.",
    accent: "text-sky-600 dark:text-sky-400",
    bar: "#0ea5e9",
    note: (
      <>
        Alles wat geen machtiging heeft en waarvan het bedrag wisselt. Een uitgave die elke week
        terugkeert kan hier prima staan: de supermarkt herhaalt zich, maar je kunt hem overslaan.
      </>
    ),
  },
};

export default function Expenses({ kind }) {
  const [months, setMonths] = useState(6);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const copy = COPY[kind];

  useEffect(() => {
    setData(null);
    api.expenseBreakdown(kind, months).then(setData).catch((e) => setError(e.message));
  }, [kind, months]);

  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <>
      <PageHeader title={copy.title} subtitle={copy.subtitle}>
        <div className="flex flex-wrap gap-1">
          {RANGES.map((range) => (
            <button
              key={range.value}
              className={months === range.value ? "btn-primary" : "btn-ghost"}
              onClick={() => setMonths(range.value)}
            >
              {range.label}
            </button>
          ))}
        </div>
      </PageHeader>

      {!data ? (
        <Spinner />
      ) : data.total === 0 ? (
        <Empty>{copy.empty}</Empty>
      ) : (
        <>
          <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="card">
              <p className="label">Totaal</p>
              <p className={`text-2xl font-semibold tabular-nums ${copy.accent}`}>{money(data.total)}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {shortDate(data.range.start)} t/m {shortDate(data.range.end)}
              </p>
            </div>
            <div className="card">
              <p className="label">Gemiddeld per maand</p>
              <p className="text-2xl font-semibold tabular-nums">{money(data.monthly_average)}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                over {data.range.periods} {data.range.periods === 1 ? "periode" : "perioden"}
              </p>
            </div>
            <div className="card">
              <p className="label">Aandeel van alle uitgaven</p>
              <p className="text-2xl font-semibold tabular-nums">
                {data.share_of_expenses === null ? "—" : `${data.share_of_expenses}%`}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {kind === "fixed"
                  ? `${money(data.variable_total)} was variabel`
                  : `${money(data.fixed_total)} lag vast`}
              </p>
            </div>
            <div className="card">
              <p className="label">Transacties</p>
              <p className="text-2xl font-semibold tabular-nums">{data.transactions}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {data.by_category.length} categorieën
              </p>
            </div>
          </section>

          <section className="mb-6 grid gap-4 lg:grid-cols-2">
            <div className="card">
              <CategoryDonut
                rows={data.by_category}
                title="Per categorie"
                empty={copy.empty}
                height={280}
                legend={10}
              />
            </div>

            <div className="card">
              <h3 className="mb-3 font-semibold">Grootste tegenpartijen</h3>
              <ul className="space-y-1 text-sm">
                {data.top_counterparties.map((row) => (
                  <li key={row.name} className="flex items-baseline justify-between gap-3">
                    <Link
                      className="truncate hover:underline"
                      to={`/transacties?search=${encodeURIComponent(row.name.slice(0, 24))}`}
                    >
                      {row.name}
                    </Link>
                    <span className="whitespace-nowrap tabular-nums">
                      {money(row.amount)}
                      <span className="ml-1 text-xs text-slate-500">{row.transactions}×</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          {data.trend.length > 1 && (
            <section className="card mb-6">
              <h3 className="mb-3 font-semibold">Verloop</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={data.trend}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="label" fontSize={11} />
                  <YAxis fontSize={11} tickFormatter={axisMoney} />
                  <Tooltip formatter={(v) => money(v)} />
                  <Bar dataKey="amount" name={copy.title} fill={copy.bar} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </section>
          )}

          <section className="card overflow-x-auto p-0">
            <table className="min-w-full">
              <thead className="border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="th">Categorie</th>
                  <th className="th text-right">Bedrag</th>
                  <th className="th text-right">Per maand</th>
                  <th className="th text-right">Aandeel</th>
                  <th className="th text-right">Transacties</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {data.by_category.map((row) => (
                  <tr key={row.name}>
                    <td className="td">
                      <span className="flex items-center gap-2">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: row.color }} />
                        {row.name}
                      </span>
                    </td>
                    <td className="td text-right tabular-nums">{money(row.amount)}</td>
                    <td className="td text-right tabular-nums text-slate-500 dark:text-slate-400">
                      {money(row.amount / data.range.periods)}
                    </td>
                    <td className="td text-right tabular-nums">{row.share}%</td>
                    <td className="td text-right tabular-nums">{row.transactions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">{copy.note}</p>
        </>
      )}
    </>
  );
}
