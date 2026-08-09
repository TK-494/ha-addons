import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import AvailablePanel from "../components/AvailablePanel.jsx";
import CategoryDonut from "../components/CategoryDonut.jsx";
import { money } from "../format.js";

const MONTHS = [
  "januari", "februari", "maart", "april", "mei", "juni",
  "juli", "augustus", "september", "oktober", "november", "december",
];

export default function Overview() {
  const [period, setPeriod] = useState(null);
  const [accountId, setAccountId] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [data, setData] = useState({});
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.accounts().then(setAccounts).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = { account_id: accountId || undefined, ...(period || {}) };
    Promise.all([
      api.summary(params),
      api.cashflow({ months: 12, account_id: accountId || undefined }),
      api.byCategory(params),
      api.byCategory({ ...params, direction: "in" }),
      api.uncategorised(5),
      api.yearOverYear(4),
      api.availableThisPeriod(period || {}),
    ])
      .then(([summary, cashflow, categories, incomeCategories, todo, yoy, available]) => {
        setData({ summary, cashflow, categories, incomeCategories, todo, yoy, available });
        if (!period) setPeriod({ year: summary.year, month: summary.month });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, period?.year, period?.month]);

  const shift = (delta) => {
    const index = period.year * 12 + (period.month - 1) + delta;
    setPeriod({ year: Math.floor(index / 12), month: (index % 12) + 1 });
  };

  if (loading && !data.summary) return <Spinner label="Overzicht laden…" />;
  const { summary, cashflow, categories, incomeCategories, todo, yoy, available } = data;
  if (!summary) return <Empty>Nog geen gegevens. Importeer eerst een CSV-bestand.</Empty>;


  return (
    <>
      <PageHeader
        title="Overzicht"
        subtitle={
          accountId
            ? "Eén rekening — overboekingen naar je eigen rekeningen tellen hier wél mee"
            : "Huishouden — overboekingen tussen je eigen rekeningen zijn eruit gefilterd"
        }
      >
        <select className="input w-auto" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
          <option value="">Alle rekeningen (huishouden)</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
        </select>
        <div className="flex items-center gap-1">
          <button className="btn-ghost" onClick={() => shift(-1)}>‹</button>
          <span className="min-w-[9rem] text-center text-sm font-medium">
            {MONTHS[summary.month - 1]} {summary.year}
          </span>
          <button className="btn-ghost" onClick={() => shift(1)}>›</button>
        </div>
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <AvailablePanel data={available} />

      <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Inkomsten" value={summary.income} delta={summary.delta_income} good="up" />
        <Kpi label="Uitgaven" value={Math.abs(summary.expenses)} delta={summary.delta_expenses} good="down" />
        <Kpi label="Netto" value={summary.net} />
<div className="card">
          <p className="label">Gespaard</p>
          {summary.savings_accounts === 0 ? (
            <>
              <p className="text-xl font-semibold text-slate-400">—</p>
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Geen spaarrekening ingesteld —{" "}
                <Link className="underline" to="/rekeningen">zet er één op Rekeningen</Link>
              </p>
            </>
          ) : (
            <>
              <p className="text-xl font-semibold tabular-nums">{money(summary.saved)}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {summary.savings_rate === null
                  ? "geen inkomsten deze periode"
                  : `spaarquote ${summary.savings_rate}%`}
              </p>
            </>
          )}
        </div>
      </section>

      <section className="card mb-6">
        <h3 className="mb-3 font-semibold">Inkomsten en uitgaven per maand</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={cashflow}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="label" fontSize={11} />
            <YAxis fontSize={11} tickFormatter={(v) => `€${Math.round(v / 100) / 10}k`} />
            <Tooltip formatter={(v) => money(v)} />
            <Legend />
            <Bar dataKey="income" name="Bij" fill="#10b981" radius={[3, 3, 0, 0]} />
            <Bar dataKey="expenses" name="Af" fill="#f43f5e" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* Both directions side by side and at the same size, so "where does it
          go" and "where does it come from" are equally readable. */}
      <section className="mb-6 grid gap-4 lg:grid-cols-2">
        <CategoryDonut
          title="Uitgaven per categorie"
          rows={categories}
          empty="Geen uitgaven in deze periode."
        />
        <CategoryDonut
          title="Inkomsten per categorie"
          rows={incomeCategories}
          empty="Geen inkomsten in deze periode."
        />
      </section>



      <section className="card mb-6">
        <h3 className="mb-1 font-semibold">Jaar op jaar</h3>
        <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
          Interne overboekingen zijn ook hier weggelaten, dus dit is wat het huishouden werkelijk
          binnenkreeg en uitgaf.
        </p>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr>
                <th className="th">Jaar</th>
                <th className="th text-right">Bij</th>
                <th className="th text-right">Af</th>
                <th className="th text-right">Netto</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {(yoy || []).map((row) => (
                <tr key={row.year}>
                  <td className="td font-medium">{row.year}</td>
                  <td className="td text-right tabular-nums">{money(row.income)}</td>
                  <td className="td text-right tabular-nums">{money(row.expenses)}</td>
                  <td className={`td text-right tabular-nums font-medium ${row.income - row.expenses < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                    {money(row.income - row.expenses)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <h3 className="font-semibold">Nog te categoriseren</h3>
            <Link className="text-sm hover:underline" to="/te-categoriseren">Aan de slag →</Link>
          </div>
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
            {todo.total_uncategorised} transacties zonder categorie, samen {money(todo.total_amount)}.
            Grootste bedragen eerst — daar vertekent het je cijfers het meest.
          </p>
          {todo.groups.length === 0 ? (
            <Empty>Alles is gecategoriseerd.</Empty>
          ) : (
            <ul className="space-y-1 text-sm">
              {todo.groups.map((group) => (
                <li key={group.name} className="flex justify-between gap-3">
                  <Link
                    className="truncate hover:underline"
                    to={`/transacties?search=${encodeURIComponent(group.name.slice(0, 24))}&uncategorised=1`}
                  >
                    {group.name}
                  </Link>
                  <span className="whitespace-nowrap tabular-nums">
                    {money(Math.abs(group.amount))}
                    <span className="ml-1 text-xs text-slate-500">{group.transactions}×</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* The detail these used to show on this page now lives on its own tab;
            what belongs here is the way in, not a second copy. */}
        <div className="card">
          <h3 className="mb-3 font-semibold">Verder kijken</h3>
          <ul className="space-y-2 text-sm">
            <li>
              <Link className="font-medium hover:underline" to="/vaste-lasten">Vaste lasten →</Link>
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                Wat er hoe dan ook afgaat, per categorie en over 1 tot 12 maanden of alles.
              </span>
            </li>
            <li>
              <Link className="font-medium hover:underline" to="/variabele-uitgaven">Variabele uitgaven →</Link>
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                Waar je zelf aan kunt draaien, met de grootste tegenpartijen.
              </span>
            </li>
            <li>
              <Link className="font-medium hover:underline" to="/rekeningen">Rekeningen →</Link>
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                Saldi per rekening en het saldoverloop over de tijd.
              </span>
            </li>
            <li>
              <Link className="font-medium hover:underline" to="/terugkerend">Terugkerend →</Link>
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                Abonnementen en incasso's, te filteren op ritme en bedrag.
              </span>
            </li>
          </ul>
        </div>
      </section>
    </>
  );
}

function Kpi({ label, value, delta, good }) {
  // "Better" differs per metric: more income is good, more expense is not.
  const improved = delta === undefined ? null : good === "down" ? delta < 0 : delta > 0;
  return (
    <div className="card">
      <p className="label">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{money(value)}</p>
      {delta !== undefined && (
        <p className={`text-xs ${improved ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
          {delta >= 0 ? "+" : ""}{money(delta)} t.o.v. vorige periode
        </p>
      )}
    </div>
  );
}
