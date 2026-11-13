// AI insights page (Requirements 28.6, 28.9, 29.9).
// The customer can send one of four preset questions, request a summary of the last five orders,
// or type a free-text question (1 to 500 characters). The answer appears in a response panel.
// Failures from the Backend get a matching message: 429 (rate limit, with the Retry-After
// seconds), 502 (AI service error) and 503 (AI not configured).
// The raw Axios error is caught here because `getErrorStatus` and `getRetryAfterSeconds` read it.
import { useState } from "react";
import { askInsight, getInsightSummary } from "../api/ai.js";
import { getErrorMessage, getErrorStatus, getRetryAfterSeconds } from "../api/client.js";
import FormField from "../components/FormField.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import Loader from "../components/Loader.jsx";
import { formatDateTime } from "../utils/format.js";
import "../styles/pages/AIInsights.css";

const MAX_QUESTION_LENGTH = 500;

const PRESET_QUESTIONS = [
  "Summarize my last five orders.",
  "Which of my orders are still not delivered?",
  "How much did I spend this week?",
  "Which food items have I ordered most frequently?",
];

const EMPTY_QUESTION_ERROR = "Enter a question.";
const TOO_LONG_ERROR = `Question must be at most ${MAX_QUESTION_LENGTH} characters.`;

/** User-facing message for a failed AI request. */
function aiErrorMessage(error) {
  const status = getErrorStatus(error);
  if (status === 429) {
    const seconds = getRetryAfterSeconds(error);
    return seconds === null
      ? "Too many requests. Please try again in a little while."
      : `Too many requests. Please try again in ${seconds} ${seconds === 1 ? "second" : "seconds"}.`;
  }
  if (status === 502) {
    return "The AI service is temporarily unavailable. Please try again later.";
  }
  if (status === 503) {
    return "AI insights are not configured. Please contact the administrator.";
  }
  return getErrorMessage(error);
}

/** Validation message for a (trimmed) question, or "" when it is valid. */
function validateQuestion(question) {
  if (question.length === 0) return EMPTY_QUESTION_ERROR;
  if (question.length > MAX_QUESTION_LENGTH) return TOO_LONG_ERROR;
  return "";
}

export default function AIInsights() {
  const [question, setQuestion] = useState("");
  const [showEmptyError, setShowEmptyError] = useState(false);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const trimmed = question.trim();
  const validationError = validateQuestion(trimmed);
  // An over-long question is reported while typing; an empty one only after a submit attempt.
  const fieldError =
    trimmed.length > MAX_QUESTION_LENGTH ? TOO_LONG_ERROR : showEmptyError ? validationError : "";

  async function run(request) {
    setPending(true);
    setError("");
    setResult(null);
    try {
      setResult(await request());
    } catch (err) {
      setError(aiErrorMessage(err));
    } finally {
      setPending(false);
    }
  }

  function handlePreset(text) {
    if (pending) return;
    run(() => askInsight(text));
  }

  function handleSummary() {
    if (pending) return;
    run(() => getInsightSummary());
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (pending) return;
    if (validationError) {
      setShowEmptyError(true);
      return;
    }
    run(() => askInsight(trimmed));
  }

  function handleChange(event) {
    setQuestion(event.target.value);
    setShowEmptyError(false);
  }

  return (
    <main className="container ai-insights-page">
      <h1 className="page-title">AI order insights</h1>
      <p className="text-muted ai-insights-intro">
        Ask about your order history. Answers are generated from your own orders.
      </p>

      <section className="ai-insights-section" aria-label="Quick questions">
        <h2 className="ai-insights-section-title">Quick questions</h2>
        <div className="ai-insights-presets">
          {PRESET_QUESTIONS.map((text) => (
            <button
              key={text}
              type="button"
              className="btn btn-secondary"
              disabled={pending}
              onClick={() => handlePreset(text)}
            >
              {text}
            </button>
          ))}
        </div>
        <div className="ai-insights-summary-action">
          <button type="button" className="btn btn-primary" disabled={pending} onClick={handleSummary}>
            Summarize my last 5 orders
          </button>
        </div>
      </section>

      <section className="ai-insights-section" aria-label="Ask your own question">
        <h2 className="ai-insights-section-title">Ask your own question</h2>
        <form className="ai-insights-form" onSubmit={handleSubmit} noValidate>
          <FormField
            label="Your question"
            as="textarea"
            rows={4}
            name="question"
            value={question}
            onChange={handleChange}
            error={fieldError}
            disabled={pending}
            placeholder="For example: What was my most expensive order?"
          />
          <div className="ai-insights-form-footer">
            <span
              className={
                trimmed.length > MAX_QUESTION_LENGTH
                  ? "ai-insights-counter ai-insights-counter-over"
                  : "ai-insights-counter text-muted"
              }
              aria-live="off"
            >
              {trimmed.length}/{MAX_QUESTION_LENGTH}
            </span>
            <button type="submit" className="btn btn-primary" disabled={pending}>
              Ask
            </button>
          </div>
        </form>
      </section>

      {pending && <Loader label="Asking the AI. This can take a few seconds..." />}
      {!pending && error && <ErrorMessage message={error} />}

      <section className="ai-insights-response" aria-label="AI response" aria-live="polite">
        {!pending && result && (
          <article className="ai-insights-response-card">
            <h2 className="ai-insights-section-title">Response</h2>
            <p className="ai-insights-answer">{result.answer}</p>
            <p className="ai-insights-response-meta text-muted">
              <span>Orders considered: {result.order_count ?? 0}</span>
              <span>Generated {formatDateTime(result.generated_at)}</span>
            </p>
          </article>
        )}
      </section>
    </main>
  );
}
