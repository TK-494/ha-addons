import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { amountClass, bankCodeLabel, money, shortDate } from "../format.js";

const EMPTY_FILTERS = {
  search: "", account_id: "", category_id: "", date_from: "", date_to: "",
  direction: "", uncategorised: false, internal: "", page: 1, page_size: 50,
};

export default function Transactions() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [data, setData] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [ruleFor, setRuleFor] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.accounts(), api.categories()])
      .then(([a, c]) => { setAccounts(a); setCategories(c); })
      .catch((e) => setError(e.message));
  }, []);

  const query = useMemo(() => {
    const params = { ...filters };
    if (!params.uncategorised) delete params.uncategorised;
    if (params.internal === "") delete params.internal;
    return params;
  }, [filters]);

  const load = useCallback(() => {
    setLoading(true);
    api.transactions(query)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [query]);

  // Debounced so typing in the search box doesn't fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(load, 250);
    return () => clearTimeout(timer);
  }, [load]);

  const update = (patch) => setFilters((f) => ({ ...f, ...patch, page: patch.page ?? 1 }));

  async function assign(id, categoryId) {
    try {
      await api.setCategory(id, categoryId ? Number(categoryId) : null);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function assignSelected(categoryId) {
    if (!selected.size) return;
    try {
      const result = await api.bulkCategory([...selected], categoryId ? Number(categoryId) : null);
      setNotice(`${result.updated} transacties bijgewerkt.`);
      setSelected(new Set());
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <>
      <PageHeader title="Transacties" subtitle={data ? `${data.total.toLocaleString("nl-NL")} regels` : ""}>
        <a className="btn-ghost" href={api.exportUrl({
          date_from: filters.date_from, date_to: filters.date_to,
          account_id: filters.account_id, category_id: filters.category_id, search: filters.search,
        })}>
          Exporteren
        </a>
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      <section className="card mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2">
          <label className="label">Zoeken</label>
          <input
            className="input"
            placeholder="Omschrijving, tegenpartij of IBAN"
            value={filters.search}
            onChange={(e) => update({ search: e.target.value })}
          />
        </div>
        <div>
          <label className="label">Rekening</label>
          <select className="input" value={filters.account_id} onChange={(e) => update({ account_id: e.target.value })}>
            <option value="">Alle rekeningen</option>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Categorie</label>
          <select className="input" value={filters.category_id} onChange={(e) => update({ category_id: e.target.value })}>
            <option value="">Alle categorieën</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Van</label>
          <input type="date" className="input" value={filters.date_from} onChange={(e) => update({ date_from: e.target.value })} />
        </div>
        <div>
          <label className="label">Tot en met</label>
          <input type="date" className="input" value={filters.date_to} onChange={(e) => update({ date_to: e.target.value })} />
        </div>
        <div>
          <label className="label">Richting</label>
          <select className="input" value={filters.direction} onChange={(e) => update({ direction: e.target.value })}>
            <option value="">Alles</option>
            <option value="in">Bij</option>
            <option value="out">Af</option>
          </select>
        </div>
        <div>
          <label className="label">Interne overboekingen</label>
          <select className="input" value={filters.internal} onChange={(e) => update({ internal: e.target.value })}>
            <option value="">Tonen</option>
            <option value="false">Verbergen</option>
            <option value="true">Alleen deze</option>
          </select>
        </div>
        <label className="flex items-end gap-2 pb-1 text-sm">
          <input
            type="checkbox"
            checked={filters.uncategorised}
            onChange={(e) => update({ uncategorised: e.target.checked })}
          />
          Alleen zonder categorie
        </label>
        <div className="flex items-end">
          <button className="btn-ghost" onClick={() => setFilters(EMPTY_FILTERS)}>Filters wissen</button>
        </div>
      </section>

      {data && (
        <div className="mb-3 flex flex-wrap items-center gap-4 text-sm">
          <span className="text-emerald-600 dark:text-emerald-400">Bij {money(data.sum_in)}</span>
          <span className="text-rose-600 dark:text-rose-400">Af {money(data.sum_out)}</span>
          <span className="font-medium">Saldo {money(data.sum_in + data.sum_out)}</span>
          {selected.size > 0 && (
            <span className="ml-auto flex items-center gap-2">
              {selected.size} geselecteerd
              <select className="input w-auto" defaultValue="" onChange={(e) => assignSelected(e.target.value)}>
                <option value="" disabled>Categorie toewijzen…</option>
                <option value="">Categorie wissen</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button className="btn-ghost" onClick={() => setSelected(new Set())}>Selectie wissen</button>
            </span>
          )}
        </div>
      )}

      {loading && !data ? (
        <Spinner />
      ) : !data || data.items.length === 0 ? (
        <Empty>Geen transacties gevonden met deze filters.</Empty>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="min-w-full">
            <thead className="border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th className="th w-8"> </th>
                <th className="th">Datum</th>
                <th className="th">Omschrijving</th>
                <th className="th">Rekening</th>
                <th className="th text-right">Bedrag</th>
                <th className="th">Categorie</th>
                <th className="th"> </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {data.items.map((tx) => (
                <tr key={tx.id} className={tx.is_internal ? "bg-slate-50 dark:bg-slate-900/40" : ""}>
                  <td className="td">
                    <input
                      type="checkbox"
                      checked={selected.has(tx.id)}
                      onChange={(e) => {
                        const next = new Set(selected);
                        e.target.checked ? next.add(tx.id) : next.delete(tx.id);
                        setSelected(next);
                      }}
                    />
                  </td>
                  <td className="td whitespace-nowrap">{shortDate(tx.booked_on)}</td>
                  <td className="td">
                    <div className="max-w-md truncate">{tx.description || "—"}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {tx.counter_name}
                      {tx.bank_code && ` · ${bankCodeLabel(tx.bank_code)}`}
                      {tx.fx_amount !== null && tx.fx_currency && (
                        <> · {tx.fx_amount} {tx.fx_currency} @ {tx.fx_rate}</>
                      )}
                    </div>
                  </td>
                  <td className="td whitespace-nowrap text-xs">{tx.account_label}</td>
                  <td className={`td whitespace-nowrap text-right font-medium ${amountClass(tx.amount)}`}>
                    {money(tx.amount)}
                  </td>
                  <td className="td">
                    {tx.is_internal ? (
                      <span
                        className="pill bg-slate-200 dark:bg-slate-700"
                        title={
                          tx.transfer_pending
                            ? "Overboeking naar een eigen rekening waarvan de andere kant nog niet geïmporteerd is"
                            : "Overboeking tussen je eigen rekeningen — telt niet mee als inkomsten of uitgaven"
                        }
                      >
                        {tx.transfer_pending ? "intern (andere kant ontbreekt)" : "interne overboeking"}
                      </span>
                    ) : (
                      <select
                        className="input py-1"
                        value={tx.category_id || ""}
                        onChange={(e) => assign(tx.id, e.target.value)}
                      >
                        <option value="">— geen —</option>
                        {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    )}
                  </td>
                  <td className="td">
                    {!tx.is_internal && (
                      <button className="btn-ghost whitespace-nowrap" onClick={() => setRuleFor(tx)}>
                        Regel maken
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && pages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2 text-sm">
          <button className="btn-ghost" disabled={filters.page <= 1} onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}>
            Vorige
          </button>
          <span>Pagina {filters.page} van {pages}</span>
          <button className="btn-ghost" disabled={filters.page >= pages} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>
            Volgende
          </button>
        </div>
      )}

      {ruleFor && (
        <RuleDialog
          transaction={ruleFor}
          categories={categories}
          onClose={() => setRuleFor(null)}
          onDone={(message) => { setRuleFor(null); setNotice(message); load(); }}
          onError={setError}
        />
      )}
    </>
  );
}

/** "Categoriseer dit en alles wat hierop lijkt" — with the impact shown first. */
function RuleDialog({ transaction, categories, onClose, onDone, onError }) {
  const [field, setField] = useState(transaction.counter_name ? "counter_name" : "description");
  const [value, setValue] = useState(transaction.counter_name || transaction.description.slice(0, 24));
  const [categoryId, setCategoryId] = useState(transaction.category_id || "");
  const [impact, setImpact] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (value.trim().length < 2) { setImpact(null); return; }
    const timer = setTimeout(() => {
      api.rulePreview(transaction.id, field, value.trim()).then(setImpact).catch(() => setImpact(null));
    }, 250);
    return () => clearTimeout(timer);
  }, [transaction.id, field, value]);

  async function save() {
    setBusy(true);
    try {
      const result = await api.createRuleFrom(transaction.id, {
        category_id: Number(categoryId),
        field,
        value: value.trim(),
        apply_to_existing: true,
      });
      onDone(`Regel opgeslagen; ${result.updated} transacties bijgewerkt.`);
    } catch (e) {
      onError(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="card w-full max-w-lg">
        <h3 className="mb-3 text-lg font-semibold">Regel maken</h3>

        <div className="mb-3 grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label">Kijk naar</label>
            <select className="input" value={field} onChange={(e) => setField(e.target.value)}>
              <option value="counter_name">Tegenpartij</option>
              <option value="description">Omschrijving</option>
              <option value="counter_iban">Tegenrekening</option>
              <option value="creditor_id">Incassant-ID</option>
              <option value="any">Alles</option>
            </select>
          </div>
          <div>
            <label className="label">Bevat</label>
            <input className="input" value={value} onChange={(e) => setValue(e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Categorie</label>
            <select className="input" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">Kies een categorie…</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        </div>

        <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">
          {impact === null
            ? "Typ minstens twee tekens om te zien hoeveel transacties dit raakt."
            : <>Deze regel raakt <strong>{impact.matches}</strong> transacties.
                {impact.locked > 0 && <> Daarvan zijn er {impact.locked} handmatig ingesteld; die blijven ongewijzigd.</>}</>}
        </p>

        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose} disabled={busy}>Annuleren</button>
          <button className="btn-primary" onClick={save} disabled={busy || !categoryId || value.trim().length < 2}>
            Opslaan en toepassen
          </button>
        </div>
      </div>
    </div>
  );
}
