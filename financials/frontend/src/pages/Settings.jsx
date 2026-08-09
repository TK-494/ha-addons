import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Alert, PageHeader, Spinner } from "../components/Bits.jsx";

const MODES = [
  { value: "calendar", label: "Kalendermaand (1e van de maand)" },
  { value: "salary", label: "Salarisdag (automatisch bepaald)" },
  { value: "day", label: "Vaste dag van de maand" },
];

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    api.periodSettings().then(setSettings).catch((e) => setError(e.message));
  }, []);

  async function save(patch) {
    const next = { mode: settings.mode, start_day: settings.start_day, ...patch };
    try {
      setSettings(await api.savePeriodSettings(next));
      setNotice("Opgeslagen.");
    } catch (e) {
      setError(e.message);
    }
  }

  if (!settings) return <Spinner />;

  return (
    <>
      <PageHeader title="Instellingen" />

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && <Alert kind="success" onDismiss={() => setNotice(null)}>{notice}</Alert>}

      <section className="card max-w-xl">
        <h3 className="mb-1 font-semibold">Maandgrens</h3>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
          Bepaalt waar een maand begint in de overzichten. Dit is puur een weergave-instelling: er wordt niets
          herschreven, dus je kunt vrij wisselen zonder opnieuw te importeren.
        </p>

        <div className="mb-3">
          <label className="label">Maand begint op</label>
          <select className="input" value={settings.mode} onChange={(e) => save({ mode: e.target.value })}>
            {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>

        {settings.mode === "day" && (
          <div className="mb-3 max-w-[8rem]">
            <label className="label">Dag (1–28)</label>
            <input
              type="number"
              min="1"
              max="28"
              className="input"
              defaultValue={settings.start_day}
              onBlur={(e) => save({ start_day: Number(e.target.value) })}
            />
          </div>
        )}

        <p className="text-sm text-slate-600 dark:text-slate-300">
          Actieve grens: dag <strong>{settings.effective_day}</strong>.
          {settings.mode === "salary" && (
            settings.detected_salary_day
              ? ` Salarisdag herkend als de ${settings.detected_salary_day}e.`
              : " Nog geen salarisdag herkend — categoriseer eerst wat inkomsten als Inkomen."
          )}
        </p>
      </section>
    </>
  );
}
