import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Alert, Confirm, Empty, PageHeader, Spinner } from "../components/Bits.jsx";

const FIELDS = {
  any: "Alles", description: "Omschrijving", counter_name: "Tegenpartij",
  counter_iban: "Tegenrekening", creditor_id: "Incassant-ID", bank_code: "Bankcode",
};

/** Create or edit a category. */
function CategoryDialog({ category, onClose, onSaved, onError }) {
  const isNew = Boolean(category.isNew);
  const [form, setForm] = useState({
    name: category.name || "",
    color: category.color || "#64748b",
    is_income: Boolean(category.is_income),
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
