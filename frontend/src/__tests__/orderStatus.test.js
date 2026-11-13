import { describe, expect, it } from "vitest";

import {
  ALL_STATUSES,
  canCancel,
  canRequestReturn,
  canReview,
  nextOwnerAction,
  nextPartnerAction,
  partitionOrders,
} from "../utils/orderStatus";

// Requirements 12.4, 12.5, 13.4: action helpers for all 9 Order_Status values.

const OWNER = { PLACED: "ACCEPTED", ACCEPTED: "PREPARING", PREPARING: "READY" };
const PARTNER = { ASSIGNED: "OUT_FOR_DELIVERY", OUT_FOR_DELIVERY: "DELIVERED" };

describe("orderStatus helpers", () => {
  it("covers 9 statuses", () => {
    expect(ALL_STATUSES).toHaveLength(9);
  });

  it.each(ALL_STATUSES)("%s: action helpers", (status) => {
    expect(canCancel({ status })).toBe(status === "PLACED");
    expect(canReview({ status })).toBe(status === "DELIVERED" || status === "REFUNDED");
    expect(canReview({ status, review: { rating: 5 } })).toBe(false);
    expect(canRequestReturn({ status, return_status: "none" })).toBe(status === "DELIVERED");
    expect(canRequestReturn({ status, return_status: "requested" })).toBe(false);
    expect(nextOwnerAction(status)?.target ?? null).toBe(OWNER[status] ?? null);
    expect(nextPartnerAction(status)?.target ?? null).toBe(PARTNER[status] ?? null);
  });

  it("handles missing orders", () => {
    expect(canCancel(undefined)).toBe(false);
    expect(canReview(null)).toBe(false);
    expect(nextOwnerAction("bogus")).toBeNull();
  });

  it("partitions orders into current and previous preserving order", () => {
    const orders = ALL_STATUSES.map((status, i) => ({ id: i, status }));
    const { current, previous } = partitionOrders(orders);
    expect(current.map((o) => o.status)).toEqual(ALL_STATUSES.slice(0, 6));
    expect(previous.map((o) => o.status)).toEqual(["DELIVERED", "CANCELLED", "REFUNDED"]);
  });
});
