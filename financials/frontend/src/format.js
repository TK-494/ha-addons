// Dutch formatting throughout: € 1.234,56 and 09-08-2026.

const currency = new Intl.NumberFormat("nl-NL", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
});

const number = new Intl.NumberFormat("nl-NL", { maximumFractionDigits: 0 });

export const money = (value) => currency.format(value ?? 0);

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
  db: "Doorlopende incasso", ei: "Euro-incasso", id: "iDEAL", tb: "Telebankieren",
  cb: "Crediteurenbetaling", bv: "Bijschrijving", bg: "Bankgirobetaling",
  cc: "Creditcard", sb: "Salarisbetaling", ec: "Euro-incasso", kh: "Kashandeling",
  te: "Terugboeking", st: "Storting",
  bea: "Betaalautomaat", ovs: "Overschrijving", ide: "iDEAL", ios: "Incasso",
  ioi: "Incasso", bvz: "Bijschrijving", eic: "Euro-incasso", afb: "Afboeking",
  rti: "Retour",
};

export const bankCodeLabel = (code) => BANK_CODES[code] || code?.toUpperCase() || "";
