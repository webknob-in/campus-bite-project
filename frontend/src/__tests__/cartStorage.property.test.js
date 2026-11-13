import { beforeEach, describe, expect, it } from "vitest";
import fc from "fast-check";
import { deserializeCart, initialCart, serializeCart } from "../context/cartReducer";
import { CART_KEY } from "../api/client";

// Feature: campusbite-platform, Property 10: Cart storage round trip
// Validates: Requirements 10.6

const idArb = fc.string({ minLength: 1, maxLength: 12 });
// Two-decimal price strings such as "0.00", "12.50", "999.99".
const priceArb = fc
  .tuple(fc.integer({ min: 0, max: 9999 }), fc.integer({ min: 0, max: 99 }))
  .map(([whole, cents]) => `${whole}.${String(cents).padStart(2, "0")}`);
const lineArb = fc.record({
  id: idArb,
  name: fc.string({ maxLength: 30 }),
  price: priceArb,
  quantity: fc.integer({ min: 1, max: 99 }),
});

// A valid non-empty cart: one restaurant, 1..n lines with unique ids.
const cartArb = fc.record({
  restaurantId: idArb,
  restaurantName: fc.string({ maxLength: 30 }),
  items: fc.uniqueArray(lineArb, { minLength: 1, maxLength: 10, selector: (l) => l.id }),
});

describe("cart storage property: serialize/deserialize round trip", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("deserializeCart(serializeCart(cart)) equals the cart, and the output is valid JSON", () => {
    fc.assert(
      fc.property(cartArb, (cart) => {
        const raw = serializeCart(cart);
        expect(() => JSON.parse(raw)).not.toThrow();
        expect(deserializeCart(raw)).toEqual(cart);
      }),
      { numRuns: 200 },
    );
  });

  it("round trips through localStorage under the campusbite_cart key", () => {
    expect(CART_KEY).toBe("campusbite_cart");
    fc.assert(
      fc.property(cartArb, (cart) => {
        localStorage.clear();
        localStorage.setItem(CART_KEY, serializeCart(cart));
        expect(deserializeCart(localStorage.getItem(CART_KEY))).toEqual(cart);
      }),
      { numRuns: 100 },
    );
  });

  it("the empty cart round trips to initialCart", () => {
    expect(deserializeCart(serializeCart(initialCart))).toEqual(initialCart);
    localStorage.setItem(CART_KEY, serializeCart(initialCart));
    expect(deserializeCart(localStorage.getItem(CART_KEY))).toEqual(initialCart);
  });

  it("corrupt input never throws and yields an empty cart", () => {
    expect(deserializeCart(null)).toEqual(initialCart);
    expect(localStorage.getItem(CART_KEY)).toBeNull();
    expect(deserializeCart(localStorage.getItem(CART_KEY))).toEqual(initialCart);
    fc.assert(
      fc.property(fc.string({ maxLength: 60 }), (raw) => {
        let result;
        expect(() => {
          result = deserializeCart(raw);
        }).not.toThrow();
        expect(result).toEqual(initialCart);
      }),
      { numRuns: 200 },
    );
  });
});
