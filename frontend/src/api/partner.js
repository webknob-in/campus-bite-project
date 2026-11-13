// Delivery partner endpoints (Requirement 40.5). All require the DELIVERY_PARTNER role
// and only ever return orders assigned to the logged-in partner. Lists return a Page.
import client, { cleanParams } from "./client";

const enc = encodeURIComponent;

/**
 * GET /partner/orders. Assigned orders.
 * @param {{status?: string, page?: number, page_size?: number}} [params]
 */
export const listPartnerOrders = (params) =>
  client.get("/partner/orders", { params: cleanParams(params) }).then((res) => res.data);

/** GET /partner/orders/{id}. Assigned order with customer delivery details. */
export const getPartnerOrder = (id) =>
  client.get(`/partner/orders/${enc(id)}`).then((res) => res.data);

/**
 * PATCH /partner/orders/{id}/status with `{status}`.
 * @param {number|string} id
 * @param {"OUT_FOR_DELIVERY" | "DELIVERED"} status
 */
export const updatePartnerOrderStatus = (id, status) =>
  client.patch(`/partner/orders/${enc(id)}/status`, { status }).then((res) => res.data);

/**
 * GET /partner/history. DELIVERED and REFUNDED orders, newest delivery first.
 * @param {{page?: number, page_size?: number}} [params]
 */
export const listPartnerHistory = (params) =>
  client.get("/partner/history", { params: cleanParams(params) }).then((res) => res.data);
