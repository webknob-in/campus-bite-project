// OrderFilters: status select plus date from/to (Requirements 14, 24.4).
//   <OrderFilters value={{status, date_from, date_to}} onChange={setFilters} onReset={clear} />
// `onChange` receives the full next value object. A date range with from > to is never sent:
// the dates are kept as a local draft, an inline error is shown, and `onChange` is not called
// until the range is valid again (the Backend returns 422 for an inverted range).
import { useState } from "react";
import FormField from "./FormField.jsx";
import { statusLabel } from "./StatusBadge.jsx";
import { ALL_STATUSES } from "../utils/orderStatus.js";
import "../styles/pages/OrderFilters.css";

export const RANGE_ERROR = "From date must be on or before the To date.";

/** True when both ISO dates (YYYY-MM-DD) are set and `from` is after `to`. */
export const isInvalidRange = (from, to) => Boolean(from) && Boolean(to) && from > to;

export default function OrderFilters({ value, onChange, onReset }) {
  const status = value?.status ?? "";
  const committedFrom = value?.date_from ?? "";
  const committedTo = value?.date_to ?? "";

  const [draft, setDraft] = useState({ date_from: committedFrom, date_to: committedTo });
  const [syncedFrom, setSyncedFrom] = useState(committedFrom);
  const [syncedTo, setSyncedTo] = useState(committedTo);

  // Follow the parent when it changes the committed dates (for example after a reset).
  if (syncedFrom !== committedFrom || syncedTo !== committedTo) {
    setSyncedFrom(committedFrom);
    setSyncedTo(committedTo);
    setDraft({ date_from: committedFrom, date_to: committedTo });
  }

  const error = isInvalidRange(draft.date_from, draft.date_to) ? RANGE_ERROR : undefined;

  function handleStatus(event) {
    onChange?.({ status: event.target.value, date_from: committedFrom, date_to: committedTo });
  }

  function handleDate(event) {
    const { name, value: next } = event.target;
    const nextDraft = { ...draft, [name]: next };
    setDraft(nextDraft);
    if (isInvalidRange(nextDraft.date_from, nextDraft.date_to)) return;
    onChange?.({ status, date_from: nextDraft.date_from, date_to: nextDraft.date_to });
  }

  function handleReset() {
    setDraft({ date_from: "", date_to: "" });
    onReset?.();
  }

  return (
    <form className="order-filters" role="search" aria-label="Filter orders" onSubmit={(e) => e.preventDefault()} noValidate>
      <FormField label="Status" as="select" name="status" value={status} onChange={handleStatus}>
        <option value="">All statuses</option>
        {ALL_STATUSES.map((s) => (
          <option key={s} value={s}>
            {statusLabel(s)}
          </option>
        ))}
      </FormField>
      <FormField label="From date" type="date" name="date_from" value={draft.date_from} max={draft.date_to || undefined} onChange={handleDate} error={error} />
      <FormField label="To date" type="date" name="date_to" value={draft.date_to} min={draft.date_from || undefined} onChange={handleDate} />
      {onReset && (
        <div className="order-filters-actions">
          <button type="button" className="btn btn-secondary" onClick={handleReset}>
            Reset filters
          </button>
        </div>
      )}
    </form>
  );
}
