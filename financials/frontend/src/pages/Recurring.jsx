import { useCallback, useEffect, useMemo, useState } from "react";
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
 *
 * The unfiltered list is too long to scan, and the questions people ask of it
 * are narrow: what do the monthly ones cost together, which annual policies
 * are coming, what changed price. So the totals follow the filter — otherwise
 * filtering just gives you a shorter list to add up by hand.
 */
const SORTS = [
  { value: "monthly", label: "Bedrag per maand" },
  { value: "amount", label: "Bedrag per keer" },
  { value: "last_seen", label: "Laatst gezien" },
  { value: "first_seen", label: "Sinds wanneer" },
  { value: "occurrences", label: "Aantal keer" },
  { value: "label", label: "Naam" },
];

const EMPTY = {
  search: "", interval: "", category: "", kind: "", source: "",
  changed_only: false, min_monthly: "", max_monthly: "",
  sort: "monthly", desc: true, only_active: true,
};

export default function Recurring() {
  const [filters, setFilters] = useState(EMPTY);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const query = useMemo(() => {
    const params = { ...filters };
    if (!params.changed_only) delete params.changed_only;
    return params;
  }, [filters]);

  const load = useCallback(() => {
    setLoading(true);
    api.recurring(query)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [query]);

  useEffect(() => {
    const timer = setTimeout(load, 200);
    return () => clearTimeout(timer);
  }, [load]);

  const update = (patch) => setFilters((f) => ({ ...f, ...patch }));
  const filtered = data && data.count !== data.total_count;

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data && loading) return <Spinner label="Terugkerende betalingen zoeken…" />;
  if (!data) return null;

  return (
    <>
      <PageHeader
        title="Terugkerende betalingen"
        subtitle={
          filtered
            ? `${data.count} van ${data.total_count} · samen ${money(data.monthly_total)} per maand`
            : `${data.count} gevonden · samen ${money(data.monthly_total)} per maand (${money(data.yearly_total)} per jaar)`
        }
      >
        {filtered && (
          <button className="btn-ghost" onClick={() => setFilters({ ...EMPTY, only_active: filters.only_active })}>
            Filters wissen
          </button>
        )}
      </PageHeader>

      <section className="card mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2">
          <label className="label">Zoeken</label>
          <input
            className="input"
            placeholder="Naam of categorie"
            value={filters.search}
            onChange={(e) => update({ search: e.target.value })}
          />
        </div>
        <div>
          <label className="label">Ritme</label>
          <select className="input" value={filters.interval} onChange={(e) => update({ interval: e.target.value })}>
            <option value="">Elk ritme</option>
            {data.facets.intervals.map((f) => (
              <option key={f.value} value={f.value}>{f.value} ({f.count})</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Categorie</label>
          <select className="input" value={filters.category} onChange={(e) => update({ category: e.target.value })}>
            <option value="">Alle categorieën</option>
            {data.facets.categories.map((f) => (
              <option key={f.value} value={f.value}>{f.value} ({f.count})</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Soort</label>
          <select className="input" value={filters.kind} onChange={(e) => update({ kind: e.target.value })}>
            <option value="">Vast en variabel</option>
            <option value="fixed">Alleen vaste lasten</option>
            <option value="variable">Alleen variabel</option>
          </select>
        </div>
        <div>
          <label className="label">Herkomst</label>
          <select className="input" value={filters.source} onChange={(e) => update({ source: e.target.value })}>
            <option value="">Alles</option>
            <option value="mandate">Incassant-ID (exact)</option>
            <option value="name">Op naam (geschat)</option>
          </select>
        </div>
        <div>
          <label className="label">Per maand vanaf</label>
          <input
            type="number"
            step="1"
            className="input"
            placeholder="€"
            value={filters.min_monthly}
            onChange={(e) => update({ min_monthly: e.target.value })}
          />
        </div>
        <div>
          <label className="label">Per maand tot</label>
          <input
            type="number"
            step="1"
            className="input"
            placeholder="€"
            value={filters.max_monthly}
            onChange={(e) => update({ max_monthly: e.target.value })}
          />
        </div>
        <div>
          <label className="label">Sorteren op</label>
          <div className="flex gap-1">
            <select className="input" value={filters.sort} onChange={(e) => update({ sort: e.target.value })}>
              {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
            <button
              className="btn-ghost"
              title={filters.desc ? "Hoog naar laag" : "Laag naar hoog"}
              onClick={() => update({ desc: !filters.desc })}
            >
              {filters.desc ? "↓" : "↑"}
            </button>
          </div>
        </div>
        <label className="flex items-end gap-2 pb-1 text-sm">
          <input
            type="checkbox"
            checked={filters.changed_only}
            onChange={(e) => update({ changed_only: e.target.checked })}
          />
          Alleen gewijzigd bedrag
        </label>
        <label className="flex items-end gap-2 pb-1 text-sm">
          <input
            type="checkbox"
            checked={filters.only_active}
            onChange={(e) => update({ only_active: e.target.checked })}
          />
          Alleen actieve
        </label>
      </section>

      {filtered && (
        <p className="mb-3 text-sm">
          Deze selectie kost <strong>{money(data.monthly_total)}</strong> per maand
          {" "}({money(data.yearly_total)} per jaar)
          {data.fixed_total > 0 && data.fixed_total !== data.monthly_total && (
            <>, waarvan {money(data.fixed_total)} vaste lasten</>
          )}.
        </p>
      )}

      {data.items.length === 0 ? (
        <Empty>
          Niets gevonden met deze filters.
          {data.total_count > 0 && " Er zijn er wel " + data.total_count + " zonder filters."}
        </Empty>
      ) : (
        <div className="card overflow-x-auto p-0">
          <table className="min-w-full">
            <thead className="border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th className="th">Wie</th>
                <th className="th">Ritme</th>
                <th className="th">Soort</th>
                <th className="th text-right">Bedrag</th>
                <th className="th text-right">Per maand</th>
                <th className="th">Laatst</th>
                <th className="th">Herkomst</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {data.items.map((row) => (
                <tr key={row.key} className={row.active ? "" : "opacity-60"}>
                  <td className="td">
                    <Link
                      className="font-medium hover:underline"
                      to={`/transacties?search=${encodeURIComponent(row.label.slice(0, 24))}`}
                    >
                      {row.label}
                    </Link>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {row.category || "zonder categorie"} · {row.occurrences}× sinds {shortDate(row.first_seen)}
                    </div>
                  </td>
                  <td className="td whitespace-nowrap">{row.interval}</td>
                  <td className="td">
                    <span
                      className={`pill text-[11px] ${
                        row.committed
                          ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-100"
                          : "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-100"
                      }`}
                      title={
                        row.committed
                          ? "Vaste last: er is een machtiging, of het bedrag blijft gelijk"
                          : "Keert terug maar het bedrag wisselt en er is geen machtiging — je kunt hem overslaan"
                      }
                    >
                      {row.committed ? "vast" : "variabel"}
                    </span>
                  </td>
                  <td className="td text-right tabular-nums">
                    {money(Math.abs(row.typical_amount))}
                    {row.amount_changed && (
                      <span
                        className="ml-1 text-xs text-amber-600 dark:text-amber-400"
                        title="Het laatste bedrag wijkt af van wat gebruikelijk was"
                      >
                        gewijzigd
                      </span>
                    )}
                  </td>
                  <td className="td text-right font-medium tabular-nums">
                    {money(Math.abs(row.monthly_equivalent))}
                  </td>
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
        Groepen op <strong>incassant-ID</strong> komen rechtstreeks uit de machtiging bij je bank en
        zijn exact. Groepen op <strong>naam</strong> zijn afgeleid uit de omschrijving en kunnen er
        soms naast zitten. <strong>Vast</strong> betekent: er is een machtiging, of het bedrag blijft
        elke keer gelijk — de rest keert wel terug maar kun je overslaan.
      </p>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        Een lang ritme betekent niet altijd een abonnement: drie supermarktbezoeken verspreid over
        jaren komen ook als “jaarlijks” naar boven. Filter op <em>alleen vaste lasten</em> om
        uitsluitend echte verplichtingen te zien.
      </p>
    </>
  );
}
