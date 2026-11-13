// OrderDetail: one of the Customer's own Orders (Requirements 12.4, 12.5, 12.6, 13.4, 14.5,
// 15.5, 23.4). Route: `/orders/:id` (wired in task 14.6).
// - Status timeline, restaurant, items table, total, payment/return badges, delivery details,
//   Payment_Ledger entries (PAYMENT and REFUND), assigned Delivery_Partner name when present.
// - Refresh reloads the Order; Cancel is offered while the Order is `PLACED`.
// - "Add review" and "Request return" open the modals when the Order allows them.
// - Unknown or foreign Order ids (HTTP 404) render a friendly "Order not found" message.
// Field names are read defensively because optional parts of the detail payload may be absent.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getErrorMessage, getErrorStatus } from "../api/client.js";
import { cancelOrder, getOrder } from "../api/orders.js";
import ErrorMessage from "../components/ErrorMessage.jsx";
import Loader from "../components/Loader.jsx";
import ReturnRequestModal from "../components/ReturnRequestModal.jsx";
import ReviewModal from "../components/ReviewModal.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import StatusTimeline from "../components/StatusTimeline.jsx";
import useAsync from "../hooks/useAsync.js";
import { formatCurrency, formatDateTime } from "../utils/format.js";
import { canCancel, canRequestReturn, canReview } from "../utils/orderStatus.js";
import "../styles/pages/OrderDetail.css";

const NOT_FOUND = Object.freeze({ notFound: true });
const DASHBOARD_PATH = "/customer/dashboard";

const RETURN_TEXT = {
  requested: "Your return request is waiting for the restaurant's decision.",
  approved: "Your return was approved and the amount was refunded.",
  rejected: "Your return request was rejected.",
};

const LEDGER_LABEL = { PAYMENT: "Payment", REFUND: "Refund" };

const firstDefined = (...values) => values.find((value) => value !== undefined && value !== null);

function getItems(order) {
  return Array.isArray(order.items) ? order.items : [];
}

function getLedger(order) {
  const entries = firstDefined(order.ledger_entries, order.ledger, order.payment_ledger, order.payments);
  return Array.isArray(entries) ? entries : [];
}

function getPartnerName(order) {
  const name = firstDefined(
    order.delivery_partner_name,
    order.partner_name,
    order.delivery_partner?.name,
    order.partner?.name
  );
  return typeof name === "string" && name.trim() !== "" ? name : null;
}

function getRestaurantName(order) {
  return firstDefined(order.restaurant?.name, order.restaurant_name);
}

function getLineTotal(item) {
  const total = firstDefined(item.line_total, item.total);
  if (total !== undefined) return total;
  const price = Number(firstDefined(item.unit_price, item.price));
  const quantity = Number(firstDefined(item.quantity, item.qty));
  return Number.isFinite(price) && Number.isFinite(quantity) ? price * quantity : null;
}

function Stars({ rating }) {
  const value = Math.max(0, Math.min(5, Number(rating) || 0));
  return (
    <span className="order-review-stars">
      <span aria-hidden="true">
        {"\u2605".repeat(value)}
        {"\u2606".repeat(5 - value)}
      </span>
      <span className="visually-hidden">{value} out of 5 stars</span>
    </span>
  );
}

