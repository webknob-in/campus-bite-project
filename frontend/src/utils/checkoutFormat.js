// Checkout helpers: money formatting and form validators (Requirements 10.2, 11.8, 11.9, 11.12).
// Rules mirror the backend `OrderCreate` / `MockPaymentIn` schemas in the design document.
// Every validator returns an error message, or `undefined` when the value is valid.
// Card data is only validated here; nothing in this module stores or logs it.

export const ADDRESS_MIN = 5;
export const ADDRESS_MAX = 300;
export const HOLDER_MIN = 2;
export const HOLDER_MAX = 100;

const PHONE_PATTERN = /^[0-9+\-\s]{7,20}$/;
const CARD_NUMBER_PATTERN = /^\d{16}$/;
const EXPIRY_PATTERN = /^(0[1-9]|1[0-2])\/(\d{2})$/;
const CVV_PATTERN = /^\d{3}$/;

// ---- Money ----

/** Converts a price (number or decimal string) to integer cents. Invalid values count as 0. */
export function toCents(price) {
  const value =
    typeof price === "number" ? price : typeof price === "string" && price.trim() !== "" ? Number(price) : NaN;
  return Number.isFinite(value) ? Math.round(value * 100) : 0;
}

/** Formats a price (number or decimal string) with two decimals, e.g. `$12.50`. */
export function formatPrice(price) {
  return `$${(toCents(price) / 100).toFixed(2)}`;
}

/** Line total (price x quantity) in dollars, computed in integer cents. */
export function lineTotal(price, quantity) {
  return (toCents(price) * quantity) / 100;
}

// ---- Normalizers ----

/** Removes spaces from a card number so it can be validated and sent. */
export const normalizeCardNumber = (raw) => String(raw ?? "").replace(/\s+/g, "");

// ---- Delivery validators ----

export function validateAddress(raw) {
  const length = String(raw ?? "").trim().length;
  if (length === 0) return "Delivery address is required.";
  if (length < ADDRESS_MIN) return `Delivery address must be at least ${ADDRESS_MIN} characters.`;
  if (length > ADDRESS_MAX) return `Delivery address must be at most ${ADDRESS_MAX} characters.`;
  return undefined;
}

export function validatePhone(raw) {
  const value = String(raw ?? "").trim();
  if (!value) return "Phone number is required.";
  if (!PHONE_PATTERN.test(value)) return "Enter 7 to 20 digits; spaces, + and - are allowed.";
  return undefined;
}

// ---- Card validators ----

export function validateCardHolder(raw) {
  const length = String(raw ?? "").trim().length;
  if (length === 0) return "Card holder name is required.";
  if (length < HOLDER_MIN) return `Card holder name must be at least ${HOLDER_MIN} characters.`;
  if (length > HOLDER_MAX) return `Card holder name must be at most ${HOLDER_MAX} characters.`;
  return undefined;
}

/** Spaces are allowed in the input and ignored; the remaining value must be exactly 16 digits. */
export function validateCardNumber(raw) {
  const value = normalizeCardNumber(raw);
  if (!value) return "Card number is required.";
  if (!CARD_NUMBER_PATTERN.test(value)) return "Card number must be exactly 16 digits.";
  return undefined;
}

/**
 * `MM/YY` with month 01-12. The card is valid through the end of its expiry month,
 * so the current month is accepted and earlier months are rejected.
 * @param {string} raw
 * @param {Date} [now] injectable for tests
 */
export function validateExpiry(raw, now = new Date()) {
  const value = String(raw ?? "").trim();
  if (!value) return "Expiry date is required.";
  const match = EXPIRY_PATTERN.exec(value);
  if (!match) return "Use the MM/YY format with a month from 01 to 12.";
  const month = Number(match[1]);
  const year = 2000 + Number(match[2]);
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  if (year < currentYear || (year === currentYear && month < currentMonth)) {
    return "This card has expired.";
  }
  return undefined;
}

export function validateCvv(raw) {
  const value = String(raw ?? "");
  if (!value) return "CVV is required.";
  if (!CVV_PATTERN.test(value)) return "CVV must be exactly 3 digits.";
  return undefined;
}

/**
 * Validates the whole checkout form. Returns an object of `{field: message}` for invalid fields.
 * @param {{address: string, phone: string, cardHolder: string, cardNumber: string, expiry: string, cvv: string}} values
 */
export function validateCheckout(values, now = new Date()) {
  const checks = {
    address: validateAddress(values.address),
    phone: validatePhone(values.phone),
    cardHolder: validateCardHolder(values.cardHolder),
    cardNumber: validateCardNumber(values.cardNumber),
    expiry: validateExpiry(values.expiry, now),
    cvv: validateCvv(values.cvv),
  };
  return Object.fromEntries(Object.entries(checks).filter(([, message]) => message));
}

/** Builds the `POST /orders` body. Card number has its spaces removed. */
export function buildOrderPayload(items, values) {
  return {
    items: items.map((line) => ({ menu_item_id: line.id, quantity: line.quantity })),
    delivery_address: values.address.trim(),
    delivery_phone: values.phone.trim(),
    payment: {
      card_holder: values.cardHolder.trim(),
      card_number: normalizeCardNumber(values.cardNumber),
      expiry: values.expiry.trim(),
      cvv: values.cvv,
    },
  };
}
