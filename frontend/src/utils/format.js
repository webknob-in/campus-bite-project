// Display formatting for money and dates. All functions tolerate null and invalid input and
// return a placeholder instead of throwing.

export const CURRENCY_SYMBOL = "₹";
export const PLACEHOLDER = "—";

/**
 * Money for display. Accepts a decimal string from the Backend ("12.5") or a number and
 * returns e.g. "₹12.50". Null, empty, and non-numeric input give the placeholder.
 */
export function formatCurrency(value) {
  if (value === null || value === undefined) return PLACEHOLDER;
  if (typeof value === "string" && value.trim() === "") return PLACEHOLDER;
  const amount = typeof value === "number" ? value : Number(String(value).trim());
  if (!Number.isFinite(amount)) return PLACEHOLDER;
  const sign = amount < 0 ? "-" : "";
  const body = Math.abs(amount).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${sign}${CURRENCY_SYMBOL}${body}`;
}

function toDate(iso) {
  if (iso === null || iso === undefined || iso === "") return null;
  const date = iso instanceof Date ? iso : new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Locale date, e.g. "12 Mar 2025". Invalid input gives the placeholder. */
export function formatDate(iso) {
  const date = toDate(iso);
  if (!date) return PLACEHOLDER;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** Locale date and time, e.g. "12 Mar 2025, 14:05". Invalid input gives the placeholder. */
export function formatDateTime(iso) {
  const date = toDate(iso);
  if (!date) return PLACEHOLDER;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
