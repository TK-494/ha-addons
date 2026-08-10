import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { axisMoney, money, shortDate } from "../format.js";

/**
 * Every salary payment, and what each one was made of.
 *
 * Base pay is what you can build commitments on; travel and working-from-home
 * allowances are not. The bank shows one lump sum, so the division is recorded
 * here — and since the base almost never changes, last month's division is
 * offered as a template with the difference landing on the variable part.
 */
export default function Salary() {
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.salary(24).then(setData).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function applyTemplate(payment) {
    setBusy(true);
    try {
      const result = await api.applySalaryTemplate(payment.transaction_id);
      setNotice(
        `${shortDate(result.date)} verdeeld: ${money(result.fixed)} vast, ${money(result.variable)} variabel.`
      );
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function applyToAll() {
    const targets = data.payments.filter((p) => !p.split);
    setBusy(true);
    let done = 0;
    let failed = 0;
    for (const payment of targets) {
      try {
        await api.applySalaryTemplate(payment.transaction_id);
        done += 1;
      } catch {
        failed += 1;
      }
    }
    setNotice(
      `${done} betalingen verdeeld volgens het sjabloon` +
      (failed ? `; ${failed} lukten niet en moeten handmatig.` : ".")
    );
    setBusy(false);
    load();
  }

  if (!data) return <Spinner />;

  if (!data.configured) {
    return (
      <>
        <PageHeader title="Salaris" />
        <Alert kind="warning">
          <p className="mb-2">
            Er is nog geen salarisbetaler ingesteld, dus deze pagina weet niet welke betalingen je
            loon zijn.
          </p>
          <Link className="underline" to="/instellingen">Instellen bij Instellingen → Maandgrens</Link>
        </Alert>
        {data.suggestions?.length > 0 && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Waarschijnlijke kandidaat uit je gegevens: <strong>{data.suggestions[0].counterparty}</strong>{" "}
            ({data.suggestions[0].payments} betalingen).
          </p>
        )}
      </>
    );
  }

  const { summary, template } = data;
  const chart = [...data.payments].reverse().slice(-18).map((p) => ({
    label: shortDate(p.date).slice(3),
    vast: p.fixed,
    variabel: p.variable,
  }));

  return (
    <>
      <PageHeader
        title="Salaris"
        subtitle={`${data.source.counterparty} · ${summary.count} betalingen`}
      >
        {template && summary.unsplit_count > 0 && (
          <button className="btn-primary" onClick={applyToAll} disabled={busy}>
            Sjabloon op alle {summary.unsplit_count} toepassen
          </button>
        )}
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Gemiddeld per maand" value={money(summary.average)} hint="laatste 12 betalingen" />
        <Stat label="Waarvan vast" value={money(summary.average_fixed)} hint="basissalaris" />
        <Stat
          label="Waarvan variabel"
          value={money(summary.average_variable)}
          hint={summary.average_variable === 0 ? "nog niets als variabel gemarkeerd" : "vergoedingen"}
        />
        <Stat
          label="Verdeeld"
          value={`${summary.split_count} / ${summary.count}`}
          hint={summary.unsplit_count > 0 ? `${summary.unsplit_count} nog niet verdeeld` : "alles verdeeld"}
        />
      </section>

      {summary.split_count > 0 && (
        <section className="card mb-6">
          <h3 className="mb-1 font-semibold">Vast en variabel per betaling</h3>
          <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
            Nog niet verdeelde betalingen tellen volledig als vast — dat is wat er bekend is, niet
            een bewering dat er geen vergoeding in zat.
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chart}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis dataKey="label" fontSize={11} />
              <YAxis fontSize={11} tickFormatter={axisMoney} />
              <Tooltip formatter={(v) => money(v)} />
              <Legend />
              <Bar dataKey="vast" stackId="a" fill="#15803d" />
              <Bar dataKey="variabel" stackId="a" fill="#86efac" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>
      )}

      {template && (
        <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
          Sjabloon van {shortDate(template.from_date)}:{" "}
          {template.parts.map((p) => `${p.category_name} ${money(p.amount)}${p.variable ? " (variabel)" : ""}`).join(" · ")}.
          Bij toepassen blijven de vaste delen gelijk en komt het verschil op het variabele deel.
        </p>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="min-w-full">
          <thead className="border-b border-slate-200 dark:border-slate-700">
            <tr>
              <th className="th">Datum</th>
              <th className="th text-right">Bedrag</th>
              <th className="th text-right">Vast</th>
              <th className="th text-right">Variabel</th>
              <th className="th">Verdeling</th>
              <th className="th"> </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {data.payments.map((payment) => (
              <tr key={payment.transaction_id} className={payment.split ? "" : "bg-amber-50/40 dark:bg-amber-950/20"}>
                <td className="td whitespace-nowrap font-medium">{shortDate(payment.date)}</td>
                <td className="td text-right tabular-nums">{money(payment.amount)}</td>
                <td className="td text-right tabular-nums">{money(payment.fixed)}</td>
                <td className="td text-right tabular-nums">
                  {payment.variable > 0 ? money(payment.variable) : "—"}
                </td>
                <td className="td">
                  {payment.split ? (
                    <div className="flex flex-wrap gap-1">
                      {payment.parts.map((part, index) => (
                        <span
                          key={index}
                          className={`pill text-[11px] ${
                            part.variable
                              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-100"
                              : "bg-slate-200 dark:bg-slate-700"
                          }`}
                          title={part.note || ""}
                        >
                          {part.category_name || "zonder categorie"} {money(part.amount)}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-500 dark:text-slate-400">nog niet verdeeld</span>
                  )}
                </td>
                <td className="td text-right">
                  {template && !payment.split && (
                    <button className="btn-ghost" disabled={busy} onClick={() => applyTemplate(payment)}>
                      Sjabloon
                    </button>
                  )}
                  <button className="btn-ghost ml-1" onClick={() => setEditing(payment)}>
                    {payment.split ? "Aanpassen" : "Verdelen"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.income_categories.filter((c) => c.variable_income).length === 0 && (
        <Alert kind="info">
          Nog geen enkele categorie is als <strong>variabel inkomen</strong> gemarkeerd. Maak er een
          aan voor bijvoorbeeld reiskosten of thuiswerkvergoeding —{" "}
          <Link className="underline" to="/regels">Categorieën &amp; regels</Link> → Nieuwe categorie,
          met <em>Dit is een inkomstencategorie</em> én <em>Variabel inkomen</em> aangevinkt.
        </Alert>
      )}

      {editing && (
        <SplitEditor
          payment={editing}
          categories={data.income_categories}
          template={template}
          onClose={() => setEditing(null)}
          onSaved={(message) => { setEditing(null); setNotice(message); load(); }}
          onError={setError}
        />
      )}
    </>
  );
}

function Stat({ label, value, hint }) {
  return (
    <div className="card">
      <p className="label">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="text-xs text-slate-500 dark:text-slate-400">{hint}</p>}
    </div>
  );
}

function SplitEditor({ payment, categories, template, onClose, onSaved, onError }) {
  const [parts, setParts] = useState(() => {
    if (payment.parts.length) {
      return payment.parts.map((p) => ({ category_id: p.category_id || "", amount: p.amount, note: p.note || "" }));
    }
    if (template) {
      const fixed = template.parts.filter((p) => !p.variable);
      const variable = template.parts.find((p) => p.variable);
      const remainder = Math.round((payment.amount - fixed.reduce((s, p) => s + p.amount, 0)) * 100) / 100;
      return [
        ...fixed.map((p) => ({ category_id: p.category_id || "", amount: p.amount, note: "" })),
        { category_id: variable?.category_id || "", amount: remainder, note: "" },
      ];
    }
    return [
      { category_id: "", amount: payment.amount, note: "" },
      { category_id: "", amount: 0, note: "" },
    ];
  });
  const [busy, setBusy] = useState(false);

  const total = parts.reduce((sum, p) => sum + (Number(p.amount) || 0), 0);
  const difference = Math.round((payment.amount - total) * 100) / 100;
  const balanced = Math.abs(difference) < 0.005;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="card max-h-[90vh] w-full max-w-2xl overflow-y-auto">
        <h3 className="mb-1 text-lg font-semibold">Loon verdelen</h3>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
          {shortDate(payment.date)} · {money(payment.amount)}
        </p>

        <div className="mb-3 space-y-2">
          {parts.map((part, index) => (
            <div key={index} className="grid gap-2 sm:grid-cols-[1fr_8rem_1fr_auto]">
              <select
                className="input"
                value={part.category_id || ""}
                onChange={(e) => setParts(parts.map((p, i) => i === index ? { ...p, category_id: e.target.value } : p))}
              >
                <option value="">— kies categorie —</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}{c.variable_income ? " (variabel)" : ""}
                  </option>
                ))}
              </select>
              <input
                type="number"
                step="0.01"
                className="input text-right"
                value={part.amount}
                onChange={(e) => setParts(parts.map((p, i) => i === index ? { ...p, amount: e.target.value } : p))}
              />
              <input
                className="input"
                placeholder="notitie"
                value={part.note}
                onChange={(e) => setParts(parts.map((p, i) => i === index ? { ...p, note: e.target.value } : p))}
              />
              <button
                className="btn-ghost"
                disabled={parts.length <= 2}
                onClick={() => setParts(parts.filter((_, i) => i !== index))}
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <button
            className="btn-ghost"
            onClick={() => setParts([...parts, { category_id: "", amount: difference, note: "" }])}
          >
            Deel toevoegen{!balanced && ` (${money(difference)})`}
          </button>
          <p className={`text-sm ${balanced ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}`}>
            {balanced ? `Sluit op ${money(payment.amount)}` : `Verschil ${money(difference)}`}
          </p>
        </div>

        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose} disabled={busy}>Annuleren</button>
          <button
            className="btn-primary"
            disabled={busy || !balanced}
            onClick={async () => {
              setBusy(true);
              try {
                await api.setSplit(payment.transaction_id, parts.map((p) => ({
                  category_id: p.category_id ? Number(p.category_id) : null,
                  amount: Number(p.amount),
                  note: p.note || null,
                })));
                onSaved("Verdeling opgeslagen.");
              } catch (e) {
                onError(e.message);
                setBusy(false);
              }
            }}
          >
            Opslaan
          </button>
        </div>
      </div>
    </div>
  );
}
