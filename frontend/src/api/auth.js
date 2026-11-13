// Authentication endpoints (Requirement 40.1).
//
// Conventions shared by every module in src/api/:
// - Each function returns a Promise of the response body (`response.data`), not the Axios response.
// - Failures reject with the Axios error; pass it to `getErrorMessage` from ./client.js.
// - Single-field request bodies take the bare value; larger bodies take the body object as-is.
import client from "./client";

/**
 * POST /auth/register (201). Returns the created user profile.
 * @param {{name: string, email: string, password: string, phone: string, address?: string,
 *   role: "CUSTOMER" | "RESTAURANT_OWNER" | "DELIVERY_PARTNER",
 *   restaurant?: {name: string, description: string, cuisine: string, address: string, image_url?: string}}} payload
 *   `restaurant` is required when `role` is RESTAURANT_OWNER.
 */
export const register = (payload) => client.post("/auth/register", payload).then((res) => res.data);

/**
 * POST /auth/login. Returns `{access_token, token_type, user}`.
 * Storing the token and user in localStorage is the job of AuthContext.
 */
export const login = (email, password) =>
  client.post("/auth/login", { email, password }).then((res) => res.data);

/** GET /auth/me. Returns the authenticated user's profile. */
export const getMe = () => client.get("/auth/me").then((res) => res.data);