export default function OrderDetail() {
  const { id } = useParams();
  const { data, loading, error, reload } = useAsync(
    () =>
      getOrder(id).catch((err) => {
        if (getErrorStatus(err) === 404) return NOT_FOUND;
        throw err;
      }),
    [id]
  );
  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [modal, setModal] = useState(null); // "review" | "return" | null

  if (loading) return <Loader label="Loading order..." />;

  if (error) {
    return (
      <main className="order-detail-page">
        <ErrorMessage message={error} onRetry={reload} />
        <p>
          <Link to={DASHBOARD_PATH}>Back to my orders</Link>
        </p>
      </main>
    );
  }

  if (!data || data === NOT_FOUND) {
    return (
      <main className="order-detail-page">
        <section className="order-not-found" aria-labelledby="order-not-found-title">
          <h1 id="order-not-found-title" className="page-title">
            Order not found
          </h1>
          <p className="text-muted">This order does not exist or does not belong to your account.</p>
          <Link to={DASHBOARD_PATH} className="btn">
            Back to my orders
          </Link>
        </section>
      </main>
    );
  }

  const order = data;
  const items = getItems(order);
  const ledger = getLedger(order);
  const partnerName = getPartnerName(order);
  const restaurantName = getRestaurantName(order);
  const total = firstDefined(order.total_amount, order.total);
  const returnStatus = order.return_status ?? "none";

  const handleCancel = async () => {
    if (cancelling) return;
    if (!window.confirm("Cancel this order? This cannot be undone.")) return;
    setCancelling(true);
    setActionError(null);
    setNotice(null);
    try {
      await cancelOrder(order.id);
      setNotice("Your order was cancelled.");
      reload();
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setCancelling(false);
    }
  };

  const handleRefresh = () => {
    setActionError(null);
    setNotice(null);
    reload();
  };

  const handleModalSuccess = (message) => {
    setModal(null);
    setActionError(null);
    setNotice(message);
    reload();
  };

  return (
    <main className="order-detail-page">
      <p className="order-detail-back">
        <Link to={DASHBOARD_PATH}>&larr; Back to my orders</Link>
      </p>

      <header className="order-detail-header">
        <div>
          <h1 className="page-title">Order #{order.id}</h1>
          <p className="text-muted">
            {restaurantName ? `${restaurantName} · ` : ""}Placed {formatDateTime(order.created_at)}
          </p>
        </div>
        <div className="order-detail-badges">
          <StatusBadge status={order.status} />
          <StatusBadge type="payment" status={order.payment_status} />
          <StatusBadge type="return" status={returnStatus} />
        </div>
      </header>

      {notice && (
        <p className="order-notice" role="status">
          {notice}
        </p>
      )}
      {actionError && <ErrorMessage message={actionError} />}

      <div className="order-detail-actions">
        <button type="button" className="btn btn-secondary" onClick={handleRefresh}>
          Refresh
        </button>
        {canCancel(order) && (
          <button type="button" className="btn btn-danger" onClick={handleCancel} disabled={cancelling}>
            {cancelling ? "Cancelling..." : "Cancel order"}
          </button>
        )}
        {canReview(order) && (
          <button type="button" className="btn" onClick={() => setModal("review")}>
            Add review
          </button>
        )}
        {canRequestReturn(order) && (
          <button type="button" className="btn btn-secondary" onClick={() => setModal("return")}>
            Request return
          </button>
        )}
      </div>

      <section className="order-section" aria-labelledby="order-progress-title">
        <h2 id="order-progress-title" className="order-section-title">
          Progress
        </h2>
        <StatusTimeline status={order.status} />
        <dl className="order-facts">
          <div>
            <dt>Last update</dt>
            <dd>{formatDateTime(order.status_updated_at)}</dd>
          </div>
          {order.delivered_at && (
            <div>
              <dt>Delivered</dt>
              <dd>{formatDateTime(order.delivered_at)}</dd>
            </div>
          )}
          {partnerName && (
            <div>
              <dt>Delivery partner</dt>
              <dd>{partnerName}</dd>
            </div>
          )}
        </dl>
      </section>

      <section className="order-section" aria-labelledby="order-items-title">
        <h2 id="order-items-title" className="order-section-title">
          Items
        </h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col" className="num">
                  Price
                </th>
                <th scope="col" className="num">
                  Qty
                </th>
                <th scope="col" className="num">
                  Line total
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => (
                <tr key={item.id ?? index}>
                  <td>{item.name}</td>
                  <td className="num">{formatCurrency(firstDefined(item.unit_price, item.price))}</td>
                  <td className="num">{firstDefined(item.quantity, item.qty)}</td>
                  <td className="num">{formatCurrency(getLineTotal(item))}</td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-muted">
                    No items.
                  </td>
                </tr>
              )}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" colSpan={3}>
                  Total
                </th>
                <td className="num order-total">{formatCurrency(total)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section className="order-section" aria-labelledby="order-delivery-title">
        <h2 id="order-delivery-title" className="order-section-title">
          Delivery
        </h2>
        <dl className="order-facts">
          <div>
            <dt>Address</dt>
            <dd>{order.delivery_address || "—"}</dd>
          </div>
          <div>
            <dt>Phone</dt>
            <dd>{order.delivery_phone || "—"}</dd>
          </div>
        </dl>
      </section>

      <section className="order-section" aria-labelledby="order-ledger-title">
        <h2 id="order-ledger-title" className="order-section-title">
          Payment history
        </h2>
        {ledger.length === 0 ? (
          <p className="text-muted">No payment entries.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Type</th>
                  <th scope="col" className="num">
                    Amount
                  </th>
                  <th scope="col">Reference</th>
                  <th scope="col">Card</th>
                  <th scope="col">Date</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((entry, index) => {
                  const type = firstDefined(entry.entry_type, entry.type);
                  return (
                    <tr key={entry.id ?? entry.transaction_ref ?? index} data-entry-type={type}>
                      <td>{LEDGER_LABEL[type] ?? type}</td>
                      <td className="num">{formatCurrency(entry.amount)}</td>
                      <td>{entry.transaction_ref || "—"}</td>
                      <td>{entry.card_last4 ? `•••• ${entry.card_last4}` : "—"}</td>
                      <td>{formatDateTime(entry.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {returnStatus !== "none" && (
        <section className="order-section" aria-labelledby="order-return-title">
          <h2 id="order-return-title" className="order-section-title">
            Return request
          </h2>
          <p>
            <StatusBadge type="return" status={returnStatus} />{" "}
            <span>{RETURN_TEXT[returnStatus]}</span>
          </p>
          {order.return_reason && (
            <p className="order-quote">
              <span className="text-muted">Your reason: </span>
              {order.return_reason}
            </p>
          )}
        </section>
      )}

      {order.review && (
        <section className="order-section" aria-labelledby="order-review-title">
          <h2 id="order-review-title" className="order-section-title">
            Your review
          </h2>
          <p>
            <Stars rating={order.review.rating} />
          </p>
          {order.review.comment ? (
            <p className="order-quote">{order.review.comment}</p>
          ) : (
            <p className="text-muted">No comment.</p>
          )}
        </section>
      )}

      {modal === "review" && (
        <ReviewModal
          orderId={order.id}
          onClose={() => setModal(null)}
          onSubmitted={() => handleModalSuccess("Thanks! Your review was submitted.")}
        />
      )}
      {modal === "return" && (
        <ReturnRequestModal
          orderId={order.id}
          onClose={() => setModal(null)}
          onSubmitted={() => handleModalSuccess("Your return request was submitted.")}
        />
      )}
    </main>
  );
}
