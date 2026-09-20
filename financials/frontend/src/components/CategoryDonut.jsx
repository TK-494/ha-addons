import { Link, useNavigate } from "react-router-dom";
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
/**
 * Where a click lands: the transactions of that category, in exactly the
 * period the chart shows. `range.end` is exclusive (a period boundary); the
 * transaction filter's `date_to` is inclusive, hence the day before.
 */
export function transactionsLink(row, range) {
  const params = new URLSearchParams();
  if (row.category_id) params.set("category_id", row.category_id);
  else params.set("uncategorised", "1");
  if (range?.start) params.set("date_from", range.start.slice(0, 10));
  if (range?.end) {
    const end = new Date(...range.end.slice(0, 10).split("-").map((v, i) => Number(v) - (i === 1 ? 1 : 0)));
    end.setDate(end.getDate() - 1);
    const pad = (n) => String(n).padStart(2, "0");
    params.set("date_to", `${end.getFullYear()}-${pad(end.getMonth() + 1)}-${pad(end.getDate())}`);
  }
  return `/transacties?${params}`;
}

export default function CategoryDonut({
  rows, title, empty = "Niets in deze periode.", height = 260, slices = 8, legend = 8, range,
}) {
  const navigate = useNavigate();
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
    ? [...head, { name: `overig (${rest.length})`, amount: restTotal, color: "#cbd5e1", rest: true }]
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
          <Pie
            data={chart}
            dataKey="amount"
            nameKey="name"
            innerRadius="52%"
            outerRadius="82%"
            onClick={(entry) => {
              // Recharts hands the sector; the datum sits on `payload`.
              const row = entry?.payload ?? entry;
              if (row && !row.rest) navigate(transactionsLink(row, range));
            }}
            className="cursor-pointer"
          >
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
              <Link
                className="truncate hover:underline"
                to={transactionsLink(row, range)}
                title="Alle transacties in deze periode"
              >
                {row.name}
              </Link>
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
