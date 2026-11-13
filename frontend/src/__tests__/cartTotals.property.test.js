import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { cartCount, cartSubtotal, initialCart } from "../context/cartReducer.js";

// Feature: campusbite-platform, Property 9: Cart totals
// **Validates: Requirements 10.5**

// Prices are decimal strings with exactly two decimals, e.g. "12.50".
const priceArb = fc
  .tuple(fc.integer({ min: 0, max: 9999 }), fc.integer({ min: 0, max: 99 }))
  .map(([units, cents]) => `${units}.${String(cents).padStart(2, "0")}`);

const lineArb = fc.record({
  id: fc.uuid(),
  name: fc.string({ minLength: 1, maxLength: 20 }),
  price: priceArb,
  quantity: fc.integer({ min: 1, max: 99 }),
});

// A cart has unique line ids.
const cartArb = fc
  .array(lineArb, { maxLength: 15, selector: (l) => l.id })
  .map((items) => ({ restaurantId: "r1", restaurantName: "Test", items }));

// Independent model: parse "units.cc" with integer math only.
function priceToCents(price) {
  const [units, frac] = price.split(".");
  return parseInt(units, 10) * 100 + parseInt(frac, 10);
}
const modelCents = (cart) => cart.items.reduce((sum, l) => sum + priceToCents(l.price) * l.quantity, 0);
const modelCount = (cart) => cart.items.reduce((sum, l) => sum + l.quantity, 0);

describe("Property 9: Cart totals", () => {
  it("cartCount equals the sum of quantities and cartSubtotal equals sum(price x quantity) in cents", () => {
    fc.assert(
      fc.property(cartArb, (cart) => {
        const cents = modelCents(cart);
        const subtotal = cartSubtotal(cart);
        expect(cartCount(cart)).toBe(modelCount(cart));
        expect(Math.round(subtotal * 100)).toBe(cents);
        expect(subtotal).toBe(cents / 100);
      }),
      { numRuns: 200 },
    );
  });

  it("totals do not depend on line order", () => {
    fc.assert(
      fc.property(cartArb, fc.integer({ min: 0, max: 100 }), (cart, shift) => {
        const items = cart.items;
        const rotated = items.length ? [...items.slice(shift % items.length), ...items.slice(0, shift % items.length)] : [];
        const reversed = [...items].reverse();
        for (const reordered of [rotated, reversed]) {
          const other = { ...cart, items: reordered };
          expect(cartCount(other)).toBe(cartCount(cart));
          expect(cartSubtotal(other)).toBe(cartSubtotal(cart));
        }
      }),
      { numRuns: 100 },
    );
  });

  it("an empty cart has count 0 and subtotal 0", () => {
    expect(cartCount(initialCart)).toBe(0);
    expect(cartSubtotal(initialCart)).toBe(0);
  });
});
