import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
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
      api.balanceHistory(12),
      api.fixedVariable(6),
      api.topCounterparties({ ...params, limit: 8 }),
      api.uncategorised(5),
      api.yearOverYear(4),
    ])
      .then(([summary, cashflow, categories, incomeCategories, balances, fixed, counterparties, todo, yoy]) => {
        setData({ summary, cashflow, categories, incomeCategories, balances, fixed, counterparties, todo, yoy });
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
  const { summary, cashflow, categories, incomeCategories, balances, fixed, counterparties, todo, yoy } = data;
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

      <section className="mb-6 grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-1 font-semibold">Saldoverloop</h3>
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
            Uit het saldo dat de bank zelf per transactie meestuurt — dus gelijk aan je afschrift.
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={(balances.periods || []).map((label, index) => ({
              label,
              total: balances.total[index],
              ...Object.fromEntries(balances.series.map((s) => [s.label, s.values[index]])),
            }))}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis dataKey="label" fontSize={11} />
              <YAxis fontSize={11} tickFormatter={(v) => `€${Math.round(v / 100) / 10}k`} />
              <Tooltip formatter={(v) => money(v)} />
              <Line type="monotone" dataKey="total" name="Totaal" stroke="#0ea5e9" strokeWidth={2} dot={false} />
              {balances.series.map((s, index) => (
                <Line
                  key={s.account_id}
                  type="monotone"
                  dataKey={s.label}
                  stroke={["#94a3b8", "#a78bfa", "#fbbf24", "#34d399", "#fb7185"][index % 5]}
                  strokeWidth={1}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h3 className="mb-1 font-semibold">Vaste versus variabele lasten</h3>
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
            {fixed.recurring_count} terugkerende betalingen herkend, samen{" "}
            <strong>{money(fixed.monthly_commitment)}</strong> per maand aan vaste verplichtingen.
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={fixed.months}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis dataKey="label" fontSize={11} />
              <YAxis fontSize={11} tickFormatter={(v) => `€${Math.round(v / 100) / 10}k`} />
              <Tooltip formatter={(v) => money(v)} />
              <Legend />
              <Bar dataKey="fixed" name="Vast" stackId="a" fill="#6366f1" />
              <Bar dataKey="variable" name="Variabel" stackId="a" fill="#c7d2fe" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
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
          <h3 className="mb-3 font-semibold">Grootste tegenpartijen deze periode</h3>
          {counterparties.length === 0 ? (
            <Empty>Geen uitgaven in deze periode.</Empty>
          ) : (
            <ul className="space-y-1 text-sm">
              {counterparties.map((row) => (
                <li key={row.name} className="flex justify-between gap-3">
                  <Link
                    className="truncate hover:underline"
                    to={`/tegenpartij?name=${encodeURIComponent(row.name.slice(0, 40))}`}
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
          )}
        </div>

        <div className="card">
          <h3 className="mb-1 font-semibold">Nog te categoriseren</h3>
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
            {todo.total_uncategorised} transacties zonder categorie — grootste bedragen eerst, want daar zit het geld.
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
      </section>
    </>
  );
}

/** One donut plus its legend. Used for both directions so they stay comparable. */
function CategoryDonut({ title, rows, empty }) {
  const total = (rows || []).reduce((sum, r) => sum + r.amount, 0);

  return (
    <div className="card">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="font-semibold">{title}</h3>
        <span className="text-sm tabular-nums text-slate-500 dark:text-slate-400">{money(total)}</span>
      </div>
      {!rows || rows.length === 0 ? (
        <Empty>{empty}</Empty>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={rows.slice(0, 8)} dataKey="amount" nameKey="name" innerRadius={50} outerRadius={82}>
                {rows.slice(0, 8).map((row) => <Cell key={row.name} fill={row.color} />)}
              </Pie>
              <Tooltip formatter={(v) => money(v)} />
            </PieChart>
          </ResponsiveContainer>
          <ul className="mt-2 space-y-1 text-sm">
            {rows.slice(0, 7).map((row) => (
              <li key={row.name} className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: row.color }} />
                  {row.category_id ? (
                    <Link className="truncate hover:underline" to={`/categorie/${row.category_id}`}>{row.name}</Link>
                  ) : (
                    <Link className="truncate hover:underline" to="/transacties?uncategorised=1">{row.name}</Link>
                  )}
                </span>
                <span className="whitespace-nowrap tabular-nums">
                  {money(row.amount)}
                  <span className="ml-1 text-xs text-slate-500">
                    {total ? Math.round((100 * row.amount) / total) : 0}%
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
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
