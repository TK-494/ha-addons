// Dutch formatting throughout: € 1.234,56 and 09-08-2026.

const currency = new Intl.NumberFormat("nl-NL", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
});

const number = new Intl.NumberFormat("nl-NL", { maximumFractionDigits: 0 });

/**
 * Privacy mode.
 *
 * A module flag rather than a context: every amount in the app already goes
 * through `money()`, so masking there covers the tables, the tooltips, the
 * chart legends and the KPI tiles in one move — instead of threading a prop
 * through twenty components and missing three of them.
 *
 * Toggling it re-renders from App, and these functions are read during render,
 * so the whole tree follows.
 */
let hidden = false;

export function setPrivate(value) {
  hidden = Boolean(value);
}

export const isPrivate = () => hidden;

const MASK = "€ ••••";

export const money = (value) => (hidden ? MASK : currency.format(value ?? 0));

/** Chart axes: same masking, but short enough to fit a tick label. */
export const axisMoney = (value) =>
  hidden ? "•••" : `€${Math.round((value ?? 0) / 100) / 10}k`;

/**
 * Account numbers identify a person as surely as an amount reveals a salary,
 * so privacy mode masks them too — keeping the last four digits, which is
 * enough to tell two accounts apart while demonstrating.
 *
 * Only IBAN-shaped tokens are touched, in place: an account you named
 * "Boodschappen" is not a secret and stays readable.
 */
const IBAN = /\b[A-Z]{2}\d{2}[A-Z0-9]{8,26}\b/g;

export function maskAccount(text) {
  if (!hidden || !text) return text;
  return String(text).replace(IBAN, (match) => `••••${match.slice(-4)}`);
}

export const count = (value) => number.format(value ?? 0);

export function shortDate(iso) {
  if (!iso) return "";
  const [year, month, day] = iso.slice(0, 10).split("-");
  return `${day}-${month}-${year}`;
}

export function dateTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("nl-NL", { dateStyle: "short", timeStyle: "short" });
}

export function bytes(value) {
  if (!value) return "0 B";
  const units = ["B", "kB", "MB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export const amountClass = (value) =>
  value < 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400";

// Dutch labels for the bank transaction-type codes. Rabobank and ASN both
// carry one, and it classifies a transaction far more reliably than keywords.
export const BANK_CODES = {
  bc: "Betaalautomaat", ba: "Betaalautomaat", ga: "Geldautomaat", gb: "Geldautomaat",
  // `db` is "diverse boeking" (bank charges, internal bookings) — not a direct
  // debit, despite how it reads. Real direct debits are `ei`.
  db: "Diverse boeking", ei: "Euro-incasso", id: "iDEAL", tb: "Telebankieren",
  cb: "Crediteurenbetaling", bv: "Bijschrijving", bg: "Bankgirobetaling",
  cc: "Creditcard", sb: "Salarisbetaling", ec: "Euro-incasso", kh: "Kashandeling",
  te: "Terugboeking", st: "Storting",
  bea: "Betaalautomaat", ovs: "Overschrijving", ide: "iDEAL", ios: "Incasso",
  ioi: "Incasso", bvz: "Bijschrijving", eic: "Euro-incasso", afb: "Afboeking",
  rti: "Retour",
};

export const bankCodeLabel = (code) => BANK_CODES[code] || code?.toUpperCase() || "";
