// ReviewModal: 1-5 star rating and optional comment for a delivered Order
// (Requirements 14.1, 14.5).
//   {open && <ReviewModal orderId={order.id} onClose={close} onSubmitted={handleSubmitted} />}
// - The rating is a native radio group (arrow keys move the selection), so it works with the
//   keyboard and screen readers; the selected stars are filled and also stated as text.
// - Comment is optional, at most 1000 characters, with a live counter.
// - Backend errors (409 duplicate or not eligible, 422, network) are shown inside the modal.
import { useId, useState } from "react";
import { getErrorMessage } from "../api/client.js";
import { submitReview } from "../api/orders.js";
import ErrorMessage from "./ErrorMessage.jsx";
import FormField from "./FormField.jsx";
import Modal from "./Modal.jsx";
import "../styles/pages/OrderModals.css";

export const MAX_COMMENT_LENGTH = 1000;
const STARS = [1, 2, 3, 4, 5];

export function validateReview({ rating, comment }) {
  const errors = {};
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
    errors.rating = "Choose a rating from 1 to 5 stars.";
  }
  if (comment.length > MAX_COMMENT_LENGTH) {
    errors.comment = `Comment must be at most ${MAX_COMMENT_LENGTH} characters.`;
  }
  return errors;
}

export default function ReviewModal({ orderId, onClose, onSubmitted }) {
  const formId = useId();
  const groupName = `${formId}-rating`;
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [showErrors, setShowErrors] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState(null);

  const errors = showErrors ? validateReview({ rating, comment }) : {};

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setShowErrors(true);
    if (Object.keys(validateReview({ rating, comment })).length > 0) return;

    setSubmitting(true);
    setApiError(null);
    const trimmed = comment.trim();
    try {
      const review = await submitReview(orderId, trimmed ? { rating, comment: trimmed } : { rating });
      onSubmitted?.(review);
    } catch (err) {
      setApiError(getErrorMessage(err));
      setSubmitting(false);
    }
  };

  const footer = (
    <>
      <button type="button" className="btn btn-secondary" onClick={() => onClose?.()} disabled={submitting}>
        Cancel
      </button>
      <button type="submit" form={formId} className="btn" disabled={submitting}>
        {submitting ? "Submitting..." : "Submit review"}
      </button>
    </>
  );

  return (
    <Modal title="Add review" onClose={onClose} footer={footer}>
      <form id={formId} className="order-modal-form" onSubmit={handleSubmit} noValidate>
        {apiError && <ErrorMessage message={apiError} />}

        <fieldset className="star-rating" aria-describedby={errors.rating ? `${formId}-rating-error` : undefined}>
          <legend>
            Rating <span className="required-mark" aria-hidden="true">*</span>
            <span className="visually-hidden"> (required)</span>
          </legend>
          <div className="star-rating-options">
            {STARS.map((value) => (
              <label
                key={value}
                className={`star-option${value <= rating ? " star-option--filled" : ""}${value === rating ? " star-option--selected" : ""}`}
              >
                <input
                  type="radio"
                  className="visually-hidden"
                  name={groupName}
                  value={value}
                  checked={rating === value}
                  disabled={submitting}
                  onChange={() => setRating(value)}
                />
                <span className="star-glyph" aria-hidden="true">
                  ★
                </span>
                <span className="visually-hidden">
                  {value} {value === 1 ? "star" : "stars"}
                </span>
              </label>
            ))}
          </div>
          <p className="star-rating-value text-muted" aria-live="polite">
            {rating > 0 ? `${rating} out of 5 selected` : "No rating selected"}
          </p>
          {errors.rating && (
            <p id={`${formId}-rating-error`} className="field-error" role="alert">
              {errors.rating}
            </p>
          )}
        </fieldset>

        <FormField
          as="textarea"
          label="Comment (optional)"
          name="comment"
          value={comment}
          maxLength={MAX_COMMENT_LENGTH}
          rows={4}
          disabled={submitting}
          onChange={(event) => setComment(event.target.value)}
          error={errors.comment}
          hint={`${comment.length}/${MAX_COMMENT_LENGTH} characters`}
        />
      </form>
    </Modal>
  );
}
