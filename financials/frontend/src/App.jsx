import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api.js";
import { applyTheme } from "./theme.js";
import { setPrivate } from "./format.js";
import Overview from "./pages/Overview.jsx";
import Import from "./pages/Import.jsx";
import Transactions from "./pages/Transactions.jsx";
import Accounts from "./pages/Accounts.jsx";
import CategoryDetail from "./pages/CategoryDetail.jsx";
import Recurring from "./pages/Recurring.jsx";
import Budgets from "./pages/Budgets.jsx";
import Expenses from "./pages/Expenses.jsx";
import Uncategorised from "./pages/Uncategorised.jsx";
import Salary from "./pages/Salary.jsx";
import Counterparty from "./pages/Counterparty.jsx";
import Tags from "./pages/Tags.jsx";
import Rules from "./pages/Rules.jsx";
import Settings from "./pages/Settings.jsx";

const NAV = [
  { to: "/overzicht", label: "Overzicht", icon: "◧" },
  { to: "/transacties", label: "Transacties", icon: "≡" },
  { to: "/salaris", label: "Salaris", icon: "€" },
  { to: "/budget", label: "Budget", icon: "◑" },
  { to: "/vaste-lasten", label: "Vaste lasten", icon: "⛓" },
  { to: "/variabele-uitgaven", label: "Variabele uitgaven", icon: "◇" },
  { to: "/terugkerend", label: "Terugkerend", icon: "↻" },
  { to: "/te-categoriseren", label: "Nog te categoriseren", icon: "?" },
  { to: "/labels", label: "Labels", icon: "◆" },
  { to: "/rekeningen", label: "Rekeningen", icon: "▤" },
  { to: "/importeren", label: "Importeren", icon: "↑" },
  { to: "/regels", label: "Categorieën & regels", icon: "⚑" },
  { to: "/instellingen", label: "Instellingen", icon: "⚙" },
];

const STORAGE_KEY = "financials.sidebar.collapsed";
const PRIVACY_KEY = "financials.privacy";

const storedPrivacy = (() => {
  try {
    return localStorage.getItem(PRIVACY_KEY) === "1";
  } catch {
    return false;
  }
})();

// Applied before the first render, so opening the app with privacy mode on
// never flashes the real amounts for a frame.
setPrivate(storedPrivacy);

export default function App() {
  // Privacy mode: masks every amount and account number so the app can be
  // shown to somebody without showing them your finances. It persists, because
  // a reload halfway through a demo uncovering everything is the exact failure
  // it exists to prevent — and the lit-up button makes it hard to forget.
  const [privacy, setPrivacy] = useState(storedPrivacy);

  function togglePrivacy() {
    const next = !privacy;
    setPrivate(next);  // the module flag first: it is read during the render below
    setPrivacy(next);
  }

  // Collapsed to icons gives the transaction table ~170px more, which is the
  // page that needs it most. Remembered, because re-collapsing it on every
  // visit would be its own small annoyance.
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });

  // The stored theme is the source of truth; the cache only prevents a flash.
  useEffect(() => {
    api.appearance()
      .then(({ theme }) => {
        applyTheme(theme);
        try { localStorage.setItem("financials.theme", theme); } catch { /* ignore */ }
      })
      .catch(() => { /* keep whatever the cache applied */ });
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
    } catch {
      /* private mode — the toggle still works, it just forgets */
    }
  }, [collapsed]);

  useEffect(() => {
    try {
      localStorage.setItem(PRIVACY_KEY, privacy ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [privacy]);

  // A shortcut is worth it here: the moment you need this is the moment
  // somebody is already looking over your shoulder. Ignored while typing, so
  // it never eats a "p" in the search box.
  useEffect(() => {
    function onKey(event) {
      if (event.key !== "p" && event.key !== "P") return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const tag = event.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (event.target?.isContentEditable) return;
      togglePrivacy();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [privacy]);

  const privacyButton = (extra = "") => (
    <button
      className={`${privacy ? "btn-primary" : "btn-ghost"} px-2 ${extra}`}
      onClick={togglePrivacy}
      title={privacy ? "Bedragen weer tonen (P)" : "Privacymodus: bedragen verbergen (P)"}
      aria-label={privacy ? "Bedragen weer tonen" : "Privacymodus inschakelen"}
      aria-pressed={privacy}
    >
      {privacy ? "🙈" : "👁"}
    </button>
  );

  return (
    <div className="mx-auto flex min-h-screen max-w-[110rem] gap-4 p-4">
      <nav className={`hidden shrink-0 md:block ${collapsed ? "w-14" : "w-56"} transition-[width] duration-150`}>
        <div className={`mb-6 flex items-center gap-2 ${collapsed ? "justify-center" : "justify-between px-2"}`}>
          {!collapsed && (
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold">Financials</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">Huishoudboekje</p>
            </div>
          )}
          <div className={`flex gap-1 ${collapsed ? "flex-col" : ""}`}>
            {privacyButton()}
            <button
              className="btn-ghost px-2"
              onClick={() => setCollapsed(!collapsed)}
              title={collapsed ? "Menu uitklappen" : "Menu inklappen"}
              aria-label={collapsed ? "Menu uitklappen" : "Menu inklappen"}
              aria-expanded={!collapsed}
            >
              {collapsed ? "»" : "«"}
            </button>
          </div>
        </div>
        {privacy && !collapsed && (
          <p className="mb-3 px-2 text-xs text-sky-700 dark:text-sky-300">
            Privacymodus aan — bedragen en rekeningnummers verborgen.
          </p>
        )}
        <ul className="space-y-1">
          {NAV.map((item) => (
            <li key={item.to}>
              {/* The label becomes the tooltip when collapsed, so an icon-only
                  sidebar stays navigable without guessing. */}
              <NavLink
                to={item.to}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg py-2 text-sm ${
                    collapsed ? "justify-center px-0" : "px-3"
                  } ${
                    isActive
                      ? "bg-sky-600 text-white"
                      : "hover:bg-slate-200 dark:hover:bg-slate-800"
                  }`
                }
              >
                <span aria-hidden className="w-4 text-center opacity-70">{item.icon}</span>
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <main className="min-w-0 flex-1">
        {/* Mobile navigation: the sidebar collapses to a scrollable strip. */}
        <div className="mb-4 flex gap-2 md:hidden">
          {privacyButton("shrink-0")}
          <div className="flex gap-2 overflow-x-auto">
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
        </div>

        <Routes>
          <Route path="/" element={<Navigate to="/overzicht" replace />} />
          <Route path="/overzicht" element={<Overview />} />
          <Route path="/transacties" element={<Transactions />} />
          <Route path="/salaris" element={<Salary />} />
          <Route path="/budget" element={<Budgets />} />
          <Route path="/vaste-lasten" element={<Expenses kind="fixed" />} />
          <Route path="/variabele-uitgaven" element={<Expenses kind="variable" />} />
          <Route path="/terugkerend" element={<Recurring />} />
          <Route path="/te-categoriseren" element={<Uncategorised />} />
          <Route path="/categorie/:id" element={<CategoryDetail />} />
          <Route path="/tegenpartij" element={<Counterparty />} />
          <Route path="/labels" element={<Tags />} />
          <Route path="/rekeningen" element={<Accounts />} />
          <Route path="/importeren" element={<Import />} />
          <Route path="/regels" element={<Rules />} />
          <Route path="/instellingen" element={<Settings />} />
          <Route path="*" element={<Navigate to="/overzicht" replace />} />
        </Routes>
      </main>
    </div>
  );
}
