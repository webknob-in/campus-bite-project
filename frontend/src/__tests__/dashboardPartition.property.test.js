import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { ALL_STATUSES, CURRENT, LIFECYCLE, TERMINAL, partitionOrders } from "../utils/orderStatus.js";

// Feature: campusbite-platform, Property 23: Dashboard partition
// **Validates: Requirements 24.1**

// Independent model (Requirement 24.1): PLACED..OUT_FOR_DELIVERY are current;
// DELIVERED, CANCELLED, REFUNDED are previous.
const MODEL_CURRENT = ["PLACED", "ACCEPTED", "PREPARING", "READY", "ASSIGNED", "OUT_FOR_DELIVERY"];
const MODEL_PREVIOUS = ["DELIVERED", "CANCELLED", "REFUNDED"];
const isCurrent = (status) => MODEL_CURRENT.includes(status);

const orderArb = fc.record({
  id: fc.integer({ min: 1, max: 1_000_000 }),
  status: fc.constantFrom(...MODEL_CURRENT, ...MODEL_PREVIOUS),
  total_amount: fc.integer({ min: 0, max: 100000 }).map((n) => (n / 100).toFixed(2)),
});

// Orders have unique ids.
const ordersArb = fc.uniqueArray(orderArb, { maxLength: 40, selector: (o) => o.id });

describe("Property 23: Dashboard partition", () => {
  it("the status sets in orderStatus.js agree with Requirement 24.1", () => {
    expect([...ALL_STATUSES].sort()).toEqual([...MODEL_CURRENT, ...MODEL_PREVIOUS].sort());
    expect([...CURRENT].sort()).toEqual([...MODEL_CURRENT].sort());
    expect([...TERMINAL].every((s) => MODEL_PREVIOUS.includes(s))).toBe(true);
    expect(LIFECYCLE.slice(0, MODEL_CURRENT.length)).toEqual(MODEL_CURRENT);
  });

  it("puts every order in exactly one list, current holds only in-progress statuses, order preserved", () => {
    fc.assert(
      fc.property(ordersArb, (orders) => {
        const snapshot = JSON.parse(JSON.stringify(orders));
        const { current, previous } = partitionOrders(orders);

        // Sizes add up.
        expect(current.length + previous.length).toBe(orders.length);

        // Each list holds only the statuses the model assigns to it.
        expect(current.every((o) => isCurrent(o.status))).toBe(true);
        expect(previous.every((o) => !isCurrent(o.status))).toBe(true);

        // Relative input order preserved; this also means no id is lost or duplicated.
        expect(current.map((o) => o.id)).toEqual(orders.filter((o) => isCurrent(o.status)).map((o) => o.id));
        expect(previous.map((o) => o.id)).toEqual(orders.filter((o) => !isCurrent(o.status)).map((o) => o.id));

        // Every id appears exactly once across both lists.
        const ids = [...current, ...previous].map((o) => o.id);
        expect(new Set(ids).size).toBe(ids.length);
        expect([...ids].sort((a, b) => a - b)).toEqual(orders.map((o) => o.id).sort((a, b) => a - b));

        // Input is not mutated.
        expect(orders).toEqual(snapshot);
      }),
      { numRuns: 100 },
    );
  });

  it("returns two empty lists for empty input", () => {
    expect(partitionOrders([])).toEqual({ current: [], previous: [] });
  });
});
