import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { money, shortDate } from "../format.js";

const KINDS = [
  { value: "checking", label: "Betaalrekening" },
  { value: "savings", label: "Spaarrekening" },
  { value: "credit_card", label: "Creditcard" },
];

/**
 * Each account stands on its own. `kind` is what decides how it reads at
 * household level: money moved to a savings account is saved, not spent.
 */
export default function Accounts() {
  const [accounts, setAccounts] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.accounts().then(setAccounts).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function patch(id, payload) {
    try {
      await api.updateAccount(id, payload);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function rematch() {
    setBusy(true);
    try {
      const r = await api.rematchTransfers();
      setNotice(
        `${r.pairs_matched} overboekingen gekoppeld, ${r.settlements_matched} creditcard-afrekeningen verrekend` +
        (r.legs_pending ? `, ${r.legs_pending} wachten op de andere kant.` : ".")
      );
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const total = (accounts || [])
    .filter((a) => a.include_in_networth && !a.archived)
    .reduce((sum, a) => sum + a.balance, 0);

  return (
    <>
      <PageHeader title="Rekeningen" subtitle={accounts ? `Totaal ${money(total)}` : ""}>
        <button className="btn-ghost" onClick={rematch} disabled={busy}>
          Overboekingen opnieuw koppelen
        </button>
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      {accounts === null ? (
        <Spinner />
      ) : accounts.length === 0 ? (
        <Empty>Nog geen rekeningen. Importeer eerst een CSV-bestand.</Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {accounts.map((account) => (
            <article key={account.id} className="card">
              <div className="mb-3 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate font-semibold">{account.label}</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {account.card_last4 ? `Creditcard ••${account.card_last4}` : account.iban}
                  </p>
                </div>
                <p className="whitespace-nowrap text-lg font-semibold">{money(account.balance)}</p>
              </div>

              <dl className="mb-3 grid grid-cols-2 gap-2 text-xs text-slate-500 dark:text-slate-400">
                <div><dt className="inline">Transacties: </dt><dd className="inline">{account.transaction_count}</dd></div>
                <div>
                  <dt className="inline">Periode: </dt>
                  <dd className="inline">
                    {account.first_transaction ? `${shortDate(account.first_transaction)} – ${shortDate(account.last_transaction)}` : "—"}
                  </dd>
                </div>
                {account.settlement_iban && (
                  <div className="col-span-2">
                    <dt className="inline">Wordt afgeschreven van: </dt>
                    <dd className="inline">{account.settlement_iban}</dd>
                  </div>
                )}
              </dl>

              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <label className="label">Naam</label>
                  <input
                    className="input"
                    defaultValue={account.display_name || ""}
                    placeholder={account.card_last4 ? "Creditcard" : "Betaalrekening"}
                    onBlur={(e) => {
                      if (e.target.value !== (account.display_name || "")) {
                        patch(account.id, { display_name: e.target.value });
                      }
                    }}
                  />
                </div>
                <div>
                  <label className="label">Soort</label>
                  <select
                    className="input"
                    value={account.kind}
                    onChange={(e) => patch(account.id, { kind: e.target.value })}
                  >
                    {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                  </select>
                </div>
              </div>

              <label className="mt-3 flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={account.include_in_networth}
                  onChange={(e) => patch(account.id, { include_in_networth: e.target.checked })}
                />
                Meetellen in totaalvermogen
              </label>
            </article>
          ))}
        </div>
      )}

      <p className="mt-6 text-xs text-slate-500 dark:text-slate-400">
        Zet een rekening op <strong>Spaarrekening</strong> om geld dat je erheen overmaakt als gespaard te
        laten tellen in plaats van als uitgave. Overboekingen tussen je eigen rekeningen blijven in beide
        rekeningen staan — ze tellen alleen niet mee in het huishoudtotaal.
      </p>
    </>
  );
}
