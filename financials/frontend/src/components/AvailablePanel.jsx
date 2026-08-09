import { Link } from "react-router-dom";
import { money, shortDate } from "../format.js";

/**
 * What is left of this period, how long it has to last, and how current the
 * data behind that claim actually is.
 *
 * The recency line is not decoration: "you have €62 left" means nothing if the
 * newest transaction is three weeks old, and the number would quietly mislead
 * rather than obviously fail.
 */
export default function AvailablePanel({ data }) {
  if (!data) return null;

  const { income, next_salary: salary } = data;
  const negative = data.available < 0;

  return (
    <section className="card mb-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="label">Vrij te besteden</p>
          <p className={`text-2xl font-semibold tabular-nums ${
            negative ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"
          }`}>
            {money(data.available)}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {data.days_left > 0
              ? <>nog {data.days_left} dagen{data.per_day !== null && <> · {money(data.per_day)} per dag</>}</>
              : "periode is afgelopen"}
          </p>
        </div>

        <div>
          <p className="label">Volgend loon</p>
          {salary ? (
            <>
              <p className="text-2xl font-semibold tabular-nums">{salary.days}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                dagen — {shortDate(salary.date)}
                {!salary.reliable && <span title={salary.note}> (schatting)</span>}
              </p>
            </>
          ) : (
            <>
              <p className="text-2xl font-semibold text-slate-400">—</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                <Link className="underline" to="/instellingen">stel je salarisbetaler in</Link>
              </p>
            </>
          )}
        </div>

        <div>
          <p className="label">Inkomsten deze periode</p>
          <p className="text-2xl font-semibold tabular-nums">{money(income.total)}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {income.variable > 0
              ? <>{money(income.fixed)} vast · {money(income.variable)} variabel</>
              : "alles als vast geteld"}
          </p>
        </div>

        <div>
          <p className="label">Gegevens bijgewerkt tot</p>
          <p className="text-2xl font-semibold tabular-nums">{shortDate(data.data_through)}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {data.stale_accounts.length === 0
              ? "alle rekeningen actueel"
              : `${data.stale_accounts.length} rekening${data.stale_accounts.length > 1 ? "en" : ""} loopt achter`}
          </p>
        </div>
      </div>

      {data.stale_accounts.length > 0 && (
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-100">
          Nog niet bijgewerkt:{" "}
          {data.stale_accounts.map((s) => `${s.label} (t/m ${shortDate(s.last_transaction)}, ${s.days_behind} dagen)`).join(" · ")}.
          Zolang die ontbreken is het bedrag hierboven te gunstig.
        </p>
      )}

      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-slate-500 dark:text-slate-400">
          Hoe is dit berekend?
        </summary>
        <div className="mt-2 space-y-1 text-xs text-slate-600 dark:text-slate-300">
          <p>
            {money(income.total)} binnengekomen − {money(data.spent)} uitgegeven −{" "}
            {money(data.committed)} nog te incasseren = <strong>{money(data.available)}</strong>
          </p>
          {data.upcoming.length > 0 ? (
            <>
              <p className="pt-1">Nog verwacht vóór het einde van de periode:</p>
              <ul className="space-y-0.5">
                {data.upcoming.map((item, index) => (
                  <li key={index} className="flex justify-between gap-3">
                    <span className="truncate">{shortDate(item.expected)} · {item.label}</span>
                    <span className="tabular-nums">{money(item.amount)}</span>
                  </li>
                ))}
              </ul>
              <p className="pt-1 text-slate-500 dark:text-slate-400">
                Alleen betalingen met een incassomachtiging tellen mee — die worden hoe dan ook
                afgeschreven. Boodschappen en dergelijke herhalen zich ook, maar zijn een keuze.
              </p>
            </>
          ) : (
            <p>Geen incasso's meer verwacht in deze periode.</p>
          )}
        </div>
      </details>
    </section>
  );
}
