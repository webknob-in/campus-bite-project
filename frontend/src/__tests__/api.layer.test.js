import { AxiosError } from "axios";
import fc from "fast-check";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { askInsight, getInsightSummary } from "../api/ai";
import * as authApi from "../api/auth";
import client, {
  NETWORK_ERROR_MESSAGE,
  TOKEN_KEY,
  cleanParams,
  getErrorMessage,
  getErrorStatus,
  getRetryAfterSeconds,
  setUnauthorizedHandler,
} from "../api/client";
import { getHealth } from "../api/health";
import * as ordersApi from "../api/orders";
import * as ownerApi from "../api/owner";
import * as partnerApi from "../api/partner";
import * as restaurantsApi from "../api/restaurants";

// Replace the network adapter: record each outgoing request config and answer with `reply`.
const originalAdapter = client.defaults.adapter;
let sent;
let reply;

beforeEach(() => {
  sent = [];
  reply = (config) => ({ status: 200, statusText: "OK", headers: {}, config, data: { ok: true } });
  client.defaults.adapter = async (config) => {
    sent.push(config);
    const response = reply(config);
    if (response.status >= 400) {
      throw new AxiosError(`status ${response.status}`, AxiosError.ERR_BAD_REQUEST, config, null, response);
    }
    return response;
  };
  localStorage.clear();
});

afterEach(() => {
  client.defaults.adapter = originalAdapter;
  setUnauthorizedHandler();
  localStorage.clear();
});

const errorWith = (status, data, headers = {}) => ({ response: { status, data, headers } });

describe("client interceptors", () => {
  it("attaches the stored JWT as a Bearer header", async () => {
    localStorage.setItem(TOKEN_KEY, "jwt-123");
    await authApi.getMe();
    expect(sent[0].headers.get("Authorization")).toBe("Bearer jwt-123");
  });

  it("sends no Authorization header when no token is stored", async () => {
    await getHealth();
    expect(sent[0].headers.get("Authorization")).toBeFalsy();
  });

  it("invokes the unauthorized handler on 401 when a token is stored, and still rejects", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    localStorage.setItem(TOKEN_KEY, "expired");
    reply = (config) => ({ status: 401, headers: {}, config, data: { detail: "Invalid token" } });

    await expect(authApi.getMe()).rejects.toMatchObject({ response: { status: 401 } });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not invoke the handler for a 401 without a stored token (failed login)", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    reply = (config) => ({ status: 401, headers: {}, config, data: { detail: "Invalid email or password" } });

    await expect(authApi.login("a@b.co", "wrong-pass")).rejects.toBeDefined();
    expect(handler).not.toHaveBeenCalled();
  });

  it("does not invoke the handler for non-401 errors", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    localStorage.setItem(TOKEN_KEY, "jwt");
    reply = (config) => ({ status: 403, headers: {}, config, data: { detail: "Forbidden" } });

    await expect(ownerApi.getOwnerStats()).rejects.toBeDefined();
    expect(handler).not.toHaveBeenCalled();
  });
});

describe("getErrorMessage", () => {
  it("returns a string detail unchanged", () => {
    expect(getErrorMessage(errorWith(409, { detail: "Email already registered" }))).toBe(
      "Email already registered"
    );
  });

  it("joins the msg of every item in a FastAPI 422 detail list", () => {
    const detail = [
      { loc: ["body", "password"], msg: "String should have at least 8 characters", type: "string_too_short" },
      { loc: ["body", "email"], msg: "value is not a valid email address", type: "value_error" },
    ];
    expect(getErrorMessage(errorWith(422, { detail }))).toBe(
      "String should have at least 8 characters, value is not a valid email address"
    );
  });

  it("returns the network message when no response was received", () => {
    expect(getErrorMessage(new Error("Network Error"))).toBe(NETWORK_ERROR_MESSAGE);
    expect(getErrorMessage(undefined)).toBe(NETWORK_ERROR_MESSAGE);
  });

  it("falls back to the status code when the body has no usable detail", () => {
    expect(getErrorMessage(errorWith(502, "<html>Bad Gateway</html>"))).toBe("Request failed (502)");
    expect(getErrorMessage(errorWith(500, null))).toBe("Request failed (500)");
    expect(getErrorMessage(errorWith(422, { detail: [] }))).toBe("Request failed (422)");
  });

  it("always returns a non-empty string for arbitrary failures", () => {
    const body = fc.oneof(
      fc.constant(null),
      fc.string(),
      fc.record({ detail: fc.oneof(fc.string(), fc.array(fc.record({ msg: fc.string() })), fc.constant(null)) })
    );
    fc.assert(
      fc.property(fc.option(fc.integer({ min: 400, max: 599 })), body, (status, data) => {
        const error = status === null ? new Error("x") : errorWith(status, data);
        const message = getErrorMessage(error);
        return typeof message === "string" && message.length > 0;
      })
    );
  });

  it("exposes the status and Retry-After seconds of a failed response", () => {
    expect(getErrorStatus(errorWith(429, {}, { "retry-after": "12" }))).toBe(429);
    expect(getErrorStatus(new Error("offline"))).toBeNull();
    expect(getRetryAfterSeconds(errorWith(429, {}, { "retry-after": "12" }))).toBe(12);
    expect(getRetryAfterSeconds(errorWith(429, {}, {}))).toBeNull();
  });
});

