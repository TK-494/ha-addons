import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Alert, Confirm, Empty, PageHeader, Spinner } from "../components/Bits.jsx";

const FIELDS = {
  any: "Alles", description: "Omschrijving", counter_name: "Tegenpartij",
  counter_iban: "Tegenrekening", creditor_id: "Incassant-ID", bank_code: "Bankcode",
};

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
  const [draft, setDraft] = useState({ value: "", field: "counter_name", category_id: "" });

  const load = () => {
    api.categories().then(setCategories).catch((e) => setError(e.message));
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
      const result = await api.reapplyRules(false);
      setNotice(`${result.updated} transacties opnieuw gecategoriseerd. Handmatige keuzes zijn ongemoeid gelaten.`);
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
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      <section className="card mb-6">
        <h3 className="mb-3 font-semibold">Categorieën</h3>
        <div className="flex flex-wrap gap-2">
          {categories.map((category) => (
            <span
              key={category.id}
              className="pill border border-slate-200 dark:border-slate-600"
              style={{ backgroundColor: `${category.color}22` }}
            >
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: category.color }} />
              {category.name}
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
                  <td className="td">{rule.priority}</td>
                  <td className="td">{FIELDS[rule.field] || rule.field}</td>
                  <td className="td font-mono text-xs">{rule.value}</td>
                  <td className="td">{rule.category_name}</td>
                  <td className="td text-xs text-slate-500 dark:text-slate-400">
                    {rule.is_seed ? "standaard" : "eigen"}
                  </td>
                  <td className="td text-right">
                    <button
                      className="btn-ghost"
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
