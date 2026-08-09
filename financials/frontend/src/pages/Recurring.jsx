import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { money, shortDate } from "../format.js";

/**
 * Detected subscriptions and standing charges.
 *
 * Rabobank direct debits carry an `Incassant ID`, so those groups are exact
 * rather than guessed — the list marks which is which, because a name-matched
 * group deserves more scepticism.
 */
export default function Recurring() {
  const [rows, setRows] = useState(null);
  const [onlyActive, setOnlyActive] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setRows(null);
    api.recurring(onlyActive).then(setRows).catch((e) => setError(e.message));
  }, [onlyActive]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!rows) return <Spinner label="Terugkerende betalingen zoeken…" />;

  const monthly = rows.reduce((sum, r) => sum + Math.abs(r.monthly_equivalent), 0);

  return (
    <>
      <PageHeader
        title="Terugkerende betalingen"
        subtitle={`${rows.length} gevonden · samen ${money(monthly)} per maand (${money(monthly * 12)} per jaar)`}
      >
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={onlyActive} onChange={(e) => setOnlyActive(e.target.checked)} />
          Alleen actieve
        </label>
      </PageHeader>

      {rows.length === 0 ? (
        <Empty>Nog niets herkend. Er zijn minstens drie maanden aan gegevens nodig.</Empty>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="min-w-full">
            <thead className="border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th className="th">Wie</th>
                <th className="th">Ritme</th>
                <th className="th text-right">Bedrag</th>
                <th className="th text-right">Per maand</th>
                <th className="th">Laatst</th>
                <th className="th">Herkomst</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {rows.map((row) => (
                <tr key={row.key} className={row.active ? "" : "opacity-60"}>
                  <td className="td">
                    <Link className="font-medium hover:underline" to={`/transacties?search=${encodeURIComponent(row.label.slice(0, 24))}`}>
                      {row.label}
                    </Link>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {row.category || "zonder categorie"} · {row.occurrences}× sinds {shortDate(row.first_seen)}
                    </div>
                  </td>
                  <td className="td">{row.interval}</td>
                  <td className="td text-right tabular-nums">
                    {money(Math.abs(row.typical_amount))}
                    {row.amount_changed && (
                      <span className="ml-1 text-xs text-amber-600 dark:text-amber-400" title="Het laatste bedrag wijkt af van wat gebruikelijk was">
                        gewijzigd
                      </span>
                    )}
                  </td>
                  <td className="td text-right tabular-nums font-medium">{money(Math.abs(row.monthly_equivalent))}</td>
                  <td className="td whitespace-nowrap">{shortDate(row.last_seen)}</td>
                  <td className="td text-xs text-slate-500 dark:text-slate-400">
                    {row.from_creditor_id ? "incassant-ID" : "naam"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
        Groepen op <strong>incassant-ID</strong> komen rechtstreeks uit de machtiging bij je bank en zijn exact.
        Groepen op <strong>naam</strong> zijn afgeleid uit de omschrijving en kunnen er soms naast zitten.
      </p>
    </>
  );
}