describe("cleanParams", () => {
  it("drops undefined, null, and empty strings but keeps false and 0", () => {
    expect(cleanParams({ a: undefined, b: null, c: "", d: false, e: 0, f: "x" })).toEqual({
      d: false,
      e: 0,
      f: "x",
    });
    expect(cleanParams(undefined)).toEqual({});
  });
});

// One row per endpoint in Requirement 40: [name, call, method, url, params, body]
const payment = { card_holder: "Asha Rao", card_number: "4111111111111111", expiry: "12/30", cvv: "123" };
const orderPayload = {
  items: [{ menu_item_id: 3, quantity: 2 }],
  delivery_address: "Hostel 5, Room 12",
  delivery_phone: "9876543210",
  payment,
};
const endpointTable = [
  ["register", () => authApi.register({ email: "a@b.co" }), "post", "/auth/register", undefined, { email: "a@b.co" }],
  ["login", () => authApi.login("a@b.co", "secret123"), "post", "/auth/login", undefined, { email: "a@b.co", password: "secret123" }],
  ["getMe", () => authApi.getMe(), "get", "/auth/me"],
  ["getHealth", () => getHealth(), "get", "/health"],

  ["listRestaurants", () => restaurantsApi.listRestaurants({ search: "curry", page: 2, page_size: 5, extra: "" }), "get", "/restaurants", { search: "curry", page: 2, page_size: 5 }],
  ["getRestaurant", () => restaurantsApi.getRestaurant(4), "get", "/restaurants/4"],
  ["getRestaurantMenu", () => restaurantsApi.getRestaurantMenu(4, { search: "dosa", min_price: 10, max_price: 90, page: 1 }), "get", "/restaurants/4/menu", { search: "dosa", min_price: 10, max_price: 90, page: 1 }],
  ["listDishes", () => restaurantsApi.listDishes({ search: "", min_price: 0 }), "get", "/dishes", { min_price: 0 }],
  ["getRestaurantReviews", () => restaurantsApi.getRestaurantReviews(4, { page: 3 }), "get", "/restaurants/4/reviews", { page: 3 }],

  ["placeOrder", () => ordersApi.placeOrder(orderPayload), "post", "/orders", undefined, orderPayload],
  ["listMyOrders", () => ordersApi.listMyOrders({ status: "PLACED", date_from: "2025-01-01", date_to: "2025-01-31", page: 1, page_size: 10 }), "get", "/orders/me", { status: "PLACED", date_from: "2025-01-01", date_to: "2025-01-31", page: 1, page_size: 10 }],
  ["getOrder", () => ordersApi.getOrder(9), "get", "/orders/9"],
  ["cancelOrder", () => ordersApi.cancelOrder(9), "post", "/orders/9/cancel"],
  ["submitReview", () => ordersApi.submitReview(9, { rating: 5, comment: "Great" }), "post", "/orders/9/review", undefined, { rating: 5, comment: "Great" }],
  ["requestReturn", () => ordersApi.requestReturn(9, "Cold food"), "post", "/orders/9/return", undefined, { reason: "Cold food" }],

  ["listOwnerMenuItems", () => ownerApi.listOwnerMenuItems({ search: "tea", page: 2 }), "get", "/owner/menu-items", { search: "tea", page: 2 }],
  ["createMenuItem", () => ownerApi.createMenuItem({ name: "Tea", price: 10 }), "post", "/owner/menu-items", undefined, { name: "Tea", price: 10 }],
  ["updateMenuItem", () => ownerApi.updateMenuItem(7, { price: 12 }), "patch", "/owner/menu-items/7", undefined, { price: 12 }],
  ["deleteMenuItem", () => ownerApi.deleteMenuItem(7), "delete", "/owner/menu-items/7"],
  ["setMenuItemAvailability", () => ownerApi.setMenuItemAvailability(7, false), "patch", "/owner/menu-items/7/availability", undefined, { is_available: false }],
  ["listOwnerOrders", () => ownerApi.listOwnerOrders({ status: "READY", date_from: "2025-02-01" }), "get", "/owner/orders", { status: "READY", date_from: "2025-02-01" }],
  ["updateOwnerOrderStatus", () => ownerApi.updateOwnerOrderStatus(5, "ACCEPTED"), "patch", "/owner/orders/5/status", undefined, { status: "ACCEPTED" }],
  ["listDeliveryPartners", () => ownerApi.listDeliveryPartners(), "get", "/owner/delivery-partners"],
  ["assignDeliveryPartner", () => ownerApi.assignDeliveryPartner(5, 11), "post", "/owner/orders/5/assign", undefined, { delivery_partner_id: 11 }],
  ["listReturns", () => ownerApi.listReturns({ status: "requested", page: 1 }), "get", "/owner/returns", { status: "requested", page: 1 }],
  ["approveReturn", () => ownerApi.approveReturn(5), "post", "/owner/returns/5/approve"],
  ["rejectReturn", () => ownerApi.rejectReturn(5), "post", "/owner/returns/5/reject"],
  ["getOwnerStats", () => ownerApi.getOwnerStats(), "get", "/owner/stats"],
  ["listReminders", () => ownerApi.listReminders({ resolved: false, page: 1 }), "get", "/owner/reminders", { resolved: false, page: 1 }],
  ["resolveReminder", () => ownerApi.resolveReminder(8), "patch", "/owner/reminders/8/resolve"],

  ["listPartnerOrders", () => partnerApi.listPartnerOrders({ status: "ASSIGNED", page: 1 }), "get", "/partner/orders", { status: "ASSIGNED", page: 1 }],
  ["getPartnerOrder", () => partnerApi.getPartnerOrder(6), "get", "/partner/orders/6"],
  ["updatePartnerOrderStatus", () => partnerApi.updatePartnerOrderStatus(6, "DELIVERED"), "patch", "/partner/orders/6/status", undefined, { status: "DELIVERED" }],
  ["listPartnerHistory", () => partnerApi.listPartnerHistory({ page: 2, page_size: 20 }), "get", "/partner/history", { page: 2, page_size: 20 }],

  ["askInsight", () => askInsight("How much did I spend?"), "post", "/ai/insights", undefined, { question: "How much did I spend?" }],
  ["getInsightSummary", () => getInsightSummary(), "get", "/ai/insights/summary"],
];

