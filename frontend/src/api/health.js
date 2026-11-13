// Health check endpoint (Requirement 40.11).
import client from "./client";

/** GET /health. Resolves when the backend and database are reachable; rejects with 503 otherwise. */
export const getHealth = () => client.get("/health").then((res) => res.data);
