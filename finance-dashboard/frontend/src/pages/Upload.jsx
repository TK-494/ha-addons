import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { uploadBankStatement } from "../api";

export default function Upload() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);

  const onDrop = useCallback(async (accepted) => {
    if (!accepted.length) return;
    setUploading(true);
    setResult(null);
    setError(null);
    try {
      const res = await uploadBankStatement(accepted[0]);
      setResult(res);
    } catch (e) {
      setError(e.response?.data?.detail || "Er is een fout opgetreden bij het importeren.");
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    multiple: false,
  });

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div>
        <h2 className="text-xl font-bold">Bankafschrift importeren</h2>
        <p className="text-slate-500 text-sm">Upload een Rabobank CSV export om transacties te importeren</p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          isDragActive
            ? "border-indigo-500 bg-indigo-950/30"
            : "border-slate-700 hover:border-slate-600 hover:bg-slate-900/50"
        }`}
      >
        <input {...getInputProps()} />
        <div className="text-4xl mb-3">📄</div>
        {uploading ? (
          <p className="text-slate-400 text-sm">Bestand wordt verwerkt...</p>
        ) : isDragActive ? (
          <p className="text-indigo-400 text-sm">Laat het bestand los om te uploaden</p>
        ) : (
          <>
            <p className="text-slate-300 text-sm font-medium">Sleep een CSV-bestand hierheen</p>
            <p className="text-slate-600 text-xs mt-1">of klik om een bestand te selecteren</p>
            <p className="text-slate-700 text-xs mt-3">Ondersteunt: Rabobank CSV (nieuw formaat)</p>
          </>
        )}
      </div>

      {/* Result */}
      {result && (
        <div className="card border-emerald-800 bg-emerald-950/20">
          <div className="flex items-center gap-3">
            <span className="text-2xl">✅</span>
            <div>
              <p className="text-sm font-semibold text-emerald-400">Import geslaagd</p>
              <p className="text-xs text-slate-400 mt-0.5">
                {result.imported} nieuwe transacties geïmporteerd · {result.skipped} duplicaten overgeslagen
              </p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="card border-red-800 bg-red-950/20">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <p className="text-sm font-semibold text-red-400">Import mislukt</p>
              <p className="text-xs text-slate-400 mt-0.5">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Instructions */}
      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-slate-300">Hoe exporteer je een Rabobank CSV?</h3>
        <ol className="space-y-2 text-sm text-slate-400">
          <li className="flex gap-2"><span className="text-indigo-400 font-medium shrink-0">1.</span>Log in op Mijn Rabobank</li>
          <li className="flex gap-2"><span className="text-indigo-400 font-medium shrink-0">2.</span>Ga naar je betaalrekening → "Overzicht"</li>
          <li className="flex gap-2"><span className="text-indigo-400 font-medium shrink-0">3.</span>Klik op "Downloaden" of het download-icoon</li>
          <li className="flex gap-2"><span className="text-indigo-400 font-medium shrink-0">4.</span>Kies "CSV" als bestandsformaat en selecteer de gewenste periode</li>
          <li className="flex gap-2"><span className="text-indigo-400 font-medium shrink-0">5.</span>Download het bestand en upload het hier</li>
        </ol>
        <p className="text-xs text-slate-600 pt-1">
          Je data blijft volledig lokaal — er wordt niets naar externe servers gestuurd.
        </p>
      </div>
    </div>
  );
}
