import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { money } from "../format.js";

/**
 * A worklist, not a report.
 *
 * The overview used to show the five largest uncategorised groups and nothing
 * you could do about them. Here each group is one dropdown away from being
 * done, and picking a category also writes the rule — otherwise the same rows
 * come back next month and the work never ends.
 *
 * Largest amount first, because that is where being uncategorised actually
 * distorts the figures.
 */
export default function Uncategorised() {
  const [data, setData] = useState(null);
  const [categories, setCategories] = useState([]);
  const [limit, setLimit] = useState(25);
  const [withRule, setWithRule] = useState(true);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = () => api.uncategorised(limit).then(setData).catch((e) => setError(e.message));

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [limit]);
  useEffect(() => { api.categories().then(setCategories).catch(() => {}); }, []);

  async function assign(group, categoryId) {
    if (!categoryId) return;
    setBusy(group.name);
    try {
      const result = await api.assignUncategorised(group.name, Number(categoryId), withRule);
      setNotice(
        `${result.updated} transacties van “${group.name}” gecategoriseerd` +
        (result.rule_id ? " en er is een regel gemaakt, zodat de volgende import meteen klopt." : ".")
      );
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  if (!data) return <Spinner />;

  const done = data.total_uncategorised === 0;

  return (
    <>
      <PageHeader
        title="Nog te categoriseren"
        subtitle={
          done
            ? "Alles is ingedeeld."
            : `${data.total_uncategorised} transacties · ${money(data.total_amount)} · ${data.progress}% van je grootboek is al ingedeeld`
        }
      >
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={withRule} onChange={(e) => setWithRule(e.target.checked)} />
          Ook een regel maken
        </label>
        <select className="input w-auto" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
          {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n} groepen</option>)}
        </select>
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      <div className="mb-4 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div className="h-full rounded-full bg-emerald-500" style={{ width: `${data.progress}%` }} />
      </div>

      {done ? (
        <Empty>
          Niets meer te doen. Nieuwe imports die niet door een regel gevangen worden verschijnen hier
          vanzelf.
        </Empty>
      ) : (
        <>
          <div className="card overflow-x-auto p-0">
            <table className="min-w-full">
              <thead className="border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="th">Tegenpartij</th>
                  <th className="th text-right">Bedrag</th>
                  <th className="th text-right">Aantal</th>
                  <th className="th">Categorie toewijzen</th>
                  <th className="th"> </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {data.groups.map((group) => (
                  <tr key={group.name} className={busy === group.name ? "opacity-50" : ""}>
                    <td className="td break-words font-medium">{group.name}</td>
                    <td className="td text-right tabular-nums">{money(Math.abs(group.amount))}</td>
                    <td className="td text-right tabular-nums">{group.transactions}</td>
                    <td className="td">
                      <select
                        className="input py-1"
                        defaultValue=""
                        disabled={busy === group.name}
                        onChange={(e) => assign(group, e.target.value)}
                      >
                        <option value="">— kies —</option>
                        {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </td>
                    <td className="td text-right">
                      <Link
                        className="btn-ghost whitespace-nowrap"
                        to={`/transacties?search=${encodeURIComponent(group.name.slice(0, 24))}&uncategorised=1`}
                      >
                        Bekijken
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
            Grootste bedragen eerst — daar vertekent het ontbreken van een categorie je cijfers het
            meest. Met <em>ook een regel maken</em> aangevinkt wordt de keuze onthouden, zodat
            dezelfde tegenpartij bij de volgende import meteen goed staat. Staat een groep er ten
            onrechte tussen, gebruik dan <em>Bekijken</em> om de losse transacties te bekijken.
          </p>
        </>
      )}
    </>
  );
}
