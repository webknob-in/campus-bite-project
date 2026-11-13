// Customer order endpoints (Requirement 40.3, 40.4, 40.5, 40.7, 40.8). All require the CUSTOMER role.
// `/orders/me` returns a Page: `{items, total, page, page_size}`.
import client, { cleanParams } from "./client";

/**
 * POST /orders (201). Places an order and records the mock payment.
 * @param {{items: {menu_item_id: number, quantity: number}[], delivery_address: string,
 *   delivery_phone: string,
 *   payment: {card_holder: string, card_number: string, expiry: string, cvv: string}}} payload
 */
export const placeOrder = (payload) => client.post("/orders", payload).then((res) => res.data);

/**
 * GET /orders/me. The customer's orders, newest first.
 * @param {{status?: string, date_from?: string, date_to?: string, page?: number, page_size?: number}} [params]
 *   Dates are ISO `YYYY-MM-DD`.
 */
export const listMyOrders = (params) =>
  client.get("/orders/me", { params: cleanParams(params) }).then((res) => res.data);

/** GET /orders/{id}. Own order with items, ledger entries, and review. */
export const getOrder = (id) =>
  client.get(`/orders/${encodeURIComponent(id)}`).then((res) => res.data);

/** POST /orders/{id}/cancel. PLACED -> CANCELLED; 409 for any other status. */
export const cancelOrder = (id) =>
  client.post(`/orders/${encodeURIComponent(id)}/cancel`).then((res) => res.data);

/**
 * POST /orders/{id}/review (201). Delivered orders only.
 * @param {number|string} id
 * @param {{rating: number, comment?: string}} review `rating` is an integer 1 to 5.
 */
export const submitReview = (id, review) =>
  client.post(`/orders/${encodeURIComponent(id)}/review`, review).then((res) => res.data);

/**
 * POST /orders/{id}/return. Requests a return/refund for a delivered order.
 * @param {number|string} id
 * @param {string} reason 5 to 1000 characters.
 */
export const requestReturn = (id, reason) =>
  client.post(`/orders/${encodeURIComponent(id)}/return`, { reason }).then((res) => res.data);
