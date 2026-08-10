import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Alert, PageHeader, Spinner } from "../components/Bits.jsx";
import { maskAccount, money, shortDate } from "../format.js";
import { THEMES, applyTheme } from "../theme.js";

const MODES = [
  { value: "calendar", label: "Kalendermaand (1e van de maand)" },
  { value: "salary", label: "Salarisdag — de dag waarop het écht binnenkwam" },
  { value: "day", label: "Vaste dag van de maand" },
];

const MONTHS = [
  "jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec",
];

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [theme, setTheme] = useState(null);

  useEffect(() => {
    api.periodSettings().then(setSettings).catch((e) => setError(e.message));
    api.accounts().then(setAccounts).catch(() => {});
    api.appearance().then((a) => setTheme(a.theme)).catch(() => {});
  }, []);

  const apply = (promise, message) =>
    promise
      .then((result) => { setSettings(result); if (message) setNotice(message); })
      .catch((e) => setError(e.message));

  function savePeriod(patch) {
    api.savePeriodSettings({ mode: settings.mode, start_day: settings.start_day, ...patch })
      .then((result) => {
        setSettings(result);
        setNotice(
          result.auto_selected_salary_source
            ? `Opgeslagen. “${result.auto_selected_salary_source}” automatisch als salarisbetaler gekozen — pas het hieronder aan als dat niet klopt.`
            : "Opgeslagen."
        );
      })
      .catch((e) => setError(e.message));
  }

  function saveSalary(patch) {
    apply(api.saveSalarySource({
      counterparty: settings.salary.counterparty,
      account_id: settings.salary.account_id,
      min_amount: settings.salary.min_amount,
      ...patch,
    }), "Salarisbron opgeslagen.");
  }

  if (!settings) return <Spinner />;

  return (
    <>
      <PageHeader title="Instellingen" />

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      <section className="card mb-4 max-w-2xl">
        <h3 className="mb-1 font-semibold">Uiterlijk</h3>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
          Home Assistant geeft zijn eigen thema niet door aan een add-on — die draait in een eigen
          venster en daar is geen koppeling voor. Kies hier dus hetzelfde thema als in HA, dan sluiten
          ze op elkaar aan. Licht of donker volgt je systeeminstelling, net als in HA.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {THEMES.map((option) => (
            <button
              key={option.value}
              onClick={async () => {
                setTheme(option.value);
                applyTheme(option.value);
                try { localStorage.setItem("financials.theme", option.value); } catch { /* ignore */ }
                try {
                  await api.saveAppearance(option.value);
                  setNotice(`Thema ${option.label} ingesteld.`);
                } catch (e) {
                  setError(e.message);
                }
              }}
              className={`rounded-xl border p-3 text-left transition-colors ${
                theme === option.value
                  ? "border-sky-500 ring-2 ring-sky-500/40"
                  : "border-slate-300 hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-700"
              }`}
            >
              <span className="mb-2 flex gap-1">
                {option.swatches.map((colour) => (
                  <span key={colour} className="h-5 w-5 rounded-full" style={{ backgroundColor: colour }} />
                ))}
              </span>
              <span className="block font-medium">{option.label}</span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">{option.description}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="card mb-4 max-w-2xl">
        <h3 className="mb-1 font-semibold">Maandgrens</h3>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
          Bepaalt waar een maand begint in de overzichten. Puur een weergave-instelling: er wordt niets
          herschreven, dus je kunt vrij wisselen zonder opnieuw te importeren.
        </p>

        <div className="mb-3">
          <label className="label">Maand begint op</label>
          <select
            className="input"
            value={settings.mode}
            onChange={(e) => savePeriod({ mode: e.target.value })}
          >
            {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>

        {settings.mode === "day" && (
          <div className="mb-3 max-w-[8rem]">
            <label className="label">Dag (1–28)</label>
            <input
              type="number"
              min="1"
              max="28"
              className="input"
              defaultValue={settings.start_day}
              onBlur={(e) => savePeriod({ start_day: Number(e.target.value) })}
            />
          </div>
        )}

        {settings.mode === "salary" && !settings.salary.configured && (
          <Alert kind="warning">
            <strong>Er is nog geen salarisbetaler ingesteld</strong>, dus er valt geen salarisdatum te
            vinden en elke maand valt terug op dag {settings.effective_day}. Daarmee doet deze stand
            precies hetzelfde als <em>Vaste dag</em>: een salaris dat op de 22e binnenkwam telt dan
            nog steeds mee met de vorige maand. Kies hieronder wie je salaris betaalt.
          </Alert>
        )}

        {settings.mode === "salary" && (
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Elke maand begint op de dag dat je salaris werkelijk geboekt is. Valt de vaste betaaldag in
            het weekend of rond de feestdagen, dan schuift de grens mee.{" "}
            {settings.shifted_months > 0 && (
              <>
                Bij jou wijken <strong>{settings.shifted_months}</strong> maanden af van de vaste dag —
                zonder deze instelling zou het salaris in die maanden in de vórige periode vallen.
              </>
            )}{" "}
            Voor maanden zonder gevonden salaris geldt dag{" "}
            <strong>{settings.effective_day}</strong> als terugval.
          </p>
        )}
      </section>

      {settings.mode === "salary" && (
        <>
          <section className="card mb-4 max-w-2xl">
            <h3 className="mb-1 font-semibold">Welke betaling is je salaris?</h3>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
              Op naam van de betaler, niet op bedrag. Een drempel als “inkomsten boven €1.000” pikt ook
              leningen en teruggaves op, en die komen op willekeurige dagen binnen — dan schuift je
              maandgrens met ze mee.
            </p>

            {settings.suggestions.length > 0 && !settings.salary.configured && (
              <div className="mb-3">
                <p className="label">Gevonden in je gegevens</p>
                <div className="flex flex-wrap gap-2">
                  {settings.suggestions.map((s) => (
                    <button
                      key={s.counterparty}
                      className="btn-ghost text-left"
                      onClick={() => saveSalary({ counterparty: s.counterparty })}
                    >
                      {s.counterparty}
                      <span className="ml-2 text-xs text-slate-500">
                        {s.payments}× · gem. {money(s.average_amount)}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-2">
                <label className="label">Naam van de betaler bevat</label>
                <input
                  className="input"
                  defaultValue={settings.salary.counterparty}
                  placeholder="bijv. de naam van je werkgever"
                  onBlur={(e) => {
                    if (e.target.value !== settings.salary.counterparty) {
                      saveSalary({ counterparty: e.target.value });
                    }
                  }}
                />
              </div>
              <div>
                <label className="label">Minimaal bedrag</label>
                <input
                  type="number"
                  step="50"
                  min="0"
                  className="input"
                  defaultValue={settings.salary.min_amount}
                  onBlur={(e) => {
                    if (Number(e.target.value) !== settings.salary.min_amount) {
                      saveSalary({ min_amount: Number(e.target.value) });
                    }
                  }}
                />
              </div>
              <div className="sm:col-span-3">
                <label className="label">Op rekening (optioneel)</label>
                <select
                  className="input"
                  value={settings.salary.account_id || ""}
                  onChange={(e) => saveSalary({ account_id: e.target.value ? Number(e.target.value) : null })}
                >
                  <option value="">Alle rekeningen</option>
                  {accounts.map((a) => <option key={a.id} value={a.id}>{maskAccount(a.label)}</option>)}
                </select>
              </div>
            </div>

            {settings.salary.configured && (
              <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
                Gebruikelijke betaaldag: de <strong>{settings.detected_salary_day || settings.effective_day}e</strong>.
              </p>
            )}
          </section>

          <section className="card">
            <h3 className="mb-1 font-semibold">Grenzen per maand</h3>
            <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
              Klopt een maand niet, pas de datum hier aan. Een handmatige correctie wint altijd van de
              gevonden salarisdatum; met <em>herstel</em> laat je hem weer los.
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead className="border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="th">Periode</th>
                    <th className="th">Begint op</th>
                    <th className="th">Bron</th>
                    <th className="th">Vaste dag</th>
                    <th className="th"> </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {[...settings.boundaries].reverse().map((row) => (
                    <tr key={`${row.year}-${row.month}`}>
                      <td className="td whitespace-nowrap font-medium">
                        {MONTHS[row.month - 1]} {row.year}
                      </td>
                      <td className="td">
                        <input
                          type="date"
                          className="input w-40"
                          defaultValue={row.start}
                          onChange={(e) => {
                            if (!e.target.value) return;
                            apply(
                              api.setPeriodOverride({
                                year: row.year, month: row.month, start_date: e.target.value,
                              }),
                              `Grens voor ${MONTHS[row.month - 1]} ${row.year} aangepast.`
                            );
                          }}
                        />
                      </td>
                      <td className="td">
                        <span
                          className={`pill ${
                            row.origin === "handmatig"
                              ? "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-100"
                              : "bg-slate-100 dark:bg-slate-700"
                          }`}
                        >
                          {row.origin}
                        </span>
                        {row.salary_date && row.salary_date !== row.fixed_date && (
                          <span className="ml-1 text-xs text-slate-500 dark:text-slate-400">
                            salaris {shortDate(row.salary_date)}
                          </span>
                        )}
                      </td>
                      <td className="td text-sm text-slate-500 dark:text-slate-400">
                        {shortDate(row.fixed_date)}
                      </td>
                      <td className="td text-right">
                        {row.origin === "handmatig" && (
                          <button
                            className="btn-ghost"
                            onClick={() =>
                              apply(
                                api.deletePeriodOverride(row.year, row.month),
                                "Correctie verwijderd."
                              )
                            }
                          >
                            Herstel
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </>
  );
}