describe("endpoint wrappers", () => {
  it.each(endpointTable)("%s calls the right method, path, query, and body", async (_name, call, method, url, params, body) => {
    await call();

    expect(sent).toHaveLength(1);
    expect(sent[0].method).toBe(method);
    expect(sent[0].url).toBe(url);
    expect(sent[0].params).toEqual(params);
    if (body === undefined) {
      expect(sent[0].data).toBeUndefined();
    } else {
      expect(JSON.parse(sent[0].data)).toEqual(body);
    }
  });

  it("returns the response body rather than the Axios response", async () => {
    reply = (config) => ({ status: 200, headers: {}, config, data: { items: [], total: 0, page: 1, page_size: 10 } });
    await expect(restaurantsApi.listRestaurants()).resolves.toEqual({ items: [], total: 0, page: 1, page_size: 10 });
  });

  it("resolves deleteMenuItem to undefined on 204", async () => {
    reply = (config) => ({ status: 204, headers: {}, config, data: "" });
    await expect(ownerApi.deleteMenuItem(7)).resolves.toBeUndefined();
  });

  it("covers every endpoint listed in Requirement 40 exactly once", () => {
    const pairs = endpointTable.map(([, , method, url]) => `${method.toUpperCase()} ${url.replace(/\/\d+/g, "/{id}")}`);
    const expected = [
      "POST /auth/register", "POST /auth/login", "GET /auth/me",
      "GET /restaurants", "GET /restaurants/{id}", "GET /restaurants/{id}/menu", "GET /dishes", "GET /restaurants/{id}/reviews",
      "GET /owner/menu-items", "POST /owner/menu-items", "PATCH /owner/menu-items/{id}", "DELETE /owner/menu-items/{id}", "PATCH /owner/menu-items/{id}/availability",
      "POST /orders", "GET /orders/me", "GET /orders/{id}",
      "POST /orders/{id}/cancel", "GET /owner/orders", "PATCH /owner/orders/{id}/status",
      "GET /partner/orders", "GET /partner/orders/{id}", "PATCH /partner/orders/{id}/status", "GET /partner/history",
      "GET /owner/delivery-partners", "POST /owner/orders/{id}/assign",
      "POST /orders/{id}/review",
      "POST /orders/{id}/return", "GET /owner/returns", "POST /owner/returns/{id}/approve", "POST /owner/returns/{id}/reject",
      "POST /ai/insights", "GET /ai/insights/summary",
      "GET /owner/stats", "GET /owner/reminders", "PATCH /owner/reminders/{id}/resolve",
      "GET /health",
    ];
    expect([...pairs].sort()).toEqual([...expected].sort());
  });
});
