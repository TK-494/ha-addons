import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { Alert, Confirm, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { bytes, dateTime, maskAccount, money, shortDate } from "../format.js";

/**
 * Upload → preview → confirm.
 *
 * The file is stored and parsed first, but nothing reaches the ledger until
 * the user has seen which format was detected, which account it belongs to and
 * what the first rows look like *as parsed*. That screen is the guard against
 * a wrong format quietly importing a few hundred rows at € 0,00.
 */
export default function Import() {
  const [formats, setFormats] = useState([]);
  const [formatKey, setFormatKey] = useState("auto");
  const [preview, setPreview] = useState(null);
  const [history, setHistory] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const fileInput = useRef(null);

  const refresh = () => api.imports().then(setHistory).catch((e) => setError(e.message));

  useEffect(() => {
    api.formats().then(setFormats).catch((e) => setError(e.message));
    refresh();
  }, []);

  async function handleFile(file) {
    if (!file) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    setPreview(null);
    try {
      setPreview(await api.upload(file, formatKey));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function changeFormat(nextKey) {
    setFormatKey(nextKey);
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      setPreview(await api.repreview(preview.batch_id, nextKey));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmImport() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.commitImport(preview.batch_id, preview.format_key);
      setNotice(
        `${result.rows_imported} transacties geïmporteerd` +
          (result.rows_duplicate ? `, ${result.rows_duplicate} overgeslagen (al aanwezig)` : "") +
          (result.rows_failed ? `, ${result.rows_failed} mislukt` : "")
      );
      setPreview(null);
      refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancelPreview() {
    // Abandoning a preview removes the stored file too: an uncommitted upload
    // should not linger on disk.
    try {
      await api.deleteImport(preview.batch_id, false);
    } catch {
      /* the preview is being discarded anyway */
    }
    setPreview(null);
    refresh();
  }

  async function askDelete(batch) {
    const impact = await api.importImpact(batch.id);
    setConfirmDelete({ batch, transactions: impact.transactions, withTransactions: false });
  }

  async function doDelete() {
    const { batch, withTransactions } = confirmDelete;
    setConfirmDelete(null);
    setBusy(true);
    try {
      const result = await api.deleteImport(batch.id, withTransactions);
      setNotice(
        withTransactions
          ? `Bestand en ${result.deleted_transactions} transacties verwijderd.`
          : "Bestand verwijderd; de transacties zijn bewaard."
      );
      refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Importeren"
        subtitle="Upload een CSV-export van je bank. Je ziet eerst wat er herkend is, daarna pas importeren."
      />

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      <section className="card mb-6">
        <div className="mb-3 max-w-sm">
          <label className="label" htmlFor="format">Bank / formaat</label>
          <select
            id="format"
            className="input"
            value={formatKey}
            onChange={(e) => changeFormat(e.target.value)}
          >
            {formats.map((f) => (
              <option key={f.key} value={f.key}>{f.label}</option>
            ))}
          </select>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Automatisch herkennen kijkt naar de kolomnamen. Kies handmatig als dat de verkeerde bank oplevert —
            een expliciete keuze wint altijd.
          </p>
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files?.[0]); }}
          className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
            dragging ? "border-sky-500 bg-sky-50 dark:bg-sky-950" : "border-slate-300 dark:border-slate-600"
          }`}
        >
          <p className="mb-2 text-sm">Sleep een CSV-bestand hierheen</p>
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.txt"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <button className="btn-primary" disabled={busy} onClick={() => fileInput.current?.click()}>
            {busy ? "Bezig…" : "Bestand kiezen"}
          </button>
        </div>
      </section>

      {preview && <PreviewPanel preview={preview} busy={busy} onConfirm={confirmImport} onCancel={cancelPreview} />}

      <section>
        <h3 className="mb-2 text-lg font-semibold">Eerdere imports</h3>
        {history === null ? (
          <Spinner />
        ) : history.length === 0 ? (
          <Empty>Nog niets geïmporteerd.</Empty>
        ) : (
          <div className="card overflow-x-auto p-0">
            <table className="min-w-full">
              <thead className="border-b border-slate-200 dark:border-slate-700">
                <tr>
                  <th className="th">Bestand</th>
                  <th className="th">Formaat</th>
                  <th className="th">Periode</th>
                  <th className="th text-right">Regels</th>
                  <th className="th text-right">In app</th>
                  <th className="th"> </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {history.map((batch) => (
                  <tr key={batch.id}>
                    <td className="td">
                      <div className="font-medium">{batch.original_filename}</div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">
                        {dateTime(batch.uploaded_at)} · {bytes(batch.size_bytes)}
                        {!batch.committed && " · niet bevestigd"}
                      </div>
                    </td>
                    <td className="td">{batch.format_label}</td>
                    <td className="td whitespace-nowrap text-sm">
                      {batch.date_from ? `${shortDate(batch.date_from)} – ${shortDate(batch.date_to)}` : "—"}
                    </td>
                    <td className="td text-right">
                      {batch.rows_imported}
                      {batch.rows_duplicate > 0 && (
                        <span className="ml-1 text-xs text-slate-500">+{batch.rows_duplicate} dubbel</span>
                      )}
                      {batch.rows_failed > 0 && (
                        <span className="ml-1 text-xs text-rose-500">{batch.rows_failed} fout</span>
                      )}
                    </td>
                    <td className="td text-right">{batch.current_transactions}</td>
                    <td className="td">
                      <div className="flex justify-end gap-1">
                        <a className="btn-ghost" href={api.downloadUrl(batch.id)}>Download</a>
                        <button
                          className="btn-ghost"
                          disabled={busy}
                          onClick={async () => {
                            setBusy(true);
                            try {
                              const r = await api.reimport(batch.id);
                              setNotice(`Opnieuw ingelezen: ${r.rows_imported} nieuw, ${r.rows_duplicate} al aanwezig.`);
                              refresh();
                            } catch (e) {
                              setError(e.message);
                            } finally {
                              setBusy(false);
                            }
                          }}
                        >
                          Opnieuw inlezen
                        </button>
                        <button className="btn-danger" onClick={() => askDelete(batch)}>Verwijderen</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Confirm
        open={Boolean(confirmDelete)}
        title="Import verwijderen"
        confirmLabel={confirmDelete?.withTransactions ? "Bestand én transacties verwijderen" : "Alleen bestand verwijderen"}
        onCancel={() => setConfirmDelete(null)}
        onConfirm={doDelete}
      >
        <p className="mb-3">
          <strong>{confirmDelete?.batch.original_filename}</strong> hoort bij{" "}
          <strong>{confirmDelete?.transactions}</strong> transacties in de app.
        </p>
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-1"
            checked={confirmDelete?.withTransactions || false}
            onChange={(e) => setConfirmDelete({ ...confirmDelete, withTransactions: e.target.checked })}
          />
          <span>
            Ook de {confirmDelete?.transactions} transacties verwijderen.
            <span className="block text-xs text-slate-500 dark:text-slate-400">
              Zonder vinkje blijft alles in de app staan en verdwijnt alleen het CSV-bestand van schijf —
              opnieuw inlezen kan dan niet meer.
            </span>
          </span>
        </label>
      </Confirm>
    </>
  );
}

function PreviewPanel({ preview, busy, onConfirm, onCancel }) {
  const zeroAmounts = preview.sample.length > 0 && preview.sample.every((row) => row.amount === 0);

  return (
    <section className="card mb-6 border-sky-300 dark:border-sky-700">
      <h3 className="mb-3 text-lg font-semibold">Controleer voordat je importeert</h3>

      {preview.duplicate_of && (
        <Alert kind="warning">
          Dit exacte bestand is al eens geïmporteerd op {dateTime(preview.duplicate_of.uploaded_at)}
          {" "}({preview.duplicate_of.original_filename}). Dubbele regels worden overgeslagen.
        </Alert>
      )}
      {zeroAmounts && (
        <Alert kind="error">
          Alle bedragen in het voorbeeld zijn € 0,00. Dat wijst op een verkeerd gekozen formaat — controleer
          de keuze hierboven voordat je doorgaat.
        </Alert>
      )}

      <dl className="mb-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Stat label="Herkend als" value={preview.format_label} />
        <Stat label="Regels gevonden" value={preview.rows_parsed} />
        <Stat label="Nieuw" value={preview.rows_new} accent="text-emerald-600 dark:text-emerald-400" />
        <Stat
          label="Al aanwezig"
          value={preview.rows_duplicate}
          accent={preview.rows_duplicate ? "text-amber-600 dark:text-amber-400" : undefined}
        />
        <Stat label="Periode" value={preview.date_from ? `${shortDate(preview.date_from)} – ${shortDate(preview.date_to)}` : "—"} />
        <Stat
          label="Niet gelezen"
          value={preview.rows_failed}
          accent={preview.rows_failed ? "text-rose-600 dark:text-rose-400" : undefined}
        />
        <div className="col-span-2">
          <dt className="label">Rekeningen</dt>
          <dd className="flex flex-wrap gap-1">
            {preview.accounts.map((account) => (
              <span
                key={account.key}
                className="pill bg-slate-200 dark:bg-slate-700"
                title={account.known ? "Bestaande rekening" : "Nieuwe rekening"}
              >
                {account.card_last4 ? `${account.product_name || "Creditcard"} ••${account.card_last4}` : maskAccount(account.iban)}
                {!account.known && <span className="text-sky-600 dark:text-sky-400">nieuw</span>}
              </span>
            ))}
          </dd>
        </div>
      </dl>

      <div className="mb-4 overflow-x-auto">
        <p className="label">Eerste regels zoals de app ze gelezen heeft</p>
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="th">Datum</th>
              <th className="th text-right">Bedrag</th>
              <th className="th">Omschrijving</th>
              <th className="th">Tegenpartij</th>
              <th className="th text-right">Saldo na</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
            {preview.sample.map((row, index) => (
              <tr key={index}>
                <td className="td whitespace-nowrap">{shortDate(row.booked_on)}</td>
                <td className={`td text-right font-medium ${row.amount < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                  {money(row.amount)}
                </td>
                <td className="td">{row.description}</td>
                <td className="td">{row.counter_name}</td>
                <td className="td text-right">{row.balance_after === null ? "—" : money(row.balance_after)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {preview.errors?.length > 0 && (
        <details className="mb-4">
          <summary className="cursor-pointer text-sm text-rose-600 dark:text-rose-400">
            {preview.rows_failed} regels konden niet gelezen worden
          </summary>
          <ul className="mt-2 space-y-1 text-xs">
            {preview.errors.map((e) => (
              <li key={e.line_no} className="font-mono">regel {e.line_no}: {e.reason}</li>
            ))}
          </ul>
        </details>
      )}

      <div className="flex justify-end gap-2">
        <button className="btn-ghost" onClick={onCancel} disabled={busy}>Annuleren</button>
        <button className="btn-primary" onClick={onConfirm} disabled={busy || preview.rows_new === 0}>
          {preview.rows_new === 0 ? "Niets nieuws te importeren" : `${preview.rows_new} transacties importeren`}
        </button>
      </div>
    </section>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className={`font-semibold ${accent || ""}`}>{value}</dd>
    </div>
  );
}
