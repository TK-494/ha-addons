import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Import from "./pages/Import.jsx";
import Transactions from "./pages/Transactions.jsx";
import Accounts from "./pages/Accounts.jsx";
import Rules from "./pages/Rules.jsx";
import Settings from "./pages/Settings.jsx";

const NAV = [
  { to: "/transacties", label: "Transacties", icon: "≡" },
  { to: "/rekeningen", label: "Rekeningen", icon: "▤" },
  { to: "/importeren", label: "Importeren", icon: "↑" },
  { to: "/regels", label: "Categorieën & regels", icon: "⚑" },
  { to: "/instellingen", label: "Instellingen", icon: "⚙" },
];

export default function App() {
  return (
    <div className="mx-auto flex min-h-screen max-w-7xl gap-6 p-4">
      <nav className="hidden w-56 shrink-0 md:block">
        <div className="mb-6 px-2">
          <h1 className="text-lg font-semibold">Financials</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">Huishoudboekje</p>
        </div>
        <ul className="space-y-1">
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3 py-2 text-sm ${
                    isActive
                      ? "bg-sky-600 text-white"
                      : "hover:bg-slate-200 dark:hover:bg-slate-800"
                  }`
                }
              >
                <span aria-hidden className="w-4 text-center opacity-70">{item.icon}</span>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <main className="min-w-0 flex-1">
        {/* Mobile navigation: the sidebar collapses to a scrollable strip. */}
        <div className="mb-4 flex gap-2 overflow-x-auto md:hidden">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm ${
                  isActive ? "bg-sky-600 text-white" : "bg-white dark:bg-slate-800"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>

        <Routes>
          <Route path="/" element={<Navigate to="/transacties" replace />} />
          <Route path="/transacties" element={<Transactions />} />
          <Route path="/rekeningen" element={<Accounts />} />
          <Route path="/importeren" element={<Import />} />
          <Route path="/regels" element={<Rules />} />
          <Route path="/instellingen" element={<Settings />} />
          <Route path="*" element={<Navigate to="/transacties" replace />} />
        </Routes>
      </main>
    </div>
  );
}
