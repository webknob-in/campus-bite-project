// AI order insight endpoints (Requirement 40.9). Both require the CUSTOMER role.
// Failures worth special handling in the UI: 429 (rate limit, see `getRetryAfterSeconds`
// in ./client.js), 502 (OpenAI error), and 503 (AI not configured).
import client from "./client";

/**
 * POST /ai/insights with `{question}`.
 * @param {string} question 1 to 500 characters.
 * @returns {Promise<object>} The backend response containing the answer text.
 */
export const askInsight = (question) =>
  client.post("/ai/insights", { question }).then((res) => res.data);

/** GET /ai/insights/summary. Summary of the customer's last five orders. */
export const getInsightSummary = () => client.get("/ai/insights/summary").then((res) => res.data);
