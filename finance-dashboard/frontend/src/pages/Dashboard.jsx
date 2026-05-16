import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend,
} from "recharts";
import {
  getDashboardStats, getDashboardTrend, getDashboardByCategory, getBalanceHistory,
} from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(n);

function StatCard({ label, value, sub, color = "text-white" }) {
  return (
    <div className="card">
      <p className="text-xs text-slate-500 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}

const MONTHS_NL = ["", "Januari", "Februari", "Maart", "April", "Mei", "Juni",
  "Juli", "Augustus", "September", "Oktober", "November", "December"];

export default function Dashboard() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);

  const [stats, setStats] = useState(null);
  const [trend, setTrend] = useState([]);
  const [byCategory, setByCategory] = useState([]);
  const [balance, setBalance] = useState([]);

  useEffect(() => {
    getDashboardStats(year, month).then(setStats);
    getDashboardByCategory(year, month).then(setByCategory);
  }, [year, month]);

  useEffect(() => {
    getDashboardTrend(6).then(setTrend);
    getBalanceHistory(90).then(setBalance);
  }, []);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Dashboard</h2>
          <p className="text-slate-500 text-sm">Overzicht van je financiën</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="select w-36"
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
          >
            {MONTHS_NL.slice(1).map((m, i) => (
              <option key={i + 1} value={i + 1}>{m}</option>
            ))}
          </select>
          <select
            className="select w-24"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {[2022, 2023, 2024, 2025, 2026].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Inkomsten"
          value={stats ? fmt(stats.total_income) : "—"}
          sub={`${MONTHS_NL[month]} ${year}`}
          color="text-emerald-400"
        />
        <StatCard
          label="Uitgaven"
          value={stats ? fmt(stats.total_expenses) : "—"}
          sub="Totaal deze maand"
          color="text-red-400"
        />
        <StatCard
          label="Netto"
          value={stats ? fmt(stats.net) : "—"}
          sub="Verschil"
          color={stats?.net >= 0 ? "text-emerald-400" : "text-red-400"}
        />
        <StatCard
          label="Transacties"
          value={stats ? stats.transaction_count : "—"}
          sub="Deze maand"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Trend bar chart */}
        <div className="card lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Inkomsten vs Uitgaven (6 maanden)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={trend} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="month" tick={{ fill: "#64748b", fontSize: 11 }} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(v) => `€${(v / 1000).toFixed(0)}k`} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
                labelStyle={{ color: "#94a3b8" }}
                formatter={(v, n) => [fmt(v), n === "income" ? "Inkomsten" : "Uitgaven"]}
              />
              <Bar dataKey="income" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="expenses" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2 justify-center">
            <span className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500 inline-block" />Inkomsten
            </span>
            <span className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="w-2.5 h-2.5 rounded-sm bg-red-500 inline-block" />Uitgaven
            </span>
          </div>
        </div>

        {/* Pie chart */}
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Uitgaven per categorie</h3>
          {byCategory.length === 0 ? (
            <p className="text-slate-600 text-sm text-center pt-10">Geen data</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie
                    data={byCategory}
                    dataKey="amount"
                    nameKey="category"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    strokeWidth={2}
                    stroke="#0f172a"
                  >
                    {byCategory.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
                    formatter={(v) => fmt(v)}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5 mt-2 max-h-32 overflow-y-auto">
                {byCategory.slice(0, 6).map((c) => (
                  <div key={c.category} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full inline-block" style={{ background: c.color }} />
                      <span className="text-slate-400">{c.icon} {c.category}</span>
                    </span>
                    <span className="text-slate-300 font-medium">{fmt(c.amount)}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Balance history */}
      <div className="card">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Saldoverloop (90 dagen)</h3>
        {balance.length === 0 ? (
          <p className="text-slate-600 text-sm text-center py-8">Importeer bankafschriften om het saldoverloop te zien</p>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={balance}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 10 }} interval={Math.floor(balance.length / 6)} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(v) => `€${(v / 1000).toFixed(1)}k`} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
                formatter={(v) => [fmt(v), "Saldo"]}
              />
              <Line type="monotone" dataKey="balance" stroke="#6366f1" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
