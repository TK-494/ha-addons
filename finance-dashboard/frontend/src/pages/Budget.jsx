import { useState, useEffect } from "react";
import { getBudgetProgress, getCategories, upsertBudget, deleteBudget } from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(n);

const MONTHS_NL = ["", "Januari", "Februari", "Maart", "April", "Mei", "Juni",
  "Juli", "Augustus", "September", "Oktober", "November", "December"];

export default function Budget() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [progress, setProgress] = useState([]);
  const [categories, setCategories] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [newBudget, setNewBudget] = useState({ category_id: "", amount: "" });

  const load = async () => {
    const [prog, cats] = await Promise.all([
      getBudgetProgress(year, month),
      getCategories(),
    ]);
    setProgress(prog);
    setCategories(cats);
  };

  useEffect(() => { load(); }, [year, month]);

  async function handleAdd() {
    if (!newBudget.category_id || !newBudget.amount) return;
    await upsertBudget({
      category_id: Number(newBudget.category_id),
      amount: Number(newBudget.amount),
      month,
      year,
    });
    setNewBudget({ category_id: "", amount: "" });
    setShowAdd(false);
    load();
  }

  async function handleDelete(budgetId) {
    await deleteBudget(budgetId);
    load();
  }

  const totalBudget = progress.reduce((s, b) => s + b.budget, 0);
  const totalSpent = progress.reduce((s, b) => s + b.spent, 0);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Budget</h2>
          <p className="text-slate-500 text-sm">Beheer je maandbudget per categorie</p>
        </div>
        <div className="flex items-center gap-2">
          <select className="select w-36" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {MONTHS_NL.slice(1).map((m, i) => (
              <option key={i + 1} value={i + 1}>{m}</option>
            ))}
          </select>
          <select className="select w-24" value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {[2023, 2024, 2025, 2026].map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <button className="btn-primary" onClick={() => setShowAdd(!showAdd)}>+ Budget</button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card text-center">
          <p className="text-xs text-slate-500 uppercase">Totaal budget</p>
          <p className="text-2xl font-bold text-indigo-400 mt-1">{fmt(totalBudget)}</p>
        </div>
        <div className="card text-center">
          <p className="text-xs text-slate-500 uppercase">Uitgegeven</p>
          <p className="text-2xl font-bold text-red-400 mt-1">{fmt(totalSpent)}</p>
        </div>
        <div className="card text-center">
          <p className="text-xs text-slate-500 uppercase">Resterend</p>
          <p className={`text-2xl font-bold mt-1 ${totalBudget - totalSpent >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {fmt(totalBudget - totalSpent)}
          </p>
        </div>
      </div>

      {/* Add budget form */}
      {showAdd && (
        <div className="card flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-xs text-slate-400 mb-1">Categorie</label>
            <select
              className="select"
              value={newBudget.category_id}
              onChange={(e) => setNewBudget((p) => ({ ...p, category_id: e.target.value }))}
            >
              <option value="">Kies categorie...</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>{c.icon} {c.name}</option>
              ))}
            </select>
          </div>
          <div className="w-40">
            <label className="block text-xs text-slate-400 mb-1">Bedrag (€)</label>
            <input
              className="input"
              type="number"
              placeholder="200"
              value={newBudget.amount}
              onChange={(e) => setNewBudget((p) => ({ ...p, amount: e.target.value }))}
            />
          </div>
          <button className="btn-primary" onClick={handleAdd}>Opslaan</button>
          <button className="btn-ghost" onClick={() => setShowAdd(false)}>Annuleren</button>
        </div>
      )}

      {/* Budget progress bars */}
      {progress.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-slate-600 text-sm">Geen budgetten ingesteld voor deze maand.</p>
          <p className="text-slate-700 text-xs mt-1">Klik op "+ Budget" om te beginnen.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {progress.map((b) => (
            <div key={b.budget_id} className="card">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span>{b.icon}</span>
                  <span className="text-sm font-medium text-slate-200">{b.category}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500">
                    {fmt(b.spent)} / {fmt(b.budget)}
                  </span>
                  <span className={`text-xs font-medium ${b.percent >= 100 ? "text-red-400" : b.percent >= 80 ? "text-amber-400" : "text-emerald-400"}`}>
                    {b.percent}%
                  </span>
                  <button
                    onClick={() => handleDelete(b.budget_id)}
                    className="text-slate-700 hover:text-red-400 text-xs transition-colors"
                  >
                    ✕
                  </button>
                </div>
              </div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(b.percent, 100)}%`,
                    backgroundColor: b.percent >= 100 ? "#ef4444" : b.percent >= 80 ? "#f59e0b" : b.color,
                  }}
                />
              </div>
              {b.remaining < 0 && (
                <p className="text-xs text-red-400 mt-1">
                  {fmt(Math.abs(b.remaining))} over budget
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
