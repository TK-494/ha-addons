import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { getCAOProjection, getCAOSettings, saveCAOSettings, getCAOScales, upsertCAOScale } from "../api";

const fmt = (n) =>
  new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(n);

const FWG_SCALES = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80];

export default function CAOProjection() {
  const [fwgScale, setFwgScale] = useState(30);
  const [currentStep, setCurrentStep] = useState(1);
  const [projection, setProjection] = useState(null);
  const [scales, setScales] = useState([]);
  const [editMode, setEditMode] = useState(false);
  const [editScaleNum, setEditScaleNum] = useState(30);
  const [editValues, setEditValues] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getCAOSettings().then((s) => {
      setFwgScale(s.fwg_scale);
      setCurrentStep(s.current_step);
    });
    getCAOScales().then(setScales);
  }, []);

  useEffect(() => {
    if (fwgScale && currentStep) {
      getCAOProjection(fwgScale, currentStep, 10).then(setProjection);
    }
  }, [fwgScale, currentStep]);

  const maxStep = projection?.max_step || 7;

  async function handleSave() {
    setSaving(true);
    await saveCAOSettings(fwgScale, currentStep);
    setSaving(false);
  }

  function loadEditScale(scaleNum) {
    setEditScaleNum(scaleNum);
    const scaleSteps = scales
      .filter((s) => s.scale === scaleNum)
      .sort((a, b) => a.step - b.step);
    setEditValues(scaleSteps.map((s) => ({ step: s.step, monthly_gross: s.monthly_gross })));
  }

  async function handleSaveScale() {
    for (const step of editValues) {
      await upsertCAOScale({ scale: editScaleNum, step: step.step, monthly_gross: Number(step.monthly_gross) });
    }
    const updated = await getCAOScales();
    setScales(updated);
    getCAOProjection(fwgScale, currentStep, 10).then(setProjection);
    setEditMode(false);
  }

  const currentSalary = projection?.projection?.[0]?.monthly_gross;
  const maxSalary = projection?.projection?.[projection.projection.length - 1]?.monthly_gross;
  const growth = currentSalary && maxSalary ? ((maxSalary - currentSalary) / currentSalary * 100).toFixed(1) : 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">CAO Salaris Groei</h2>
          <p className="text-slate-500 text-sm">VGN CAO — FWG loonschalen</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={() => { setEditMode(!editMode); if (!editMode) loadEditScale(fwgScale); }}>
            {editMode ? "Annuleren" : "✏️ Schalen bewerken"}
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="card">
        <h3 className="text-sm font-semibold text-slate-300 mb-4">Jouw huidige situatie</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">FWG Schaal</label>
            <select
              className="select"
              value={fwgScale}
              onChange={(e) => setFwgScale(Number(e.target.value))}
            >
              {FWG_SCALES.map((s) => (
                <option key={s} value={s}>FWG {s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Huidige periodiek</label>
            <select
              className="select"
              value={currentStep}
              onChange={(e) => setCurrentStep(Number(e.target.value))}
            >
              {Array.from({ length: maxStep }, (_, i) => i + 1).map((s) => (
                <option key={s} value={s}>Periodiek {s}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2 flex items-end">
            <button className="btn-primary w-full" onClick={handleSave} disabled={saving}>
              {saving ? "Opslaan..." : "Instellingen opslaan"}
            </button>
          </div>
        </div>
      </div>

      {/* Stat cards */}
      {projection && (
        <div className="grid grid-cols-3 gap-4">
          <div className="card text-center">
            <p className="text-xs text-slate-500 uppercase">Huidig maandsalaris</p>
            <p className="text-2xl font-bold text-indigo-400 mt-1">{fmt(currentSalary)}</p>
            <p className="text-xs text-slate-500 mt-1">bruto per maand</p>
          </div>
          <div className="card text-center">
            <p className="text-xs text-slate-500 uppercase">Maximum (FWG {fwgScale})</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">{fmt(maxSalary)}</p>
            <p className="text-xs text-slate-500 mt-1">bij eindschaal</p>
          </div>
          <div className="card text-center">
            <p className="text-xs text-slate-500 uppercase">Groei potential</p>
            <p className="text-2xl font-bold text-amber-400 mt-1">+{growth}%</p>
            <p className="text-xs text-slate-500 mt-1">t/m eindschaal</p>
          </div>
        </div>
      )}

      {/* Projection chart */}
      {projection?.projection && (
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Salarisontwikkeling (10 jaar)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={projection.projection}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="year" tick={{ fill: "#64748b", fontSize: 11 }} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(v) => `€${(v / 1000).toFixed(1)}k`} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8 }}
                formatter={(v, n) => [
                  fmt(v),
                  n === "monthly_gross" ? "Bruto/maand" :
                  n === "monthly_net_estimate" ? "Netto schatting/maand" : "Jaarsalaris (incl. vakantiegeld)"
                ]}
                labelFormatter={(label) => `Jaar ${label}`}
              />
              <Line type="stepAfter" dataKey="monthly_gross" stroke="#6366f1" strokeWidth={2.5} dot={{ r: 4, fill: "#6366f1" }} name="monthly_gross" />
              <Line type="stepAfter" dataKey="monthly_net_estimate" stroke="#22c55e" strokeWidth={1.5} strokeDasharray="5 5" dot={false} name="monthly_net_estimate" />
            </LineChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2 justify-center">
            <span className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="w-6 h-0.5 bg-indigo-500 inline-block" /> Bruto maandsalaris
            </span>
            <span className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="w-6 h-0.5 bg-emerald-500 inline-block border-dashed" /> Netto schatting (~72%)
            </span>
          </div>
        </div>
      )}

      {/* Projection table */}
      {projection?.projection && (
        <div className="card p-0 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300">Jaarlijks overzicht</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-800/30">
              <tr>
                <th className="text-left px-5 py-3 text-slate-400 font-medium">Jaar</th>
                <th className="text-left px-5 py-3 text-slate-400 font-medium">Periodiek</th>
                <th className="text-right px-5 py-3 text-slate-400 font-medium">Bruto/maand</th>
                <th className="text-right px-5 py-3 text-slate-400 font-medium">Netto/maand (est.)</th>
                <th className="text-right px-5 py-3 text-slate-400 font-medium">Jaarsalaris</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {projection.projection.map((row, i) => (
                <tr key={row.year} className={i === 0 ? "bg-indigo-950/30" : "hover:bg-slate-800/20"}>
                  <td className="px-5 py-3 font-medium text-slate-200">
                    {row.year} {i === 0 && <span className="text-xs text-indigo-400 ml-1">(nu)</span>}
                  </td>
                  <td className="px-5 py-3 text-slate-400">Periodiek {row.step}</td>
                  <td className="px-5 py-3 text-right text-slate-200">{fmt(row.monthly_gross)}</td>
                  <td className="px-5 py-3 text-right text-emerald-400">{fmt(row.monthly_net_estimate)}</td>
                  <td className="px-5 py-3 text-right text-slate-300">{fmt(row.annual_gross)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit scale mode */}
      {editMode && (
        <div className="card space-y-4">
          <h3 className="text-sm font-semibold text-slate-300">Loonschalen bewerken</h3>
          <div className="flex gap-2 items-center">
            <label className="text-xs text-slate-400">Schaal:</label>
            <select className="select w-32" value={editScaleNum} onChange={(e) => { setEditScaleNum(Number(e.target.value)); loadEditScale(Number(e.target.value)); }}>
              {FWG_SCALES.map((s) => <option key={s} value={s}>FWG {s}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {editValues.map((v, i) => (
              <div key={v.step}>
                <label className="text-xs text-slate-500">Periodiek {v.step}</label>
                <input
                  className="input mt-1"
                  type="number"
                  value={v.monthly_gross}
                  onChange={(e) => {
                    const copy = [...editValues];
                    copy[i] = { ...copy[i], monthly_gross: e.target.value };
                    setEditValues(copy);
                  }}
                />
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-600">Bedragen zijn bruto maandsalaris in euro's (excl. vakantiegeld)</p>
          <div className="flex gap-2">
            <button className="btn-primary" onClick={handleSaveScale}>Schalen opslaan</button>
            <button className="btn-ghost" onClick={() => setEditMode(false)}>Annuleren</button>
          </div>
        </div>
      )}
    </div>
  );
}
