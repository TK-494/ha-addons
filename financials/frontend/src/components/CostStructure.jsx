import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { money, shortDate } from "../format.js";

/**
 * Fixed versus variable, spelled out.
 *
 * A stacked bar answers "how much" and nothing else. What you actually want to
 * know is *which* costs are fixed, because that is the list you would have to
 * renegotiate to change anything — so it is shown item by item, with the
 * variable side broken down by category next to it.
 *
 * "Recurring" is deliberately not the same as "fixed": the supermarket repeats
 * every week too. A cost counts as fixed when somebody has a mandate to
 * collect it, or when it repeats at a stable amount (which catches card
 * subscriptions).
 */
export default function CostStructure({ data, trend }) {
  if (!data) return null;

  const share = data.share_fixed ?? 0;
  const items = data.items.slice(0, 8);

  return (
    <section className="card mb-6">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="font-semibold">Vaste en variabele lasten</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {shortDate(data.period.start)} t/m {shortDate(data.period.end)}
          </p>
        </div>
        <Link className="btn-ghost" to="/terugkerend">Alle terugkerende betalingen</Link>
      </div>

      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <div>
          <p className="label">Vast deze periode</p>
          <p className="text-2xl font-semibold tabular-nums text-indigo-600 dark:text-indigo-400">
            {money(data.period_fixed)}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {money(data.monthly_commitment)} per maand aan verplichtingen
          </p>
        </div>
        <div>
          <p className="label">Variabel deze periode</p>
          <p className="text-2xl font-semibold tabular-nums text-sky-600 dark:text-sky-400">
            {money(data.period_variable)}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">hier kun je aan draaien</p>
        </div>
        <div>
          <p className="label">Over na vaste lasten</p>
          <p className="text-2xl font-semibold tabular-nums">{money(data.left_after_fixed)}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {data.fixed_share_of_income !== null
              ? `vast slokt ${data.fixed_share_of_income}% van je inkomen op`
              : "geen inkomsten deze periode"}
          </p>
        </div>
      </div>

      {/* One bar, honestly proportional — the quickest read of the whole thing. */}
      <div className="mb-1 flex h-6 overflow-hidden rounded-lg">
        <div
          className="flex items-center justify-center bg-indigo-500 text-[11px] font-medium text-white"
          style={{ width: `${share}%` }}
          title={`Vast ${money(data.period_fixed)}`}
        >
          {share >= 12 && `${share}% vast`}
        </div>
        <div
          className="flex items-center justify-center bg-sky-300 text-[11px] font-medium text-sky-900 dark:bg-sky-700 dark:text-sky-50"
          style={{ width: `${100 - share}%` }}
          title={`Variabel ${money(data.period_variable)}`}
        >
          {100 - share >= 12 && `${Math.round(100 - share)}% variabel`}
        </div>
      </div>
      <p className="mb-5 text-xs text-slate-500 dark:text-slate-400">
        Van elke euro die uitgaat ligt {Math.round(share)} cent vast.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <h4 className="mb-2 text-sm font-semibold">Waar de vaste lasten in zitten</h4>
          <ul className="space-y-1 text-sm">
            {items.map((item) => (
              <li key={item.label} className="flex items-baseline justify-between gap-3">
                <span className="min-w-0">
                  <span className="truncate">{item.label}</span>
                  <span className="ml-1 text-xs text-slate-500 dark:text-slate-400">
                    {item.interval}
                    {!item.mandated && " · geen machtiging"}
                    {item.amount_changed && " · bedrag gewijzigd"}
                  </span>
                </span>
                <span className="whitespace-nowrap tabular-nums">{money(item.monthly)}</span>
              </li>
            ))}
          </ul>
          {data.items.length > items.length && (
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              en nog {data.items.length - items.length} kleinere posten.
            </p>
          )}
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            {data.excluded_recurring} andere posten keren wel terug maar tellen niet als vast: het
            bedrag wisselt en er is geen machtiging, dus je kunt ze overslaan.
          </p>
        </div>

        <div>
          <h4 className="mb-2 text-sm font-semibold">Waar het variabele geld heen ging</h4>
          {data.variable_by_category.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Geen variabele uitgaven in deze periode.
            </p>
          ) : (
            <ul className="space-y-1 text-sm">
              {data.variable_by_category.slice(0, 8).map((row) => (
                <li key={row.name} className="flex items-baseline justify-between gap-3">
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: row.color }} />
                    <span className="truncate">{row.name}</span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">{row.transactions}×</span>
                  </span>
                  <span className="whitespace-nowrap tabular-nums">{money(row.amount)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {trend?.months?.length > 0 && (
        <details className="mt-5">
          <summary className="cursor-pointer text-sm text-slate-500 dark:text-slate-400">
            Verloop over de afgelopen maanden
          </summary>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trend.months}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis dataKey="label" fontSize={11} />
              <YAxis fontSize={11} tickFormatter={(v) => `€${Math.round(v / 100) / 10}k`} />
              <Tooltip formatter={(v) => money(v)} />
              <Legend />
              <Bar dataKey="fixed" name="Vast" stackId="a" fill="#6366f1" />
              <Bar dataKey="variable" name="Variabel" stackId="a" fill="#7dd3fc" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </details>
      )}
    </section>
  );
}
