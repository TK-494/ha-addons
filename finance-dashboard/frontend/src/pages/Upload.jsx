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
        <p className="text-slate-500 text-sm">Upload een CSV export van Rabobank of ASN Bank — het formaat wordt automatisch herkend</p>
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
            <p className="text-slate-700 text-xs mt-3">Ondersteunt: Rabobank en ASN Bank CSV</p>
          </>
        )}
      </div>

      {/* Result */}
      {result && (
        <div className="card border-emerald-800 bg-emerald-950/20">
          <div className="flex items-center gap-3">
            <span className="text-2xl">✅</span>
            <div>
              <p className="text-sm font-semibold text-emerald-400">
                Import geslaagd
                {result.bank && (
                  <span className="ml-2 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-300 border border-emerald-800/60 align-middle">
                    {result.bank === "asn" ? "ASN Bank" : "Rabobank"}
                  </span>
                )}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                {result.imported} nieuwe transacties geïmporteerd · {result.skipped} duplicaten overgeslagen
                {typeof result.transfers_flagged_in_batch === "number" && result.transfers_flagged_in_batch > 0 && (
                  <> · {result.transfers_flagged_in_batch} overboekingen tussen eigen rekeningen</>
                )}
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
        <h3 className="text-sm font-semibold text-slate-300">Hoe exporteer je een CSV?</h3>

        <div className="space-y-2">
          <p className="text-xs text-indigo-400 uppercase tracking-wide font-semibold">Rabobank</p>
          <ol className="space-y-1.5 text-sm text-slate-400">
            <li className="flex gap-2"><span className="text-indigo-400 font-medium shrink-0">1.</span>Log in op Mijn Rabobank</li>
            <li className="flex gap-2"><span className="text-indigo-400 font-medium shrink-0">2.</span>Ga naar je betaalrekening → "Overzicht"</li>
            <li className="flex gap-2"><span className="text-indigo-400 font-medium shrink-0">3.</span>Klik op "Downloaden" en kies "CSV" als formaat</li>
          </ol>
        </div>

        <div className="space-y-2">
          <p className="text-xs text-amber-400 uppercase tracking-wide font-semibold">ASN Bank</p>
          <ol className="space-y-1.5 text-sm text-slate-400">
            <li className="flex gap-2"><span className="text-amber-400 font-medium shrink-0">1.</span>Log in op Mijn ASN</li>
            <li className="flex gap-2"><span className="text-amber-400 font-medium shrink-0">2.</span>Ga naar je rekening → "Afschriften" / "Transacties downloaden"</li>
            <li className="flex gap-2"><span className="text-amber-400 font-medium shrink-0">3.</span>Kies "CSV" en de gewenste periode</li>
          </ol>
        </div>

        <p className="text-xs text-slate-600 pt-1">
          Je data blijft volledig lokaal — er wordt niets naar externe servers gestuurd. Heb je rekeningen bij meerdere banken? Importeer ze allemaal; overboekingen tussen je eigen rekeningen worden automatisch als zodanig gemarkeerd.
        </p>
      </div>
    </div>
  );
}
