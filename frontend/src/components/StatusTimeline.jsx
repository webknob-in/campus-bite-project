// StatusTimeline: lifecycle progress for an Order (Requirements 12.4, 12.5).
//   <StatusTimeline status={order.status} />
// Renders PLACED..DELIVERED as an ordered list: earlier steps are completed, the matching step
// has aria-current="step", later steps are upcoming. For CANCELLED or REFUNDED the progress
// list is replaced by a terminal banner. State is also written as text, not only color.
import { LIFECYCLE } from "../utils/orderStatus.js";
import { statusLabel } from "./StatusBadge.jsx";
import "../styles/pages/StatusTimeline.css";

const TERMINAL_TEXT = {
  CANCELLED: "This order was cancelled.",
  REFUNDED: "This order was refunded.",
};

export default function StatusTimeline({ status }) {
  if (Object.hasOwn(TERMINAL_TEXT, status)) {
    return (
      <div className={`status-timeline-banner status-timeline-banner--${status.toLowerCase()}`} role="status">
        <strong>{statusLabel(status)}</strong>
        <span>{TERMINAL_TEXT[status]}</span>
      </div>
    );
  }

  const currentIndex = LIFECYCLE.indexOf(status);

  return (
    <ol className="status-timeline" aria-label="Order progress">
      {LIFECYCLE.map((step, index) => {
        const state = currentIndex < 0 || index > currentIndex ? "upcoming" : index < currentIndex ? "completed" : "current";
        const stateText = { completed: "Completed", current: "Current step", upcoming: "Upcoming" }[state];
        return (
          <li
            key={step}
            className={`status-timeline-step status-timeline-step--${state}`}
            data-step={step}
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="status-timeline-marker" aria-hidden="true">
              {state === "completed" ? "✓" : index + 1}
            </span>
            <span className="status-timeline-label">{statusLabel(step)}</span>
            <span className="status-timeline-state">{stateText}</span>
          </li>
        );
      })}
    </ol>
  );
}
