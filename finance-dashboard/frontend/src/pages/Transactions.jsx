import { useState, useEffect, useCallback, useMemo } from "react";
import {
  getTransactions, getCategories, setTransactionCategory, deleteTransaction,
  getTransactionIds, bulkSetCategory,
} from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(n);

export default function Transactions() {
  const [transactions, setTransactions] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [filterCat, setFilterCat] = useState("");
  const [loading, setLoading] = useState(false);

  // Bulk-select state.
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkCatId, setBulkCatId] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);

  const filterParams = useMemo(() => {
    const p = {};
    if (search) p.search = search;
    if (filterCat) p.category_id = filterCat;
    return p;
  }, [search, filterCat]);

  const load = useCallback(async () => {
    setLoading(true);
    const [txs, cats] = await Promise.all([
      getTransactions({ ...filterParams, limit: 300 }),
      getCategories(),
    ]);
    setTransactions(txs);
    setCategories(cats);
    setLoading(false);
  }, [filterParams]);

  // Debounce so typing in the search box doesn't fire on every keystroke.
  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [load]);

  // When the filter changes, the previous selection is no longer meaningful.
  useEffect(() => {
    setSelectedIds(new Set());
  }, [search, filterCat]);

  async function handleCategoryChange(txId, catId) {
    await setTransactionCategory(txId, catId || null);
    setTransactions((prev) =>
      prev.map((tx) =>
        tx.id === txId
          ? { ...tx, category_id: catId || null, category: categories.find((c) => c.id === Number(catId)) || null }
          : tx
      )
    );
  }

  async function handleDelete(txId) {
    if (!confirm("Transactie verwijderen?")) return;
    await deleteTransaction(txId);
    setTransactions((prev) => prev.filter((tx) => tx.id !== txId));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.delete(txId);
      return next;
    });
  }

  function toggleOne(id) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleVisible() {
    setSelectedIds((prev) => {
      const visibleIds = transactions.map((t) => t.id);
      const allVisibleSelected = visibleIds.every((id) => prev.has(id));
      if (allVisibleSelected) {
        // Deselect only the visible ones; keep any off-screen-but-selected.
        const next = new Set(prev);
        visibleIds.forEach((id) => next.delete(id));
        return next;
      }
      return new Set([...prev, ...visibleIds]);
    });
  }

  async function selectAllMatchingFilter() {
    // Ask the backend for the full ID list under the active filter — the
    // visible page is capped at 300, but the filter can match thousands.
    const { ids } = await getTransactionIds(filterParams);
    setSelectedIds(new Set(ids));
  }

  async function applyBulkCategory() {
    if (selectedIds.size === 0) return;
    setBulkBusy(true);
    const catId = bulkCatId === "" ? null : Number(bulkCatId);
    await bulkSetCategory([...selectedIds], catId);
    setBulkBusy(false);
    setSelectedIds(new Set());
    setBulkCatId("");
    load();
  }

  const visibleCount = transactions.length;
  const visibleSelectedCount = transactions.reduce(
    (n, t) => n + (selectedIds.has(t.id) ? 1 : 0), 0,
  );
  const allVisibleSelected = visibleCount > 0 && visibleSelectedCount === visibleCount;
  const filterIsActive = Boolean(search || filterCat);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Transacties</h2>
          <p className="text-slate-500 text-sm">{transactions.length} transacties gevonden</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <input
          className="input max-w-xs"
          placeholder="Zoek op omschrijving of naam..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="select w-48"
          value={filterCat}
          onChange={(e) => setFilterCat(e.target.value)}
        >
          <option value="">Alle categorieën</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
          ))}
        </select>
      </div>

      {/* Bulk action bar — appears only when a selection exists. */}
      {selectedIds.size > 0 && (
        <div className="card flex flex-wrap items-center gap-3 border-indigo-700/40 bg-indigo-950/30">
          <span className="text-sm text-indigo-200">
            <strong>{selectedIds.size}</strong> geselecteerd
          </span>
          <select
            className="select w-56"
            value={bulkCatId}
            onChange={(e) => setBulkCatId(e.target.value)}
          >
            <option value="">— geen categorie —</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
            ))}
          </select>
          <button
            className="btn-primary"
            onClick={applyBulkCategory}
            disabled={bulkBusy}
          >
            {bulkBusy ? "Bezig..." : "Toepassen op selectie"}
          </button>
          {filterIsActive && (
            <button
              className="btn-ghost"
              onClick={selectAllMatchingFilter}
              title="Selecteer ook transacties buiten de zichtbare 300 rijen die aan het filter voldoen"
            >
              Selecteer alles wat aan filter voldoet
            </button>
          )}
          <button
            className="btn-ghost"
            onClick={() => setSelectedIds(new Set())}
          >
            Selectie wissen
          </button>
        </div>
      )}

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-800/50 border-b border-slate-800">
              <tr>
                <th className="px-3 py-3 w-10">
                  <input
                    type="checkbox"
                    aria-label="Alles op deze pagina selecteren"
                    checked={allVisibleSelected}
                    onChange={toggleVisible}
                  />
                </th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Datum</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Omschrijving</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Tegenpartij</th>
                <th className="text-left px-4 py-3 text-slate-400 font-medium">Categorie</th>
                <th className="text-right px-4 py-3 text-slate-400 font-medium">Bedrag</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-600">Laden...</td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-600">
                    Geen transacties gevonden. Importeer een bankafschrift.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr
                    key={tx.id}
                    className={`hover:bg-slate-800/30 transition-colors ${
                      selectedIds.has(tx.id) ? "bg-indigo-950/30" : ""
                    }`}
                  >
                    <td className="px-3 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(tx.id)}
                        onChange={() => toggleOne(tx.id)}
                      />
                    </td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                      {new Date(tx.date).toLocaleDateString("nl-NL")}
                    </td>
                    <td className="px-4 py-3 text-slate-300 max-w-xs truncate">
                      <span className="inline-flex items-center gap-2">
                        {tx.is_transfer && (
                          <span
                            title="Overboeking tussen eigen rekeningen — telt niet mee in inkomsten of uitgaven"
                            className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-sky-900/40 text-sky-300 border border-sky-800/60"
                          >
                            Overboeking
                          </span>
                        )}
                        <span>{tx.description || tx.counter_name || "—"}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500 max-w-[160px] truncate">
                      {tx.counter_name}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        className="bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                        value={tx.category_id || ""}
                        onChange={(e) => handleCategoryChange(tx.id, e.target.value)}
                      >
                        <option value="">— geen —</option>
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
                        ))}
                      </select>
                    </td>
                    <td className={`px-4 py-3 text-right font-mono font-medium whitespace-nowrap ${
                      tx.amount >= 0 ? "text-emerald-400" : "text-red-400"
                    }`}>
                      {fmt(tx.amount)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(tx.id)}
                        className="text-slate-700 hover:text-red-400 transition-colors text-xs"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
