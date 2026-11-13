// Price display and price-filter validation for the browsing pages (Requirements 8.8, 9.5, 9.7).

/** Formats a decimal string or number such as "12.5" as "$12.50". Invalid values show "$0.00". */
export function formatPrice(price) {
  const value = typeof price === "number" ? price : Number(String(price ?? "").trim() || NaN);
  return `$${(Number.isFinite(value) ? value : 0).toFixed(2)}`;
}

function checkNumber(raw) {
  const text = String(raw ?? "").trim();
  if (text === "") return { blank: true };
  const value = Number(text);
  if (!Number.isFinite(value)) return { error: "Enter a valid number." };
  if (value < 0) return { error: "Must be 0 or more." };
  return { value };
}

/**
 * Validates the min and max price filter inputs before any request is made.
 * Blank inputs are allowed. Returns `{min?: string, max?: string}` with a message per invalid field;
 * an empty object means the filters can be sent.
 */
export function validatePriceRange(min, max) {
  const errors = {};
  const low = checkNumber(min);
  const high = checkNumber(max);
  if (low.error) errors.min = low.error;
  if (high.error) errors.max = high.error;
  if (!errors.min && !errors.max && low.value !== undefined && high.value !== undefined && low.value > high.value) {
    errors.max = "Maximum must be at least the minimum.";
  }
  return errors;
}

/** True when `validatePriceRange` found no problems. */
export const isPriceRangeValid = (errors) => !errors.min && !errors.max;
