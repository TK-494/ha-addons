import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api.js";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits.jsx";
import { money } from "../format.js";

export default function CategoryDetail() {
  const { id } = useParams();
  const [months, setMonths] = useState(12);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    api.categoryDetail(id, months).then(setData).catch((e) => setError(e.message));
  }, [id, months]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return <Spinner />;

  return (
    <>
      <PageHeader
        title={data.category.name}
        subtitle={`${money(data.total)} in ${months} maanden · gemiddeld ${money(data.average)} per actieve maand`}
      >
        <select className="input w-auto" value={months} onChange={(e) => setMonths(Number(e.target.value))}>
          {[6, 12, 24, 36].map((m) => <option key={m} value={m}>{m} maanden</option>)}
        </select>
        <Link className="btn-ghost" to={`/transacties?category_id=${id}`}>Transacties tonen</Link>
      </PageHeader>

      <section className="card mb-4">
        <h3 className="mb-3 font-semibold">Verloop</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data.trend}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="label" fontSize={11} />
            <YAxis fontSize={11} />
            <Tooltip formatter={(v) => money(v)} />
            <Bar dataKey="amount" name={data.category.name} fill={data.category.color} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>

      <section className="card">
        <h3 className="mb-3 font-semibold">Grootste tegenpartijen</h3>
        {data.merchants.length === 0 ? (
          <Empty>Nog geen transacties in deze categorie.</Empty>
        ) : (
          <ul className="space-y-1 text-sm">
            {data.merchants.map((m) => (
              <li key={m.name} className="flex justify-between gap-3">
                <Link className="truncate hover:underline" to={`/transacties?search=${encodeURIComponent(m.name.slice(0, 24))}`}>
                  {m.name}
                </Link>
                <span className="whitespace-nowrap tabular-nums">
                  {money(m.amount)} <span className="text-xs text-slate-500">{m.transactions}×</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
