// ReturnRequestModal: reason for a return/refund request on a delivered Order
// (Requirements 15.1, 15.3, 15.5).
//   {open && <ReturnRequestModal orderId={order.id} onClose={close} onSubmitted={handleSubmitted} />}
// - The reason is required; its trimmed length must be 5 to 1000 characters.
// - Backend errors (409 already requested or not delivered, 422, network) are shown inside the modal.
import { useId, useState } from "react";
import { getErrorMessage } from "../api/client.js";
import { requestReturn } from "../api/orders.js";
import ErrorMessage from "./ErrorMessage.jsx";
import FormField from "./FormField.jsx";
import Modal from "./Modal.jsx";
import "../styles/pages/OrderModals.css";

export const MIN_REASON_LENGTH = 5;
export const MAX_REASON_LENGTH = 1000;

/** Returns an error message for an invalid reason, or `null` when it is valid. */
export function validateReason(reason) {
  const length = reason.trim().length;
  if (length === 0) return "Please explain why you are returning this order.";
  if (length < MIN_REASON_LENGTH) return `Reason must be at least ${MIN_REASON_LENGTH} characters.`;
  if (length > MAX_REASON_LENGTH) return `Reason must be at most ${MAX_REASON_LENGTH} characters.`;
  return null;
}

export default function ReturnRequestModal({ orderId, onClose, onSubmitted }) {
  const formId = useId();
  const [reason, setReason] = useState("");
  const [showErrors, setShowErrors] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState(null);

  const error = showErrors ? validateReason(reason) : null;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setShowErrors(true);
    if (validateReason(reason)) return;

    setSubmitting(true);
    setApiError(null);
    try {
      const order = await requestReturn(orderId, reason.trim());
      onSubmitted?.(order);
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
        {submitting ? "Submitting..." : "Request return"}
      </button>
    </>
  );

  return (
    <Modal title="Request return" onClose={onClose} footer={footer}>
      <form id={formId} className="order-modal-form" onSubmit={handleSubmit} noValidate>
        {apiError && <ErrorMessage message={apiError} />}
        <FormField
          as="textarea"
          label="Reason for return"
          name="reason"
          value={reason}
          maxLength={MAX_REASON_LENGTH}
          rows={5}
          required
          disabled={submitting}
          onChange={(event) => setReason(event.target.value)}
          error={error}
          hint={`${reason.length}/${MAX_REASON_LENGTH} characters (at least ${MIN_REASON_LENGTH})`}
        />
      </form>
    </Modal>
  );
}
