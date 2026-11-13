// Public restaurant, menu, dish, and review endpoints (Requirement 40.2).
// List endpoints return a Page: `{items, total, page, page_size}`.
// `params` objects are sent as query strings; blank values (undefined, null, "") are dropped.
import client, { cleanParams } from "./client";

/**
 * GET /restaurants
 * @param {{search?: string, page?: number, page_size?: number}} [params]
 */
export const listRestaurants = (params) =>
  client.get("/restaurants", { params: cleanParams(params) }).then((res) => res.data);

/** GET /restaurants/{id}. Restaurant details with average rating. */
export const getRestaurant = (id) =>
  client.get(`/restaurants/${encodeURIComponent(id)}`).then((res) => res.data);

/**
 * GET /restaurants/{id}/menu
 * @param {number|string} id Restaurant id.
 * @param {{search?: string, min_price?: number|string, max_price?: number|string,
 *   page?: number, page_size?: number}} [params]
 */
export const getRestaurantMenu = (id, params) =>
  client
    .get(`/restaurants/${encodeURIComponent(id)}/menu`, { params: cleanParams(params) })
    .then((res) => res.data);

/**
 * GET /dishes. Dish search across all restaurants; each item includes its restaurant id and name.
 * @param {{search?: string, min_price?: number|string, max_price?: number|string,
 *   page?: number, page_size?: number}} [params]
 */
export const listDishes = (params) =>
  client.get("/dishes", { params: cleanParams(params) }).then((res) => res.data);

/**
 * GET /restaurants/{id}/reviews. Newest first.
 * @param {number|string} id Restaurant id.
 * @param {{page?: number, page_size?: number}} [params]
 */
export const getRestaurantReviews = (id, params) =>
  client
    .get(`/restaurants/${encodeURIComponent(id)}/reviews`, { params: cleanParams(params) })
    .then((res) => res.data);
