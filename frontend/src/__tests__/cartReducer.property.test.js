import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { cartReducer, initialCart, MAX_QUANTITY } from "../context/cartReducer";

// Feature: campusbite-platform, Property 8: Cart reducer matches model
// Validates: Requirements 10.1, 10.2, 10.3, 10.4

// Fixed catalogue so the same dish id always has the same name and two-decimal price string.
const DISHES = [
  { id: "d1", name: "Paneer Roll", price: "45.00" },
  { id: "d2", name: "Veg Burger", price: "60.50" },
  { id: "d3", name: "Cold Coffee", price: "35.25" },
  { id: "d4", name: "Masala Dosa", price: "70.00" },
];
const RESTAURANTS = [
  { id: "r1", name: "Campus Cafe" },
  { id: "r2", name: "Food Court" },
];

const dishArb = fc.constantFrom(...DISHES);
const restaurantArb = fc.constantFrom(...RESTAURANTS);
const idArb = fc.constantFrom(...DISHES.map((d) => d.id), "missing");

// Quantities cover removal (<= 0), valid 1..99, over the cap, and non-integers.
const quantityArb = fc.oneof(
  fc.integer({ min: -3, max: 0 }),
  fc.integer({ min: 1, max: 99 }),
  fc.integer({ min: 100, max: 120 }),
  fc.double({ min: -5, max: 120, noNaN: true }),
  fc.constantFrom(1, 99, 100, 0),
);

const actionArb = fc.oneof(
  { weight: 5, arbitrary: fc.record({ type: fc.constant("ADD"), item: dishArb, restaurant: restaurantArb }) },
  { weight: 1, arbitrary: fc.record({ type: fc.constant("REPLACE"), item: dishArb, restaurant: restaurantArb }) },
  { weight: 3, arbitrary: fc.record({ type: fc.constant("UPDATE"), id: idArb, quantity: quantityArb }) },
  { weight: 2, arbitrary: fc.record({ type: fc.constant("REMOVE"), id: idArb }) },
  { weight: 1, arbitrary: fc.constant({ type: "CLEAR" }) },
);

// Independent reference model: a Map of dish id -> line (insertion order = display order).
function newModel() {
  return { restaurant: null, lines: new Map() };
}

function modelApply(model, action) {
  const next = { restaurant: model.restaurant, lines: new Map(model.lines) };
  const removeLine = (id) => {
    next.lines.delete(id);
    if (next.lines.size === 0) next.restaurant = null;
  };

  switch (action.type) {
    case "ADD": {
      if (model.restaurant !== null && model.restaurant.id !== action.restaurant.id) return model;
      next.restaurant = { id: action.restaurant.id, name: action.restaurant.name };
      const line = next.lines.get(action.item.id);
      if (line) {
        next.lines.set(action.item.id, { ...line, quantity: Math.min(MAX_QUANTITY, line.quantity + 1) });
      } else {
        next.lines.set(action.item.id, { name: action.item.name, price: action.item.price, quantity: 1 });
      }
      return next;
    }
    case "REPLACE":
      return {
        restaurant: { id: action.restaurant.id, name: action.restaurant.name },
        lines: new Map([[action.item.id, { name: action.item.name, price: action.item.price, quantity: 1 }]]),
      };
    case "UPDATE": {
      const q = action.quantity;
      if (q <= 0) {
        removeLine(action.id);
        return next;
      }
      if (!Number.isInteger(q) || q > MAX_QUANTITY) return model;
      const line = next.lines.get(action.id);
      if (line) next.lines.set(action.id, { ...line, quantity: q });
      return next;
    }
    case "REMOVE":
      removeLine(action.id);
      return next;
    case "CLEAR":
      return newModel();
    default:
      return model;
  }
}

function modelToState(model) {
  return {
    restaurantId: model.restaurant ? model.restaurant.id : null,
    restaurantName: model.restaurant ? model.restaurant.name : null,
    items: [...model.lines].map(([id, l]) => ({ id, name: l.name, price: l.price, quantity: l.quantity })),
  };
}

describe("cartReducer property: matches reference model", () => {
  it("equals the model after every action in a random sequence", () => {
    fc.assert(
      fc.property(fc.array(actionArb, { maxLength: 60 }), (actions) => {
        let state = initialCart;
        let model = newModel();
        for (const action of actions) {
          state = cartReducer(state, action);
          model = modelApply(model, action);
          const expected = modelToState(model);

          expect(state).toEqual(expected);
          // Invariants: one restaurant, unique ids, quantities in 1..99, empty cart is the initial cart.
          expect(new Set(state.items.map((l) => l.id)).size).toBe(state.items.length);
          for (const line of state.items) {
            expect(Number.isInteger(line.quantity)).toBe(true);
            expect(line.quantity).toBeGreaterThanOrEqual(1);
            expect(line.quantity).toBeLessThanOrEqual(MAX_QUANTITY);
          }
          if (state.items.length === 0) expect(state).toBe(initialCart);
        }
        // The shared initial cart is never mutated.
        expect(initialCart).toEqual({ restaurantId: null, restaurantName: null, items: [] });
      }),
      { numRuns: 200 },
    );
  });
});

describe("cartReducer examples", () => {
  const [d1, d2] = DISHES;
  const [r1, r2] = RESTAURANTS;

  it("ADD from another restaurant leaves the cart unchanged; REPLACE swaps it", () => {
    const s1 = cartReducer(initialCart, { type: "ADD", item: d1, restaurant: r1 });
    expect(cartReducer(s1, { type: "ADD", item: d2, restaurant: r2 })).toBe(s1);
    const s2 = cartReducer(s1, { type: "REPLACE", item: d2, restaurant: r2 });
    expect(s2).toEqual({
      restaurantId: "r2",
      restaurantName: "Food Court",
      items: [{ id: "d2", name: "Veg Burger", price: "60.50", quantity: 1 }],
    });
  });

  it("quantity bounds: 99 accepted, 100 and fractions ignored, 0 removes", () => {
    const s1 = cartReducer(initialCart, { type: "ADD", item: d1, restaurant: r1 });
    const s99 = cartReducer(s1, { type: "UPDATE", id: "d1", quantity: 99 });
    expect(s99.items[0].quantity).toBe(99);
    expect(cartReducer(s99, { type: "UPDATE", id: "d1", quantity: 100 })).toBe(s99);
    expect(cartReducer(s99, { type: "UPDATE", id: "d1", quantity: 2.5 })).toBe(s99);
    expect(cartReducer(s99, { type: "ADD", item: d1, restaurant: r1 }).items[0].quantity).toBe(99);
    expect(cartReducer(s99, { type: "UPDATE", id: "d1", quantity: 0 })).toBe(initialCart);
  });
});
