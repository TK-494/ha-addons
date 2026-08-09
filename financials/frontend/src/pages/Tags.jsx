import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Alert, Confirm, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { money, shortDate } from "../format.js";

/**
 * Labels are the second dimension next to categories.
 *
 * A tank of fuel during a holiday is fully fuel and fully holiday, so it keeps
 * the category "Brandstof" and gains the label "Vakantie 2019". Categories
 * stay a clean partition of your spending; labels answer the cross-cutting
 * question of what a trip or a renovation cost in total.
 */
export default function Tags() {
  const [tags, setTags] = useState(null);
  const [open, setOpen] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [editing, setEditing] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = () => api.tags().then(setTags).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (open === null) { setBreakdown(null); return; }
    api.tagBreakdown(open).then(setBreakdown).catch((e) => setError(e.message));
  }, [open]);

  if (tags === null) return <Spinner />;

  return (
    <>
      <PageHeader
        title="Labels"
        subtitle="Een tweede laag naast de categorie — voor een vakantie, een verbouwing, een project"
      >
        <button
          className="btn-primary"
          onClick={() => setEditing({ isNew: true, name: "", color: "#0ea5e9", note: "" })}
        >
          Nieuw label
        </button>
      </PageHeader>

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      {tags.length === 0 ? (
        <Empty>
          Nog geen labels. Maak er één aan, ga daarna naar Transacties, filter op de periode,
          selecteer de regels en ken het label in één keer toe.
        </Empty>
      ) : (
        <div className="space-y-2">
          {tags.map((tag) => (
            <article key={tag.id} className="card">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button
                  className="flex min-w-0 items-center gap-2 text-left"
                  onClick={() => setOpen(open === tag.id ? null : tag.id)}
                >
                  <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: tag.color }} />
                  <span className="truncate font-medium">{tag.name}</span>
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    {tag.transactions} transacties
                    {tag.first_seen && ` · ${shortDate(tag.first_seen)} – ${shortDate(tag.last_seen)}`}
                  </span>
                </button>
                <div className="flex items-center gap-2">
                  <span className="tabular-nums font-semibold">{money(Math.abs(tag.total))}</span>
                  <Link className="btn-ghost" to={`/transacties?tag_id=${tag.id}`}>Transacties</Link>
                  <button className="btn-ghost" onClick={() => setEditing(tag)}>Bewerken</button>
                  <button className="btn-danger" onClick={() => setConfirmDelete(tag)}>Verwijderen</button>
                </div>
              </div>

              {tag.note && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{tag.note}</p>
              )}

              {open === tag.id && (
                breakdown === null ? (
                  <Spinner label="Verdeling laden…" />
                ) : (
                  <div className="mt-3 border-t border-slate-200 pt-3 dark:border-slate-700">
                    <p className="mb-2 text-sm">
                      Uitgegeven <strong>{money(breakdown.spent)}</strong>
                      {breakdown.received > 0 && <> · terugontvangen {money(breakdown.received)}</>}
                      {breakdown.received > 0 && <> · netto <strong>{money(Math.abs(breakdown.net))}</strong></>}
                    </p>
                    <ul className="space-y-1 text-sm">
                      {breakdown.categories.map((row) => (
                        <li key={row.name} className="flex items-center justify-between gap-2">
                          <span className="flex min-w-0 items-center gap-2">
                            <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: row.color }} />
                            <span className="truncate">{row.name}</span>
                          </span>
                          <span className="whitespace-nowrap tabular-nums">
                            {money(row.amount)}
                            <span className="ml-1 text-xs text-slate-500">{row.transactions}×</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              )}
            </article>
          ))}
        </div>
      )}

      <p className="mt-6 text-xs text-slate-500 dark:text-slate-400">
        Labels veranderen niets aan je inkomsten- en uitgaventotalen. Een transactie houdt precies één
        categorie — daarmee blijft de optelsom kloppen — en kan daarnaast zoveel labels dragen als je
        wilt.
      </p>

      {editing && (
        <TagDialog
          tag={editing}
          onClose={() => setEditing(null)}
          onSaved={(message) => { setEditing(null); setNotice(message); load(); }}
          onError={setError}
        />
      )}

      <Confirm
        open={Boolean(confirmDelete)}
        title="Label verwijderen"
        onCancel={() => setConfirmDelete(null)}
        onConfirm={async () => {
          const tag = confirmDelete;
          setConfirmDelete(null);
          try {
            const result = await api.deleteTag(tag.id);
            setNotice(`Label verwijderd bij ${result.untagged_transactions} transacties.`);
            setOpen(null);
            load();
          } catch (e) {
            setError(e.message);
          }
        }}
      >
        <strong>{confirmDelete?.name}</strong> wordt verwijderd bij{" "}
        {confirmDelete?.transactions} transacties. De transacties zelf blijven gewoon bestaan,
        inclusief hun categorie.
      </Confirm>
    </>
  );
}

function TagDialog({ tag, onClose, onSaved, onError }) {
  const isNew = Boolean(tag.isNew);
  const [form, setForm] = useState({
    name: tag.name || "",
    color: tag.color || "#0ea5e9",
    note: tag.note || "",
  });
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      const payload = { ...form, note: form.note.trim() || null };
      if (isNew) {
        await api.createTag(payload);
        onSaved(`Label “${form.name}” aangemaakt.`);
      } else {
        await api.updateTag(tag.id, payload);
        onSaved(`Label “${form.name}” bijgewerkt.`);
      }
    } catch (e) {
      onError(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="card w-full max-w-md">
        <h3 className="mb-3 text-lg font-semibold">{isNew ? "Nieuw label" : "Label bewerken"}</h3>

        <div className="mb-3 grid gap-3 sm:grid-cols-[1fr_auto]">
          <div>
            <label className="label">Naam</label>
            <input
              className="input"
              maxLength={60}
              placeholder="Vakantie 2019"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="label">Kleur</label>
            <input
              type="color"
              className="input h-9 w-16 p-1"
              value={form.color}
              onChange={(e) => setForm({ ...form, color: e.target.value })}
            />
          </div>
        </div>

        <div className="mb-4">
          <label className="label">Notitie (optioneel)</label>
          <input
            className="input"
            maxLength={200}
            placeholder="Frankrijk, twee weken"
            value={form.note}
            onChange={(e) => setForm({ ...form, note: e.target.value })}
          />
        </div>

        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose} disabled={busy}>Annuleren</button>
          <button className="btn-primary" onClick={save} disabled={busy || form.name.trim().length < 1}>
            Opslaan
          </button>
        </div>
      </div>
    </div>
  );
}
