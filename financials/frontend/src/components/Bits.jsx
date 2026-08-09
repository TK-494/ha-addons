// Small shared pieces: page header, async state, confirmation dialog.

export function PageHeader({ title, subtitle, children }) {
  return (
    <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-xl font-semibold">{title}</h2>
        {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </header>
  );
}

export function Alert({ kind = "info", children, onDismiss }) {
  const styles = {
    info: "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-100",
    error: "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-100",
    success: "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100",
    warning: "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100",
  }[kind];

  return (
    <div className={`mb-4 flex items-start justify-between gap-3 rounded-lg border px-3 py-2 text-sm ${styles}`}>
      <div className="min-w-0">{children}</div>
      {onDismiss && (
        <button className="shrink-0 opacity-60 hover:opacity-100" onClick={onDismiss} aria-label="Sluiten">
          ✕
        </button>
      )}
    </div>
  );
}

export function Spinner({ label = "Bezig…" }) {
  return <p className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">{label}</p>;
}

export function Empty({ children }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
      {children}
    </div>
  );
}

/** Modal that states the consequence before a destructive action. */
export function Confirm({ open, title, children, confirmLabel = "Verwijderen", onConfirm, onCancel, danger = true }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="card w-full max-w-md">
        <h3 className="mb-2 text-lg font-semibold">{title}</h3>
        <div className="mb-4 text-sm text-slate-600 dark:text-slate-300">{children}</div>
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onCancel}>Annuleren</button>
          <button className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
