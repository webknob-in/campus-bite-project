// Role constants and per-role home pages (Requirements 5.9, 32.2).

export const ROLES = Object.freeze({
  CUSTOMER: "CUSTOMER",
  RESTAURANT_OWNER: "RESTAURANT_OWNER",
  DELIVERY_PARTNER: "DELIVERY_PARTNER",
});

const ROLE_HOME = Object.freeze({
  [ROLES.CUSTOMER]: "/restaurants",
  [ROLES.RESTAURANT_OWNER]: "/owner/dashboard",
  [ROLES.DELIVERY_PARTNER]: "/partner/dashboard",
});

/**
 * Home page path for a role: the restaurant list for a Customer, the owner dashboard for a
 * Restaurant_Owner, the partner dashboard for a Delivery_Partner. Unknown or missing roles
 * (visitors) get "/login".
 */
export function roleHome(role) {
  return ROLE_HOME[role] ?? "/login";
}
