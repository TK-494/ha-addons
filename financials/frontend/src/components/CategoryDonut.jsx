import { Link } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Empty } from "./Bits.jsx";
import { money } from "../format.js";

/**
 * One donut plus its legend.
 *
 * Shared so the overview and the two expense pages stay visually comparable —
 * a category that is blue in one chart and green in another makes the reader
 * do work the chart is supposed to do for them.
 *
 * Only the eight largest slices are drawn; beyond that the ring turns into
 * confetti. The remainder is folded into one "overig" slice so the total the
 * ring represents still matches the number above it.
 */
export default function CategoryDonut({
  rows, title, empty = "Niets in deze periode.", height = 260, slices = 8, legend = 8,
}) {
  const total = (rows || []).reduce((sum, r) => sum + r.amount, 0);

  if (!rows || rows.length === 0) {
    return (
      <div>
        {title && <h3 className="mb-3 font-semibold">{title}</h3>}
        <Empty>{empty}</Empty>
      </div>
    );
  }

  const head = rows.slice(0, slices);
  const rest = rows.slice(slices);
  const restTotal = rest.reduce((sum, r) => sum + r.amount, 0);
  const chart = restTotal > 0
    ? [...head, { name: `overig (${rest.length})`, amount: restTotal, color: "#cbd5e1" }]
    : head;

  return (
    <div>
      {title && (
        <div className="mb-2 flex items-baseline justify-between gap-2">
          <h3 className="font-semibold">{title}</h3>
          <span className="text-sm tabular-nums text-slate-500 dark:text-slate-400">{money(total)}</span>
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie data={chart} dataKey="amount" nameKey="name" innerRadius="52%" outerRadius="82%">
            {chart.map((row) => <Cell key={row.name} fill={row.color} />)}
          </Pie>
          <Tooltip formatter={(value, name) => [money(value), name]} />
        </PieChart>
      </ResponsiveContainer>
      <ul className="mt-2 space-y-1 text-sm">
        {rows.slice(0, legend).map((row) => (
          <li key={row.name} className="flex items-baseline justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: row.color }} />
              {row.category_id ? (
                <Link className="truncate hover:underline" to={`/categorie/${row.category_id}`}>{row.name}</Link>
              ) : (
                <span className="truncate">{row.name}</span>
              )}
            </span>
            <span className="whitespace-nowrap tabular-nums">
              {money(row.amount)}
              <span className="ml-1 text-xs text-slate-500">
                {row.share ?? (total ? Math.round((100 * row.amount) / total) : 0)}%
              </span>
            </span>
          </li>
        ))}
      </ul>
      {rows.length > legend && (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          en nog {rows.length - legend} categorieën, samen {money(restTotal)}.
        </p>
      )}
    </div>
  );
}
