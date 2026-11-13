// Cart reducer and helpers (Requirements 10.1-10.4, 10.6).
//
// State shape: { restaurantId, restaurantName, items: [{ id, name, price, quantity }] }.
// - All lines belong to one restaurant. An empty cart is always `initialCart`.
// - Quantities are whole numbers from 1 to 99.
// - `price` is stored exactly as received (the API sends decimal strings such as "12.50").
//   Money math runs in integer cents so totals never drift.
// Everything here is pure and deterministic.

export const MIN_QUANTITY = 1;
export const MAX_QUANTITY = 99;

export const initialCart = Object.freeze({ restaurantId: null, restaurantName: null, items: Object.freeze([]) });

function newLine(item) {
  return { id: item.id, name: item.name, price: item.price, quantity: 1 };
}

export function cartReducer(state, action) {
  switch (action.type) {
    case "ADD": {
      // The caller confirms a restaurant switch first; a mismatched ADD is ignored.
      const { item, restaurant } = action;
      if (state.restaurantId !== null && state.restaurantId !== restaurant.id) return state;
      const existing = state.items.find((l) => l.id === item.id);
      const items = existing
        ? state.items.map((l) => (l.id === item.id ? { ...l, quantity: Math.min(MAX_QUANTITY, l.quantity + 1) } : l))
        : [...state.items, newLine(item)];
      return { restaurantId: restaurant.id, restaurantName: restaurant.name, items };
    }
    case "REPLACE": // confirmed restaurant switch
      return {
        restaurantId: action.restaurant.id,
        restaurantName: action.restaurant.name,
        items: [newLine(action.item)],
      };
    case "UPDATE": {
      const q = action.quantity;
      if (q <= 0) return cartReducer(state, { type: "REMOVE", id: action.id });
      if (!Number.isInteger(q) || q > MAX_QUANTITY) return state;
      if (!state.items.some((l) => l.id === action.id)) return state;
      return { ...state, items: state.items.map((l) => (l.id === action.id ? { ...l, quantity: q } : l)) };
    }
    case "REMOVE": {
      const items = state.items.filter((l) => l.id !== action.id);
      return items.length ? { ...state, items } : initialCart;
    }
    case "CLEAR":
      return initialCart;
    default:
      return state;
  }
}

/** Converts a price (number or decimal string) to integer cents. Invalid values count as 0. */
function toCents(price) {
  const value = typeof price === "number" ? price : typeof price === "string" && price.trim() !== "" ? Number(price) : NaN;
  return Number.isFinite(value) ? Math.round(value * 100) : 0;
}

/** Total number of dishes in the cart (sum of quantities). */
export const cartCount = (s) => s.items.reduce((n, l) => n + l.quantity, 0);

/** Sum of price x quantity, computed in integer cents and returned as a number with 2 decimals. */
export const cartSubtotal = (s) => s.items.reduce((cents, l) => cents + toCents(l.price) * l.quantity, 0) / 100;

export const serializeCart = (s) => JSON.stringify(s);

const isId = (v) => (typeof v === "string" && v !== "") || (typeof v === "number" && Number.isFinite(v));
const isPrice = (v) =>
  (typeof v === "number" && Number.isFinite(v) && v >= 0) ||
  (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v)) && Number(v) >= 0);

/**
 * Parses a stored cart. Corrupt JSON or malformed shapes give an empty cart; malformed lines are
 * dropped, duplicate ids keep the first line, and quantities are floored and capped at 99.
 */
export function deserializeCart(raw) {
  if (!raw) return initialCart;
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return initialCart;
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) return initialCart;
  if (!isId(data.restaurantId) || !Array.isArray(data.items)) return initialCart;

  const seen = new Set();
  const items = [];
  for (const line of data.items) {
    if (!line || typeof line !== "object" || Array.isArray(line)) continue;
    if (!isId(line.id) || typeof line.name !== "string" || !isPrice(line.price)) continue;
    if (typeof line.quantity !== "number" || !Number.isFinite(line.quantity)) continue;
    const quantity = Math.min(MAX_QUANTITY, Math.floor(line.quantity));
    if (quantity < MIN_QUANTITY || seen.has(line.id)) continue;
    seen.add(line.id);
    items.push({ id: line.id, name: line.name, price: line.price, quantity });
  }
  if (items.length === 0) return initialCart;
  return {
    restaurantId: data.restaurantId,
    restaurantName: typeof data.restaurantName === "string" ? data.restaurantName : null,
    items,
  };
}
