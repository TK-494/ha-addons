import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Transactions from "./pages/Transactions";
import Categories from "./pages/Categories";
import Budget from "./pages/Budget";
import CAOProjection from "./pages/CAOProjection";
import Upload from "./pages/Upload";

const NAV = [
  { to: "/", icon: "📊", label: "Dashboard" },
  { to: "/transactions", icon: "💳", label: "Transacties" },
  { to: "/categories", icon: "🗂️", label: "Categorieën" },
  { to: "/budget", icon: "🎯", label: "Budget" },
  { to: "/cao", icon: "📈", label: "CAO Groei" },
  { to: "/upload", icon: "⬆️", label: "Importeren" },
];

export default function App() {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
        <div className="px-5 py-6 border-b border-slate-800">
          <h1 className="text-base font-bold text-white">💶 Financiën</h1>
          <p className="text-xs text-slate-500 mt-0.5">Persoonlijk dashboard</p>
        </div>

        <nav className="flex-1 p-3 space-y-0.5">
          {NAV.map(({ to, icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-indigo-600 text-white font-medium"
                    : "text-slate-400 hover:text-slate-100 hover:bg-slate-800"
                }`
              }
            >
              <span>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-800">
          <p className="text-xs text-slate-600">Alle data lokaal opgeslagen</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-slate-950">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/categories" element={<Categories />} />
          <Route path="/budget" element={<Budget />} />
          <Route path="/cao" element={<CAOProjection />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
