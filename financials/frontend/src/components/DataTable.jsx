import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Column widths the user can drag, remembered per table.
 *
 * A fixed layout is what makes dragging work at all — with `table-auto` the
 * browser overrules any width you set the moment content does not fit. The
 * trade-off is that content must be allowed to wrap instead of being clipped,
 * otherwise widening a column would not reveal anything.
 */
export function useColumnWidths(storageKey, defaults, minimums = {}) {
  // A fixed layout does not clip: content wider than its column paints straight
  // over the neighbour. Text wraps and survives that, but a row of buttons with
  // `whitespace-nowrap` cannot, so a column holding those needs a floor — and
  // the floor has to apply to widths saved before it existed, or the layout
  // that was already too narrow stays too narrow forever.
  const floor = useCallback(
    (value) => Object.fromEntries(
      Object.entries(value).map(([key, width]) => [key, Math.max(minimums[key] ?? 52, width)])
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [storageKey]
  );

  const [widths, setWidths] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
      // Merge rather than replace: a saved layout from an older version must
      // not hide a column that has been added since.
      return floor(saved ? { ...defaults, ...saved } : defaults);
    } catch {
      return floor(defaults);
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(widths));
    } catch {
      /* private mode, quota — the table still works, it just forgets */
    }
  }, [storageKey, widths]);

  const drag = useRef(null);

  const startResize = useCallback((key) => (event) => {
    event.preventDefault();
    event.stopPropagation();
    drag.current = { key, startX: event.clientX, startWidth: widths[key] };

    const onMove = (move) => {
      if (!drag.current) return;
      const min = minimums[drag.current.key] ?? 52;
      const next = Math.max(min, drag.current.startWidth + (move.clientX - drag.current.startX));
      setWidths((current) => ({ ...current, [drag.current.key]: next }));
    };
    const onUp = () => {
      drag.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [widths]);

  const reset = useCallback(() => setWidths(floor(defaults)), [defaults, floor]);

  return { widths, startResize, reset };
}

/**
 * A header cell that can sort and can be dragged wider.
 *
 * Clicking the label sorts; clicking again flips direction. The drag handle
 * sits in its own element so a resize never registers as a sort.
 */
export function Th({
  label, sortKey, sort, desc, onSort, align = "left", onResize, title,
}) {
  const active = sortKey && sort === sortKey;
  const arrow = active ? (desc ? "▾" : "▴") : "";

  return (
    <th className="th relative select-none" title={title}>
      <div className={`flex items-center gap-1 ${align === "right" ? "justify-end" : ""}`}>
        {sortKey ? (
          <button
            className="flex items-center gap-1 hover:text-slate-900 dark:hover:text-slate-100"
            onClick={() => onSort(sortKey)}
            title={active ? "Klik om de volgorde om te draaien" : `Sorteren op ${label.toLowerCase()}`}
          >
            <span>{label}</span>
            <span className={`text-[10px] ${active ? "" : "opacity-0 group-hover:opacity-40"}`}>
              {arrow || "▴"}
            </span>
          </button>
        ) : (
          <span>{label}</span>
        )}
      </div>
      {onResize && (
        <span
          onMouseDown={onResize}
          onDoubleClick={(e) => e.stopPropagation()}
          title="Sleep om de kolom breder te maken"
          className="absolute right-0 top-0 h-full w-2 cursor-col-resize border-r border-transparent hover:border-sky-400"
        />
      )}
    </th>
  );
}
