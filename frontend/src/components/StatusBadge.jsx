// StatusBadge: colored label for an Order_Status, Payment_Status, or Return_Status.
//   <StatusBadge status={order.status} />
//   <StatusBadge type="payment" status={order.payment_status} />
//   <StatusBadge type="return" status={order.return_status} />
// `type` is optional: the value sets do not overlap (Order_Status is upper case, Payment_Status
// and Return_Status are lower case), so it is inferred when omitted. The status text is always
// shown, so color is never the only signal.

// Color families (see components.css): info, progress, transit, success, danger, neutral.
const TONES = {
  order: {
    PLACED: "info",
    ACCEPTED: "info",
    PREPARING: "progress",
    READY: "progress",
    ASSIGNED: "transit",
    OUT_FOR_DELIVERY: "transit",
    DELIVERED: "success",
    CANCELLED: "danger",
    REFUNDED: "neutral",
  },
  payment: {
    pending: "progress",
    mock_paid: "success",
    refunded: "neutral",
  },
  return: {
    none: "neutral",
    requested: "progress",
    approved: "success",
    rejected: "danger",
  },
};

const LABEL_OVERRIDES = {
  return: { none: "No return" },
};

function inferType(status) {
  return Object.keys(TONES).find((type) => Object.hasOwn(TONES[type], status)) ?? null;
}

/** Color family for a status value; `neutral` when the value is not a known status. */
export function statusTone(status, type = inferType(status)) {
  return (type && TONES[type]?.[status]) || "neutral";
}

/** Human-readable text: `OUT_FOR_DELIVERY` -> "Out for delivery", `mock_paid` -> "Mock paid". */
export function statusLabel(status, type = inferType(status)) {
  const override = type && LABEL_OVERRIDES[type]?.[status];
  if (override) return override;
  const words = String(status).replaceAll("_", " ").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export default function StatusBadge({ status, type }) {
  if (status === undefined || status === null || status === "") return null;
  const resolvedType = type ?? inferType(status);
  return (
    <span
      className={`badge badge-${statusTone(status, resolvedType)}`}
      data-status={status}
      data-status-type={resolvedType ?? undefined}
    >
      {statusLabel(status, resolvedType)}
    </span>
  );
}
