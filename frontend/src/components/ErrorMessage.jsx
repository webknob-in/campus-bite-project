// ErrorMessage: shows the error detail from a failed request with an optional retry button
// (Requirement 33.3). `role="alert"` makes assistive technology announce it immediately.
const FALLBACK_MESSAGE = "Something went wrong. Please try again.";

export default function ErrorMessage({ message, onRetry, retryLabel = "Try again" }) {
  return (
    <div className="error-message" role="alert" aria-live="assertive" aria-atomic="true">
      <p className="error-message-text">{message || FALLBACK_MESSAGE}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}
