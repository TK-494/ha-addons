import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import CategoryDonut, { transactionsLink } from "../components/CategoryDonut.jsx";
import PeriodPicker from "../components/PeriodPicker.jsx";
import { axisMoney, money, shortDate } from "../format.js";
import { usePeriod } from "../period.js";

/**
 * One page, two tabs: fixed expenses and variable expenses.
 *
 * They ask the same question from opposite sides — what lies fixed, and what
 * is yours to steer — so they share a component and stay directly comparable.
 * A category rendered blue on one page and green on the other would make the
 * reader do work the chart is meant to do.
 *
 * The period is the shared one, so it follows you from the overview. It
 * matters more here than there: one month of variable spending is mostly
 * noise, and "what does this actually cost me" only has an answer across
 * several — which is what the 3/6/12-month presets are for.
 */

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
  const period = usePeriod();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const copy = COPY[kind];

  useEffect(() => {
    if (!period.range) return;
    setData(null);
    api.expenseBreakdown(kind, period.params).then(setData).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, period.range?.from, period.range?.to]);

  if (error) return <Alert kind="error">{error}</Alert>;

  // A mean well above the median means outliers, not a higher normal month.
  const skewed = data && data.monthly_median > 0 && data.monthly_average > data.monthly_median * 1.25;

  return (
    <>
      <PageHeader title={copy.title} subtitle={copy.subtitle} />

      <div className="card mb-6 flex flex-wrap items-center justify-between gap-3">
        <PeriodPicker />
        {data && <span className="text-sm font-medium">{data.range.label}</span>}
      </div>

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
                {data.one_off.transactions > 0 && (
                  <>
                    {" "}— inclusief {data.one_off.transactions} eenmalige{" "}
                    {data.one_off.transactions === 1 ? "aankoop" : "aankopen"}
                  </>
                )}
              </p>
            </div>
            <div className="card">
              <p className="label">Mediaan per maand</p>
              <p className="text-2xl font-semibold tabular-nums">{money(data.monthly_median)}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                gemiddeld {money(data.monthly_average)} over {data.range.periods}{" "}
                {data.range.periods === 1 ? "periode" : "perioden"}
                {data.one_off.transactions > 0 && (
                  <>
                    {" "}· {money(data.one_off.total)} eenmalig niet meegerekend
                  </>
                )}
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
                range={data.range}
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
                        <Link className="hover:underline" to={transactionsLink(row, data.range)} title="Alle transacties in deze periode">
                          {row.name}
                        </Link>
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

          {data.round_trip.parties.length > 0 && (
            <Alert kind="warning">
              <p className="mb-2">
                <strong>{money(data.round_trip.total)}</strong> ({data.round_trip.share}% van dit
                totaal) ging naar rekeningen die je in deze periode óók geld hebben betaald. Dat is
                zelden een uitgave: meestal een eigen spaar- of beleggingsrekening die de app niet
                kent, een gezamenlijke rekening, of iemand met wie je verrekent.
              </p>
              <ul className="mb-2 space-y-0.5 text-xs">
                {data.round_trip.parties.map((party) => (
                  <li key={party.iban} className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-medium">{party.name}</span>
                    <span className="tabular-nums">
                      {money(party.paid_out)} eruit, {money(party.received)} erin — netto{" "}
                      <strong>{money(party.net)}</strong>
                    </span>
                    <Link className="underline" to={`/transacties?search=${encodeURIComponent(party.iban)}`}>
                      bekijk
                    </Link>
                  </li>
                ))}
              </ul>
              <p className="text-xs">
                Is het een eigen rekening? Voeg het IBAN toe onder{" "}
                <Link className="underline" to="/rekeningen">Rekeningen</Link> — dan worden deze
                overboekingen intern en verdwijnen ze uit je uitgaven én je inkomsten.
              </p>
            </Alert>
          )}

          {skewed && (
            <Alert kind="warning">
              <p className="mb-1">
                Het gemiddelde ({money(data.monthly_average)}) ligt{" "}
                {Math.round((data.monthly_average / data.monthly_median - 1) * 100)}% boven de mediaan
                ({money(data.monthly_median)}). Eén of enkele maanden trekken het omhoog — het
                gemiddelde beschrijft dus geen normale maand.
              </p>
              {data.busiest_period && (
                <p className="text-xs">
                  De duurste was <strong>{data.busiest_period.label}</strong> met{" "}
                  {money(data.busiest_period.amount)}. Was het een eenmalige aankoop, open hem dan bij
                  Transacties met <strong>⋯</strong> en kies <em>Markeer als eenmalig</em> — hij
                  blijft dan in je totaal staan, maar valt uit het gemiddelde en de mediaan.{" "}
                  <Link className="underline" to={`${transactionsLink({}, data.range)}&direction=out&sort=amount&desc=0`}>
                    Bekijk de grootste uitgaven in deze periode
                  </Link>{" "}
                  om te zien wat daar in zat. Staat er een overboeking naar een eigen rekening
                  tussen, voeg die rekening dan toe onder{" "}
                  <Link className="underline" to="/rekeningen">Rekeningen</Link> — dan telt hij
                  voortaan niet meer als uitgave.
                </p>
              )}
            </Alert>
          )}

          <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">{copy.note}</p>
        </>
      )}
    </>
  );
}
