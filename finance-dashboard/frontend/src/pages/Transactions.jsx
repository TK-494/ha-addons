import { useState, useEffect, useCallback } from "react";
import { getTransactions, getCategories, setTransactionCategory, deleteTransaction } from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(n);

export default function Transactions() {
  const [transactions, setTransactions] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [filterCat, setFilterCat] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const params = {};
    if (search) params.search = search;
    if (filterCat) params.category_id = filterCat;
    const [txs, cats] = await Promise.all([
      getTransactions({ ...params, limit: 300 }),
      getCategories(),
    ]);
    setTransactions(txs);
    setCategories(cats);
    setLoading(false);
  }, [search, filterCat]);

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
  }, [load]);

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
  }

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

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-800/50 border-b border-slate-800">
              <tr>
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
                  <td colSpan={6} className="text-center py-12 text-slate-600">Laden...</td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-slate-600">
                    Geen transacties gevonden. Importeer een bankafschrift.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                      {new Date(tx.date).toLocaleDateString("nl-NL")}
                    </td>
                    <td className="px-4 py-3 text-slate-300 max-w-xs truncate">
                      {tx.description || tx.counter_name || "—"}
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
