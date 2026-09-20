import { createContext, createElement, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

/**
 * The period you are looking at, shared by every page that has one.
 *
 * Pick March on the overview and the fixed-cost tab shows March too: one
 * choice, everywhere the same. A range is `{ from, to }` in `YYYY-MM` labels;
 * a single month is just a range where both are equal, so no page needs two
 * code paths.
 *
 * Kept in sessionStorage rather than localStorage on purpose: it should
 * survive a reload while you are working, but a fresh visit tomorrow should
 * open on the current month, not on whatever you were digging into last week.
 */
const STORAGE_KEY = "financials.period";

const PeriodContext = createContext(null);

const monthIndex = (label) => {
  const [year, month] = label.split("-").map(Number);
  return year * 12 + (month - 1);
};

const labelOf = (index) => {
  const year = Math.floor(index / 12);
  const month = (index % 12) + 1;
  return `${year}-${String(month).padStart(2, "0")}`;
};

const clampRange = (from, to) => (monthIndex(from) <= monthIndex(to) ? { from, to } : { from: to, to: from });

export function PeriodProvider({ children }) {
  const [options, setOptions] = useState(null);
  const [range, setRangeState] = useState(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
      return saved?.from && saved?.to ? clampRange(saved.from, saved.to) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    api.periodOptions()
      .then((result) => {
        setOptions(result);
        setRangeState((current) => current || { from: result.current, to: result.current });
      })
      .catch(() => { /* pages show their own error; the picker just stays empty */ });
  }, []);

  useEffect(() => {
    if (!range) return;
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(range));
    } catch {
      /* ignore */
    }
  }, [range]);

  const setRange = useCallback((from, to) => setRangeState(clampRange(from, to ?? from)), []);

  const value = useMemo(() => {
    if (!range) return { range: null, options, setRange, params: {} };

    const fromIndex = monthIndex(range.from);
    const toIndex = monthIndex(range.to);
    const count = toIndex - fromIndex + 1;
    const currentIndex = options ? monthIndex(options.current) : toIndex;
    const earliestIndex = options ? monthIndex(options.earliest) : fromIndex;

    return {
      range,
      options,
      count,
      single: count === 1,
      params: { from: range.from, to: range.to },
      setRange,
      /** Move the whole window by its own length: next month, or next quarter. */
      shift: (direction) => {
        const step = count * direction;
        // Never past the current month: slide the window back so it ends there.
        const to = Math.min(toIndex + step, currentIndex);
        setRangeState({ from: labelOf(to - count + 1), to: labelOf(to) });
      },
      /** Presets end at the month you are looking at, not at today — so while
          browsing March you can ask for "the three months up to March". */
      preset: (name) => {
        if (name === "current") return setRangeState({ from: options?.current ?? range.to, to: options?.current ?? range.to });
        if (name === "all") return setRangeState({ from: labelOf(earliestIndex), to: labelOf(currentIndex) });
        if (name === "year") return setRangeState({ from: `${range.to.slice(0, 4)}-01`, to: range.to });
        const months = Number(name);
        return setRangeState({ from: labelOf(toIndex - months + 1), to: range.to });
      },
    };
  }, [range, options, setRange]);

  return createElement(PeriodContext.Provider, { value }, children);
}

export function usePeriod() {
  const context = useContext(PeriodContext);
  if (!context) throw new Error("usePeriod() buiten een PeriodProvider");
  return context;
}

export const periodLabel = (label, options) =>
  options?.options?.find((o) => o.value === label)?.label ?? label;
