import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Alert, Confirm, Empty, PageHeader, Spinner } from "../components/Bits.jsx";

const FIELDS = {
  any: "Alles", description: "Omschrijving", counter_name: "Tegenpartij",
  counter_iban: "Tegenrekening", creditor_id: "Incassant-ID", bank_code: "Bankcode",
};

const OPERATORS = {
  contains: "bevat",
  equals: "is exact",
  startswith: "begint met",
};

/** Edit every part of a rule, with a live count of what it would touch. */
function RuleEditor({ rule, categories, onClose, onSaved, onError }) {
  const [form, setForm] = useState({
    category_id: rule.category_id,
    field: rule.field,
    operator: rule.operator,
    value: rule.value,
    priority: rule.priority,
    active: rule.active,
    amount_min: rule.amount_min ?? "",
    amount_max: rule.amount_max ?? "",
  });
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!form.value) { setPreview(null); return; }
    const timer = setTimeout(() => {
      api.previewRule({
        field: form.field,
        operator: form.operator,
        value: form.value,
        category_id: form.category_id,
        amount_min: form.amount_min === "" ? undefined : form.amount_min,
        amount_max: form.amount_max === "" ? undefined : form.amount_max,
      }).then(setPreview).catch(() => setPreview(null));
    }, 300);
    return () => clearTimeout(timer);
  }, [form.field, form.operator, form.value, form.category_id, form.amount_min, form.amount_max]);

  async function save() {
    setBusy(true);
    try {
      await api.updateRule(rule.id, {
        category_id: Number(form.category_id),
        field: form.field,
        operator: form.operator,
        value: form.value,
        priority: Number(form.priority),
        active: form.active,
        amount_min: form.amount_min === "" ? null : Number(form.amount_min),
        amount_max: form.amount_max === "" ? null : Number(form.amount_max),
        account_id: rule.account_id ?? null,
      });
      onSaved("Regel aangepast. Klik op ‘Regels opnieuw toepassen’ om bestaande transacties bij te werken.");
    } catch (e) {
      onError(e.message);
      setBusy(false);
    }
  }

  const trailingSpace = form.value !== form.value.trim();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="card max-h-[90vh] w-full max-w-2xl overflow-y-auto">
        <h3 className="mb-3 text-lg font-semibold">Regel bewerken</h3>

        <div className="mb-3 grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label">Categorie</label>
            <select
              className="input"
              value={form.category_id}
              onChange={(e) => setForm({ ...form, category_id: Number(e.target.value) })}
            >
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Prioriteit</label>
            <input
              type="number"
              min="1"
              max="10000"
              className="input"
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: e.target.value })}
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Lager wint. Standaardregels zitten op 10–270, de tweede set op 500+.
            </p>
          </div>
          <div>
            <label className="label">Kijkt naar</label>
            <select
              className="input"
              value={form.field}
              onChange={(e) => setForm({ ...form, field: e.target.value })}
            >
              {Object.entries(FIELDS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Vergelijking</label>
            <select
              className="input"
              value={form.operator}
              onChange={(e) => setForm({ ...form, operator: e.target.value })}
            >
              {Object.entries(OPERATORS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label">
              Patronen — één per regel
              {form.value.split("\n").filter((v) => v.trim()).length > 1 &&
                ` (${form.value.split("\n").filter((v) => v.trim()).length})`}
            </label>
            <textarea
              className="input h-24 font-mono"
              value={form.value}
              onChange={(e) => setForm({ ...form, value: e.target.value })}
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Elke regel is een alternatief. Ze delen dezelfde categorie en prioriteit, dus varianten
              van dezelfde winkel horen hier bij elkaar in plaats van in losse regels.
            </p>
            {trailingSpace && (
              <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                Deze waarde heeft een spatie aan het begin of eind — dat is bewust bruikbaar
                (<code>ns </code> vangt wél de NS, niet “jetbrains”), maar let op dat je hem niet per
                ongeluk weghaalt.
              </p>
            )}
          </div>
          <div>
            <label className="label">Bedrag vanaf (optioneel)</label>
            <input
              type="number"
              step="0.01"
              className="input"
              value={form.amount_min}
              onChange={(e) => setForm({ ...form, amount_min: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Bedrag tot (optioneel)</label>
            <input
              type="number"
              step="0.01"
              className="input"
              value={form.amount_max}
              onChange={(e) => setForm({ ...form, amount_max: e.target.value })}
            />
          </div>
        </div>

        <label className="mb-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.active}
            onChange={(e) => setForm({ ...form, active: e.target.checked })}
          />
          Regel is actief
        </label>

        <div className="mb-4 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-700">
          {preview === null ? (
            <p className="text-slate-500 dark:text-slate-400">Bezig met tellen…</p>
          ) : (
            <>
              <p>
                Raakt <strong>{preview.matches}</strong> transacties.{" "}
                {preview.already_in_category > 0 && <>{preview.already_in_category} staan al in deze categorie. </>}
                {preview.locked > 0 && <>{preview.locked} zijn handmatig ingesteld en blijven ongewijzigd. </>}
                <strong>{preview.would_change}</strong> zouden verplaatst worden.
              </p>
              {preview.samples.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-xs text-slate-500 dark:text-slate-400">
                  {preview.samples.map((s, i) => (
                    <li key={i} className="truncate">
                      {s.booked_on} · {s.counter_name || s.description}
                      {s.category && <> · nu: {s.category}</>}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose} disabled={busy}>Annuleren</button>
          <button className="btn-primary" onClick={save} disabled={busy || !form.value}>Opslaan</button>
        </div>
      </div>
    </div>
  );
}

/** Create or edit a category. */
function CategoryDialog({ category, onClose, onSaved, onError }) {
  const isNew = Boolean(category.isNew);
  const [form, setForm] = useState({
    name: category.name || "",
    color: category.color || "#64748b",
    is_income: Boolean(category.is_income),
    variable_income: Boolean(category.variable_income),
    excluded_from_budget: Boolean(category.excluded_from_budget),
  });
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const payload = { ...form, parent_id: null, sort_order: category.sort_order ?? 100 };
      if (isNew) {
        await api.createCategory(payload);
        onSaved(`Categorie “${form.name}” aangemaakt.`);
      } else {
        await api.updateCategory(category.id, payload);
        onSaved(`Categorie “${form.name}” bijgewerkt.`);
      }
    } catch (e) {
      onError(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="card w-full max-w-md">
        <h3 className="mb-3 text-lg font-semibold">
          {isNew ? "Nieuwe categorie" : "Categorie bewerken"}
        </h3>

        <div className="mb-3 grid gap-3 sm:grid-cols-[1fr_auto]">
          <div>
            <label className="label">Naam</label>
            <input
              className="input"
              value={form.name}
              maxLength={80}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Kleur</label>
            <input
              type="color"
              className="input h-9 w-16 p-1"
              value={form.color}
              onChange={(e) => setForm({ ...form, color: e.target.value })}
            />
          </div>
        </div>

        <label className="mb-2 flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={form.is_income}
            onChange={(e) => setForm({ ...form, is_income: e.target.checked })}
          />
          <span>
            Dit is een inkomstencategorie
            <span className="block text-xs text-slate-500 dark:text-slate-400">
              Inkomstencategorieën verschijnen niet in het budgetoverzicht.
            </span>
          </span>
        </label>

        {form.is_income && (
          <label className="mb-2 flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={form.variable_income}
              onChange={(e) => setForm({ ...form, variable_income: e.target.checked })}
            />
            <span>
              Variabel inkomen
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                Voor reiskosten, thuiswerkvergoeding of overwerk — inkomsten waar je niet elke maand
                op kunt rekenen. Het overzicht telt ze apart van je vaste inkomen.
              </span>
            </span>
          </label>
        )}

        <label className="mb-4 flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={form.excluded_from_budget}
            onChange={(e) => setForm({ ...form, excluded_from_budget: e.target.checked })}
          />
          <span>
            Buiten het budget houden
            <span className="block text-xs text-slate-500 dark:text-slate-400">
              Voor uitgaven die je wel wilt zien maar niet wilt begroten — bijvoorbeeld iets uit een
              afgesloten periode.
            </span>
          </span>
        </label>

        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose} disabled={busy}>Annuleren</button>
          <button className="btn-primary" onClick={save} disabled={busy || form.name.trim().length < 1}>
            Opslaan
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Categories and rules live in the database, so changing how something is
 * categorised is a form submission here — not a code change and a redeploy.
 */
export default function Rules() {
  const [categories, setCategories] = useState(null);
  const [rules, setRules] = useState([]);
  const [filterCategory, setFilterCategory] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [confirmCategory, setConfirmCategory] = useState(null);
  const [editCategory, setEditCategory] = useState(null);
  const [confirmOverride, setConfirmOverride] = useState(null);
  const [conflicts, setConflicts] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [editRule, setEditRule] = useState(null);
  const [draft, setDraft] = useState({ value: "", field: "counter_name", category_id: "" });

  const load = () => {
    api.categories().then(setCategories).catch((e) => setError(e.message));
    api.ruleConflicts().then(setConflicts).catch(() => {});
    api.rules({ category_id: filterCategory, search })
      .then(setRules)
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    const timer = setTimeout(load, 200);
    return () => clearTimeout(timer);
  }, [filterCategory, search]);

  async function addRule() {
    if (!draft.value.trim() || !draft.category_id) return;
    setBusy(true);
    try {
      await api.createRule({
        value: draft.value.trim(),
        field: draft.field,
        category_id: Number(draft.category_id),
        priority: 1,
      });
      setDraft({ ...draft, value: "" });
      setNotice("Regel toegevoegd. Klik op ‘Regels opnieuw toepassen’ om bestaande transacties bij te werken.");
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function reapply() {
    setBusy(true);
    try {
      const result = await api.reapplyRules(false, false);
      setNotice(
        `${result.updated} transacties opnieuw gecategoriseerd.` +
        (result.manual > 0
          ? ` ${result.manual} handmatig ingestelde transacties zijn met rust gelaten.`
          : " Handmatige keuzes zijn ongemoeid gelaten.")
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  /** Ask the server what an override *would* do, then ask the user. */
  async function askOverride() {
    setBusy(true);
    try {
      setConfirmOverride(await api.reapplyRules(true, true));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (categories === null) return <Spinner />;

  return (
    <>
      <PageHeader
        title="Categorieën & regels"
        subtitle="Eerste passende regel wint, op volgorde van prioriteit."
      >
        <button className="btn-primary" onClick={reapply} disabled={busy}>Regels opnieuw toepassen</button>
        <button
          className="btn-ghost"
          onClick={async () => {
            try {
              const data = await api.exportRules();
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const link = document.createElement("a");
              link.href = url;
              link.download = `financials-regels-${new Date().toISOString().slice(0, 10)}.json`;
              link.click();
              URL.revokeObjectURL(url);
            } catch (e) {
              setError(e.message);
            }
          }}
          title="Alle regels met herkomst en aantal treffers als JSON"
        >
          Regels exporteren
        </button>
        <label className="btn-ghost cursor-pointer" title="Een eerder geëxporteerd bestand inlezen">
          Importeren
          <input
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              try {
                const parsed = JSON.parse(await file.text());
                const payload = { rules: (parsed.rules || []).map((r) => ({
                  category: r.category, value: r.value, field: r.field || "any",
                  operator: r.operator || "contains", priority: r.priority ?? 50,
                  active: r.active ?? true, note: r.note ?? null,
                })) };
                setImportResult({ payload, preview: await api.importRules(payload, true) });
              } catch (err) {
                setError(`Kon het bestand niet lezen: ${err.message}`);
              }
            }}
          />
        </label>
        <button
          className="btn-ghost"
          onClick={askOverride}
          disabled={busy}
          title="Past regels toe én overschrijft categorieën die je zelf hebt ingesteld"
        >
          Ook handmatige keuzes overschrijven…
        </button>
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      {conflicts && (conflicts.duplicates.length > 0 || conflicts.shadowed.length > 0) && (
        <Alert kind="warning">
          <details>
            <summary className="cursor-pointer font-medium">
              {conflicts.duplicates.length + conflicts.shadowed.length} regels botsen met elkaar
            </summary>
            <ul className="mt-2 space-y-1 text-xs">
              {conflicts.duplicates.map((d, i) => (
                <li key={`d${i}`}>
                  <code>{d.value}</code> staat twee keer: <strong>{d.winner}</strong> wint,{" "}
                  {d.loser} komt nooit aan bod.
                </li>
              ))}
              {conflicts.shadowed.map((s, i) => (
                <li key={`s${i}`}>
                  <code>{s.value}</code> ({s.category}) vuurt nooit — <code>{s.shadowed_by}</code>{" "}
                  ({s.shadowed_by_category}) vangt hem eerder af.
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs">
              Op te lossen door de prioriteit van de specifieke regel te verlagen (lager getal wint),
              of door de te brede regel aan te scherpen.
            </p>
          </details>
        </Alert>
      )}

      <section className="card mb-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold">Categorieën</h3>
          <button className="btn-ghost" onClick={() => setEditCategory({ isNew: true, name: "", color: "#64748b", is_income: false, excluded_from_budget: false })}>
            Nieuwe categorie
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map((category) => (
            <span
              key={category.id}
              className="pill border border-slate-200 dark:border-slate-600"
              style={{ backgroundColor: `${category.color}22` }}
            >
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: category.color }} />
              <button className="hover:underline" title="Bewerken" onClick={() => setEditCategory(category)}>
                {category.name}
              </button>
              <span className="text-slate-500 dark:text-slate-400">{category.transaction_count}</span>
              <button
                className="ml-1 opacity-50 hover:opacity-100"
                title="Categorie verwijderen"
                onClick={() => setConfirmCategory(category)}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      </section>

      <section className="card mb-4">
        <h3 className="mb-3 font-semibold">Nieuwe regel</h3>
        <div className="grid gap-2 sm:grid-cols-4">
          <select className="input" value={draft.field} onChange={(e) => setDraft({ ...draft, field: e.target.value })}>
            {Object.entries(FIELDS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
          <input
            className="input"
            placeholder="bevat…"
            value={draft.value}
            onChange={(e) => setDraft({ ...draft, value: e.target.value })}
          />
          <select className="input" value={draft.category_id} onChange={(e) => setDraft({ ...draft, category_id: e.target.value })}>
            <option value="">Categorie…</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button className="btn-primary" onClick={addRule} disabled={busy}>Toevoegen</button>
        </div>
      </section>

      <section className="card mb-4 grid gap-2 sm:grid-cols-2">
        <input className="input" placeholder="Zoek in regels" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="input" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
          <option value="">Alle categorieën</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </section>

      {rules.length === 0 ? (
        <Empty>Geen regels gevonden.</Empty>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="min-w-full">
            <thead className="border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th className="th">Prio</th>
                <th className="th">Kijkt naar</th>
                <th className="th">Bevat</th>
                <th className="th">Categorie</th>
                <th className="th">Herkomst</th>
                <th className="th"> </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {rules.map((rule) => (
                <tr key={rule.id} className={rule.active ? "" : "opacity-50"}>
                  <td className="td">
                    {/* Priority decides which rule wins, so it is the thing you
                        reach for most — inline rather than behind a dialog. */}
                    <input
                      type="number"
                      min="1"
                      max="10000"
                      className="input w-20 py-1 text-right"
                      defaultValue={rule.priority}
                      title="Lager getal wint"
                      onBlur={async (e) => {
                        const next = Number(e.target.value);
                        if (!next || next === rule.priority) return;
                        try {
                          await api.updateRule(rule.id, { ...rule, priority: next });
                          setNotice("Prioriteit aangepast. Klik op ‘Regels opnieuw toepassen’ om het te laten gelden.");
                          load();
                        } catch (err) {
                          setError(err.message);
                        }
                      }}
                    />
                  </td>
                  <td className="td">{FIELDS[rule.field] || rule.field}</td>
                  <td className="td">
                    <button
                      className="text-left font-mono text-xs hover:underline"
                      title="Regel bewerken"
                      onClick={() => setEditRule(rule)}
                    >
                      {rule.value.split("\n")[0]}
                      {rule.value.split("\n").filter((v) => v.trim()).length > 1 && (
                        <span className="ml-1 text-slate-500">
                          +{rule.value.split("\n").filter((v) => v.trim()).length - 1}
                        </span>
                      )}
                    </button>
                  </td>
                  <td className="td">{rule.category_name}</td>
                  <td className="td text-xs text-slate-500 dark:text-slate-400">
                    {rule.origin === "seed" ? `standaard (batch ${rule.seed_batch})`
                      : rule.origin === "transaction" ? "vanaf transactie"
                      : rule.origin === "import" ? "geïmporteerd" : "handmatig"}
                  </td>
                  <td className="td text-right">
                    <button className="btn-ghost" onClick={() => setEditRule(rule)}>Bewerken</button>
                    <button
                      className="btn-ghost ml-1"
                      onClick={async () => {
                        await api.updateRule(rule.id, { ...rule, active: !rule.active });
                        load();
                      }}
                    >
                      {rule.active ? "Uitzetten" : "Aanzetten"}
                    </button>
                    <button
                      className="btn-danger ml-1"
                      onClick={async () => { await api.deleteRule(rule.id); load(); }}
                    >
                      Verwijderen
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Confirm
        open={Boolean(confirmOverride)}
        title="Handmatige keuzes overschrijven"
        confirmLabel={`Ja, ${confirmOverride?.manual || 0} handmatige keuzes overschrijven`}
        onCancel={() => setConfirmOverride(null)}
        onConfirm={async () => {
          setConfirmOverride(null);
          setBusy(true);
          try {
            const result = await api.reapplyRules(true, false);
            setNotice(`${result.updated} transacties bijgewerkt, waarvan ${result.manual} handmatig ingesteld waren.`);
          } catch (e) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {confirmOverride?.manual === 0 ? (
          <p>
            Geen enkele handmatig ingestelde categorie zou veranderen — de regels komen overeen met wat
            je zelf gekozen hebt. Je kunt dit gerust annuleren.
          </p>
        ) : (
          <>
            <p className="mb-2">
              Dit overschrijft <strong>{confirmOverride?.manual}</strong> categorieën die je zelf hebt
              ingesteld, plus {confirmOverride?.auto} die automatisch waren toegekend.
            </p>
            <p>
              Handmatige keuzes gaan hiermee verloren en zijn niet terug te halen. Normaal gesproken wil
              je hier <em>Regels opnieuw toepassen</em> voor gebruiken; die laat jouw keuzes staan.
            </p>
          </>
        )}
      </Confirm>

      <Confirm
        open={Boolean(importResult)}
        title="Regels importeren"
        confirmLabel={`${importResult?.preview.added || 0} regels toevoegen`}
        danger={false}
        onCancel={() => setImportResult(null)}
        onConfirm={async () => {
          const { payload } = importResult;
          setImportResult(null);
          try {
            const result = await api.importRules(payload, false);
            setNotice(
              `${result.added} regels toegevoegd, ${result.skipped} overgeslagen omdat ze al bestonden.` +
              (result.created_categories.length
                ? ` Nieuwe categorieën: ${result.created_categories.join(", ")}.`
                : "")
            );
            load();
          } catch (e) {
            setError(e.message);
          }
        }}
      >
        <p className="mb-2">
          <strong>{importResult?.preview.added}</strong> nieuwe regels,{" "}
          <strong>{importResult?.preview.skipped}</strong> bestaan al en worden overgeslagen.
        </p>
        {importResult?.preview.created_categories?.length > 0 && (
          <p className="mb-2">
            Nieuwe categorieën die aangemaakt worden: {importResult.preview.created_categories.join(", ")}
          </p>
        )}
        <p className="text-xs">
          Bestaande regels en de categorie van je transacties blijven ongemoeid. Klik daarna op
          <em> Regels opnieuw toepassen</em> om de nieuwe regels te laten werken.
        </p>
      </Confirm>

      {editRule && (
        <RuleEditor
          rule={editRule}
          categories={categories}
          onClose={() => setEditRule(null)}
          onSaved={(message) => { setEditRule(null); setNotice(message); load(); }}
          onError={setError}
        />
      )}

      {editCategory && (
        <CategoryDialog
          category={editCategory}
          onClose={() => setEditCategory(null)}
          onSaved={(message) => { setEditCategory(null); setNotice(message); load(); }}
          onError={setError}
        />
      )}

      <Confirm
        open={Boolean(confirmCategory)}
        title="Categorie verwijderen"
        onCancel={() => setConfirmCategory(null)}
        onConfirm={async () => {
          const category = confirmCategory;
          setConfirmCategory(null);
          try {
            const result = await api.deleteCategory(category.id);
            setNotice(`Categorie verwijderd; ${result.uncategorised} transacties staan nu zonder categorie.`);
            load();
          } catch (e) {
            setError(e.message);
          }
        }}
      >
        <strong>{confirmCategory?.name}</strong> wordt verwijderd.{" "}
        {confirmCategory?.transaction_count > 0 && (
          <>De {confirmCategory.transaction_count} transacties blijven bestaan, maar staan daarna zonder categorie.</>
        )}
      </Confirm>
    </>
  );
}
