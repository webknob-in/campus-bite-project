// Restaurant owner endpoints (Requirement 40.2, 40.5, 40.6, 40.8, 40.10).
// All require the RESTAURANT_OWNER role. List endpoints return a Page unless noted.
import client, { cleanParams } from "./client";

const enc = encodeURIComponent;

// ---- Menu management ----

/**
 * GET /owner/menu-items. The owner's own dishes.
 * @param {{search?: string, page?: number, page_size?: number}} [params]
 */
export const listOwnerMenuItems = (params) =>
  client.get("/owner/menu-items", { params: cleanParams(params) }).then((res) => res.data);

/**
 * POST /owner/menu-items (201).
 * @param {{name: string, description?: string, price: number, category?: string,
 *   image_url?: string, is_available?: boolean}} payload
 */
export const createMenuItem = (payload) =>
  client.post("/owner/menu-items", payload).then((res) => res.data);

/**
 * PATCH /owner/menu-items/{id}. Updates only the supplied fields.
 * @param {number|string} id
 * @param {object} changes Subset of the create payload.
 */
export const updateMenuItem = (id, changes) =>
  client.patch(`/owner/menu-items/${enc(id)}`, changes).then((res) => res.data);

/** DELETE /owner/menu-items/{id} (204). Resolves to `undefined`. */
export const deleteMenuItem = (id) =>
  client.delete(`/owner/menu-items/${enc(id)}`).then(() => undefined);

/** PATCH /owner/menu-items/{id}/availability with `{is_available}`. */
export const setMenuItemAvailability = (id, isAvailable) =>
  client
    .patch(`/owner/menu-items/${enc(id)}/availability`, { is_available: isAvailable })
    .then((res) => res.data);

// ---- Orders and delivery assignment ----

/**
 * GET /owner/orders. Orders of the owner's restaurant, newest first.
 * @param {{status?: string, date_from?: string, date_to?: string, page?: number, page_size?: number}} [params]
 */
export const listOwnerOrders = (params) =>
  client.get("/owner/orders", { params: cleanParams(params) }).then((res) => res.data);

/**
 * PATCH /owner/orders/{id}/status with `{status}`.
 * @param {number|string} id
 * @param {"ACCEPTED" | "PREPARING" | "READY"} status
 */
export const updateOwnerOrderStatus = (id, status) =>
  client.patch(`/owner/orders/${enc(id)}/status`, { status }).then((res) => res.data);

/** GET /owner/delivery-partners. Plain list of delivery partner profiles (not paged). */
export const listDeliveryPartners = () =>
  client.get("/owner/delivery-partners").then((res) => res.data);

/**
 * POST /owner/orders/{id}/assign with `{delivery_partner_id}`. READY -> ASSIGNED.
 * @param {number|string} orderId
 * @param {number} deliveryPartnerId
 */
export const assignDeliveryPartner = (orderId, deliveryPartnerId) =>
  client
    .post(`/owner/orders/${enc(orderId)}/assign`, { delivery_partner_id: deliveryPartnerId })
    .then((res) => res.data);

// ---- Returns and refunds ----

/**
 * GET /owner/returns. Orders with a return request, filterable by return status.
 * @param {{status?: "requested" | "approved" | "rejected", page?: number, page_size?: number}} [params]
 */
export const listReturns = (params) =>
  client.get("/owner/returns", { params: cleanParams(params) }).then((res) => res.data);

/** POST /owner/returns/{order_id}/approve. Refunds the order. */
export const approveReturn = (orderId) =>
  client.post(`/owner/returns/${enc(orderId)}/approve`).then((res) => res.data);

/** POST /owner/returns/{order_id}/reject. */
export const rejectReturn = (orderId) =>
  client.post(`/owner/returns/${enc(orderId)}/reject`).then((res) => res.data);

// ---- Statistics and reminders ----

/** GET /owner/stats. Also triggers the reminder task on the backend. */
export const getOwnerStats = () => client.get("/owner/stats").then((res) => res.data);

/**
 * GET /owner/reminders. Also triggers the reminder task on the backend.
 * @param {{resolved?: boolean, page?: number, page_size?: number}} [params]
 *   `resolved: false` lists unresolved reminders; omit it for all.
 */
export const listReminders = (params) =>
  client.get("/owner/reminders", { params: cleanParams(params) }).then((res) => res.data);

/** PATCH /owner/reminders/{id}/resolve. */
export const resolveReminder = (id) =>
  client.patch(`/owner/reminders/${enc(id)}/resolve`).then((res) => res.data);
