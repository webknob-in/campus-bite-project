// RatingSummary: average rating with review count, or "No ratings yet" (Requirement 8.1).
import "../styles/pages/BrowseCards.css";

export default function RatingSummary({ average, count = 0 }) {
  if (average === null || average === undefined || !Number.isFinite(Number(average))) {
    return <span className="rating-summary text-muted">No ratings yet</span>;
  }
  const value = Number(average).toFixed(1);
  return (
    <span className="rating-summary" aria-label={`Average rating ${value} out of 5, ${count} reviews`}>
      <span aria-hidden="true" className="rating-star">
        ★
      </span>{" "}
      <strong>{value}</strong>
      <span className="text-muted"> ({count})</span>
    </span>
  );
}
