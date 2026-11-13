// Loader: shown while a page waits for a Backend response (Requirement 33.2).
// `role="status"` makes assistive technology announce the label politely.
export default function Loader({ label = "Loading..." }) {
  return (
    <div className="loader" role="status" aria-live="polite" aria-atomic="true">
      <span className="loader-spinner" aria-hidden="true" />
      <span className="loader-label">{label}</span>
    </div>
  );
}
