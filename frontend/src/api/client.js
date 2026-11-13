// API_Client: the single Axios instance every page uses to talk to the FastAPI backend
// (Requirements 1.5, 5.6, 5.8, 33.1, 33.3, 45.3).
//
// - Base URL comes from the `VITE_API_BASE_URL` environment variable (Requirement 33.1).
// - A request interceptor attaches `Authorization: Bearer <jwt>` from localStorage (Requirement 5.6).
// - A response interceptor calls the registered 401 handler so AuthContext can log out and
//   navigate to /login (Requirement 5.8).
// - `getErrorMessage` turns any failed request into text for the ErrorMessage component
//   (Requirement 33.3).
import axios from "axios";

// localStorage keys shared with AuthContext and CartContext.
export const TOKEN_KEY = "campusbite_token";
export const USER_KEY = "campusbite_user";
export const CART_KEY = "campusbite_cart";

export const NETWORK_ERROR_MESSAGE = "Network error. Please check your connection and try again.";

// Replaced by AuthContext (task 12.3) through setUnauthorizedHandler.
const noop = () => {};
let onUnauthorized = noop;

/**
 * Registers the callback invoked when a request made with a stored token receives HTTP 401.
 * Pass nothing (or a non-function) to clear it, for example from an effect cleanup.
 */
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = typeof fn === "function" ? fn : noop;
};

// Strip trailing slashes so `${baseURL}${path}` never produces `//`.
const baseURL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "") || undefined;

const client = axios.create({ baseURL, timeout: 40000 });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    // Only react when a session exists. A 401 from a failed login (no stored token)
    // must surface as a normal form error instead of triggering a logout.
    if (error.response?.status === 401 && localStorage.getItem(TOKEN_KEY)) onUnauthorized();
    return Promise.reject(error);
  }
);

/**
 * Drops query parameters that are `undefined`, `null`, or an empty string so that blank
 * filter inputs are not sent (the backend would reject `status=` with HTTP 422).
 * `false` and `0` are kept: `resolved=false` and `page=0` are meaningful values.
 */
export function cleanParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params ?? {}).filter(([, value]) => value !== undefined && value !== null && value !== "")
  );
}

/**
 * Converts a failed request into a user-facing message.
 * - No response (offline, DNS, CORS, timeout): generic network message.
 * - `detail` string (HTTPException): used as is.
 * - `detail` list (FastAPI 422 validation errors): the `msg` of each item joined by ", ".
 * - Anything else: "Request failed (<status>)".
 */
export function getErrorMessage(error) {
  const response = error?.response;
  if (!response) return NETWORK_ERROR_MESSAGE;

  const detail = response.data?.detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (typeof item === "string" ? item : item?.msg))
      .filter((msg) => typeof msg === "string" && msg.trim() !== "");
    if (messages.length > 0) return messages.join(", ");
  } else if (typeof detail === "string" && detail.trim() !== "") {
    return detail;
  } else if (typeof detail?.message === "string" && detail.message.trim() !== "") {
    return detail.message;
  }
  return `Request failed (${response.status})`;
}

/** HTTP status of a failed request, or `null` when no response was received. */
export function getErrorStatus(error) {
  return error?.response?.status ?? null;
}

/**
 * Seconds from the `Retry-After` header of a 429 response, or `null` when absent or invalid.
 * The backend exposes this header through CORS (`expose_headers`).
 */
export function getRetryAfterSeconds(error) {
  const headers = error?.response?.headers;
  const raw = headers?.get?.("retry-after") ?? headers?.["retry-after"];
  const seconds = Number.parseFloat(raw);
  return Number.isFinite(seconds) && seconds >= 0 ? Math.ceil(seconds) : null;
}

export default client;
