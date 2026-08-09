import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { money, shortDate } from "../format.js";

/** Everything ever paid to one merchant: total, frequency, first and last. */
export default function Counterparty() {
  const [searchParams, setSearchParams] = useSearchParams();
  const name = searchParams.get("name") || "";
  const [query, setQuery] = useState(name);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (name.trim().length < 2) { setData(null); return; }
    setData(null);
    api.counterparty(name).then(setData).catch((e) => setError(e.message));
  }, [name]);

  return (
    <>
      <PageHeader title="Tegenpartij" subtitle="Alles wat je ooit aan één partij betaald hebt" />

      {error && <Alert kind="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <form
        className="card mb-4 flex gap-2"
        onSubmit={(e) => { e.preventDefault(); setSearchParams({ name: query }); }}
      >
        <input
          className="input"
          placeholder="Naam van de winkel of incassant"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn-primary" disabled={query.trim().length < 2}>Zoeken</button>
      </form>

      {!name ? (
        <Empty>Vul een naam in, of klik een tegenpartij aan op het overzicht.</Empty>
      ) : !data ? (
        <Spinner />
      ) : data.transactions === 0 ? (
        <Empty>Niets gevonden voor “{name}”.</Empty>
      ) : (
        <>
          <section className="mb-4 grid gap-3 sm:grid-cols-4">
            <Stat label="Totaal" value={money(data.total)} />
            <Stat label="Transacties" value={data.transactions} />
            <Stat label="Eerste" value={shortDate(data.first_seen)} />
            <Stat label="Laatste" value={shortDate(data.last_seen)} />
          </section>

          <section className="card mb-4">
            <h3 className="mb-3 font-semibold">Per maand</h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={data.history}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="label" fontSize={11} />
                <YAxis fontSize={11} />
                <Tooltip formatter={(v) => money(v)} />
                <Bar dataKey="amount" name={data.name} fill="#0ea5e9" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </section>

          <Link className="btn-ghost" to={`/transacties?search=${encodeURIComponent(name)}`}>
            Transacties tonen
          </Link>
        </>
      )}
    </>
  );
}

function Stat({ label, value }) {
  return (
    <div className="card">
      <p className="label">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}
