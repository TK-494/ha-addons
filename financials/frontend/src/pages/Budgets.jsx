import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { money } from "../format.js";

const MONTHS = [
  "januari", "februari", "maart", "april", "mei", "juni",
  "juli", "augustus", "september", "oktober", "november", "december",
];

export default function Budgets() {
  const [period, setPeriod] = useState(null);
  const [data, setData] = useState(null);
  const [suggestions, setSuggestions] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = (next) => {
    api.budgets(next || period || {})
      .then((result) => {
        setData(result);
        if (!period) setPeriod({ year: result.year, month: result.month });
      })
      .catch((e) => setError(e.message));
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [period?.year, period?.month]);

  const shift = (delta) => {
    const index = period.year * 12 + (period.month - 1) + delta;
    setPeriod({ year: Math.floor(index / 12), month: (index % 12) + 1 });
  };

  async function save(categoryId, amount, rollover) {
    try {
      await api.upsertBudget({
        category_id: categoryId, year: data.year, month: data.month,
        amount: Number(amount) || 0, rollover,
      });
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  if (!data) return <Spinner />;

  const spentShare = data.total_available
    ? Math.round((100 * data.total_spent) / data.total_available)
    : null;

  return (
    <>
      <PageHeader
        title="Budget"
        subtitle={
          data.total_available
            ? `${money(data.total_spent)} van ${money(data.total_available)} besteed` +
              (spentShare !== null ? ` (${spentShare}%)` : "")
            : "Nog geen budgetten ingesteld voor deze maand"
        }
      >
        <div className="flex items-center gap-1">
          <button className="btn-ghost" onClick={() => shift(-1)}>‹</button>
          <span className="min-w-[9rem] text-center text-sm font-medium">
            {MONTHS[data.month - 1]} {data.year}
          </span>
          <button className="btn-ghost" onClick={() => shift(1)}>›</button>
        </div>
        <button
          className="btn-ghost"
          onClick={async () => {
            const result = await api.copyPreviousBudgets(data.year, data.month);
            setNotice(`${result.copied} budgetten overgenomen van vorige maand.`);
            load();
          }}
        >
          Vorige maand overnemen
        </button>
        <button
          className="btn-ghost"
          onClick={async () => setSuggestions(await api.suggestBudgets(data.year, data.month, 6))}
        >
          Voorstel op basis van historie
        </button>
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      {suggestions && (
        <section className="card mb-4">
          <h3 className="mb-1 font-semibold">Voorstel</h3>
          <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
            De mediaan van de laatste {suggestions.based_on_months} maanden — niet het gemiddelde, zodat
            één vakantie je boodschappenbudget niet omhoog trekt. Er is nog niets opgeslagen.
          </p>
          <ul className="mb-3 grid gap-1 text-sm sm:grid-cols-2">
            {suggestions.proposals.slice(0, 12).map((p) => (
              <li key={p.category_id} className="flex justify-between gap-2">
                <span className="truncate">{p.category_name}</span>
                <span className="tabular-nums">{money(p.suggested)}</span>
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <button
              className="btn-primary"
              onClick={async () => {
                for (const p of suggestions.proposals) {
                  await api.upsertBudget({
                    category_id: p.category_id, year: data.year, month: data.month,
                    amount: p.suggested, rollover: false,
                  });
                }
                setSuggestions(null);
                setNotice("Voorstel overgenomen.");
                load();
              }}
            >
              Alles overnemen
            </button>
            <button className="btn-ghost" onClick={() => setSuggestions(null)}>Sluiten</button>
          </div>
        </section>
      )}

      {data.rows.length === 0 ? (
        <Empty>Nog geen uitgaven of budgetten in deze maand.</Empty>
      ) : (
        <div className="space-y-2">
          {data.rows.map((row) => {
            // A category with no budget is *unbudgeted*, not overspent — it
            // must not be flagged red as though a limit had been breached.
            const budgeted = row.available > 0;
            const over = budgeted && row.remaining < 0;
            const percentage = budgeted ? Math.min(100, row.percentage ?? 0) : 0;
            return (
              <article key={row.category_id} className="card">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <Link className="font-medium hover:underline" to={`/categorie/${row.category_id}`}>
                    {row.category_name}
                  </Link>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="tabular-nums">{money(row.spent)}</span>
                    <span className="text-slate-400">van</span>
                    <input
                      type="number"
                      step="5"
                      min="0"
                      className="input w-28 text-right"
                      defaultValue={row.planned || ""}
                      placeholder="0"
                      onBlur={(e) => {
                        if (Number(e.target.value || 0) !== row.planned) {
                          save(row.category_id, e.target.value, row.rollover);
                        }
                      }}
                    />
                    <label className="flex items-center gap-1 text-xs" title="Wat je overhoudt schuift door naar volgende maand">
                      <input
                        type="checkbox"
                        checked={row.rollover}
                        onChange={(e) => save(row.category_id, row.planned, e.target.checked)}
                      />
                      doorschuiven
                    </label>
                  </div>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                  <div
                    className={`h-full rounded-full ${over ? "bg-rose-500" : ""}`}
                    style={{ width: `${percentage}%`, backgroundColor: over ? undefined : row.color }}
                  />
                </div>

                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  {!budgeted ? (
                    `geen budget ingesteld · ${money(row.spent)} uitgegeven`
                  ) : over ? (
                    <span className="text-rose-600 dark:text-rose-400">
                      {money(Math.abs(row.remaining))} over budget
                    </span>
                  ) : (
                    `${money(row.remaining)} over`
                  )}
                  {row.carried_over > 0 && ` · ${money(row.carried_over)} meegenomen uit vorige maand`}
                </p>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}
