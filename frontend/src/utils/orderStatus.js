// Order_Status helpers shared by the customer, owner, and partner pages
// (Requirements 12.4, 12.5, 13.4, 14, 15, 17, 18, 21, 22, 24.1). Pure functions, no React.

/** All Order_Status values, happy path first, then the terminal off-path statuses. */
export const ALL_STATUSES = Object.freeze([
  "PLACED",
  "ACCEPTED",
  "PREPARING",
  "READY",
  "ASSIGNED",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
  "CANCELLED",
  "REFUNDED",
]);

/** Ordered happy path shown by the status timeline (Requirement 12.4). */
export const LIFECYCLE = Object.freeze([
  "PLACED",
  "ACCEPTED",
  "PREPARING",
  "READY",
  "ASSIGNED",
  "OUT_FOR_DELIVERY",
  "DELIVERED",
]);

/** In-progress statuses: `PLACED` through `OUT_FOR_DELIVERY` (Requirement 24.1). */
export const CURRENT = new Set([
  "PLACED",
  "ACCEPTED",
  "PREPARING",
  "READY",
  "ASSIGNED",
  "OUT_FOR_DELIVERY",
]);

/** Terminal statuses with no outgoing transitions. */
export const TERMINAL = new Set(["CANCELLED", "REFUNDED"]);

/** A Customer may cancel only while the Order is `PLACED` (Requirement 13). */
export const canCancel = (order) => order?.status === "PLACED";

/** Reviewable once delivered or refunded, and only if no Review exists yet. */
export const canReview = (order) =>
  ["DELIVERED", "REFUNDED"].includes(order?.status) && !order?.review;

/** A return can be requested for a delivered Order with no previous return request. */
export const canRequestReturn = (order) =>
  order?.status === "DELIVERED" && order?.return_status === "none";

const OWNER_ACTIONS = {
  PLACED: { label: "Accept", target: "ACCEPTED" },
  ACCEPTED: { label: "Start preparing", target: "PREPARING" },
  PREPARING: { label: "Mark ready", target: "READY" },
};

const PARTNER_ACTIONS = {
  ASSIGNED: { label: "Out for Delivery", target: "OUT_FOR_DELIVERY" },
  OUT_FOR_DELIVERY: { label: "Mark Delivered", target: "DELIVERED" },
};

/**
 * Next status change a Restaurant_Owner can make through the status endpoint, as
 * `{label, target}`, or null. `READY` has none: the owner assigns a Delivery_Partner instead.
 */
export const nextOwnerAction = (status) =>
  (Object.hasOwn(OWNER_ACTIONS, status) && { ...OWNER_ACTIONS[status] }) || null;

/** Next status change a Delivery_Partner can make, as `{label, target}`, or null. */
export const nextPartnerAction = (status) =>
  (Object.hasOwn(PARTNER_ACTIONS, status) && { ...PARTNER_ACTIONS[status] }) || null;

/**
 * Split Orders into `current` (`PLACED`..`OUT_FOR_DELIVERY`) and `previous`
 * (`DELIVERED`, `CANCELLED`, `REFUNDED`, and anything else). Each Order lands in exactly one
 * list and the input order is preserved in both.
 */
export const partitionOrders = (orders) => ({
  current: orders.filter((o) => CURRENT.has(o.status)),
  previous: orders.filter((o) => !CURRENT.has(o.status)),
});
