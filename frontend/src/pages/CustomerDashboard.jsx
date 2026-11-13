// Customer dashboard (Requirements 13.4, 24.1, 24.4, 24.5, 24.6, 27.5, 33.2, 33.3).
// Lists the signed-in customer's orders for the current page in two sections (current and
// previous), with status/date filters, status badges, a cancel action for PLACED orders, links
// to the order detail page for reviews and return requests, and pagination.
import { useState } from "react";
import { Link } from "react-router-dom";
import { cancelOrder, listMyOrders } from "../api/orders.js";
import { getErrorMessage } from "../api/client.js";
import useAsync from "../hooks/useAsync.js";
import OrderFilters from "../components/OrderFilters.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import Loader from "../components/Loader.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import Pagination from "../components/Pagination.jsx";
import { canCancel, canRequestReturn, canReview, partitionOrders } from "../utils/orderStatus.js";
import { formatCurrency, formatDate } from "../utils/format.js";
import "../styles/pages/CustomerDashboard.css";

const PAGE_SIZE = 10;
const NO_FILTERS = { status: "", date_from: "", date_to: "" };
const CANCEL_CONFIRMATION = "Cancel this order? This cannot be undone.";

/** Restaurant name from whichever shape the Backend sends (`restaurant_name`, object, or string). */
function restaurantName(order) {
  if (order.restaurant_name) return order.restaurant_name;
  const restaurant = order.restaurant;
  if (typeof restaurant === "string") return restaurant;
  return restaurant?.name ?? "";
}

function OrderCard({ order, cancelling, onCancel }) {
  const name = restaurantName(order);
  return (
    <li className="dashboard-order">
      <article className="dashboard-order-card" aria-label={`Order #${order.id}`}>
        <header className="dashboard-order-header">
          <h3 className="dashboard-order-title">Order #{order.id}</h3>
          <span className="dashboard-order-total">{formatCurrency(order.total_amount)}</span>
        </header>
        <p className="dashboard-order-meta text-muted">
          {name && <span className="dashboard-order-restaurant">{name}</span>}
          <span className="dashboard-order-date">Placed {formatDate(order.created_at)}</span>
        </p>
        <ul className="dashboard-order-badges" aria-label="Order status">
          <li>
            <span className="dashboard-badge-label">Order</span>
            <StatusBadge type="order" status={order.status} />
          </li>
          <li>
            <span className="dashboard-badge-label">Payment</span>
            <StatusBadge type="payment" status={order.payment_status} />
          </li>
          <li>
            <span className="dashboard-badge-label">Return</span>
            <StatusBadge type="return" status={order.return_status} />
          </li>
        </ul>
        <div className="dashboard-order-actions">
          <Link to={`/orders/${order.id}`} className="btn btn-secondary btn-sm">
            View details
          </Link>
          {canReview(order) && (
            <Link to={`/orders/${order.id}`} className="btn btn-link btn-sm">
              Add review
            </Link>
          )}
          {canRequestReturn(order) && (
            <Link to={`/orders/${order.id}`} className="btn btn-link btn-sm">
              Request return
            </Link>
          )}
          {canCancel(order) && (
            <button
              type="button"
              className="btn btn-danger btn-sm"
              disabled={cancelling}
              onClick={() => onCancel(order)}
            >
              {cancelling ? "Cancelling..." : "Cancel order"}
            </button>
          )}
        </div>
      </article>
    </li>
  );
}

function OrderSection({ title, orders, emptyText, cancellingId, onCancel }) {
  return (
    <section className="dashboard-section" aria-label={title}>
      <h2 className="dashboard-section-title">{title}</h2>
      {orders.length === 0 ? (
        <p className="empty-state text-muted">{emptyText}</p>
      ) : (
        <ul className="dashboard-order-list">
          {orders.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              cancelling={cancellingId === order.id}
              onCancel={onCancel}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

export default function CustomerDashboard() {
  // Filters and page live together so any filter change starts again at page 1.
  const [query, setQuery] = useState({ filters: NO_FILTERS, page: 1 });
  const [cancellingId, setCancellingId] = useState(null);
  const [cancelError, setCancelError] = useState("");
  const { filters, page } = query;

  const { data, loading, error, reload } = useAsync(
    () =>
      listMyOrders({
        status: filters.status,
        date_from: filters.date_from,
        date_to: filters.date_to,
        page,
        page_size: PAGE_SIZE,
      }),
    [filters.status, filters.date_from, filters.date_to, page]
  );

  const hasFilters = Boolean(filters.status || filters.date_from || filters.date_to);
  const { current, previous } = partitionOrders(data?.items ?? []);

  async function handleCancel(order) {
    if (!window.confirm(CANCEL_CONFIRMATION)) return;
    setCancelError("");
    setCancellingId(order.id);
    try {
      await cancelOrder(order.id);
    } catch (err) {
      setCancelError(getErrorMessage(err));
    } finally {
      setCancellingId(null);
    }
    // Reload either way: after a 409 the order's status has changed on the Backend.
    reload();
  }

  return (
    <main className="container customer-dashboard-page">
      <h1 className="page-title">My orders</h1>

      <OrderFilters
        value={filters}
        onChange={(next) => setQuery({ filters: next, page: 1 })}
        onReset={() => setQuery({ filters: NO_FILTERS, page: 1 })}
      />

      {cancelError && <ErrorMessage message={cancelError} />}

      {loading && <Loader label="Loading your orders..." />}
      {!loading && error && <ErrorMessage message={error} onRetry={reload} />}
      {!loading && !error && data && (
        <>
          <OrderSection
            title="Current orders"
            orders={current}
            emptyText={hasFilters ? "No current orders match these filters." : "You have no current orders."}
            cancellingId={cancellingId}
            onCancel={handleCancel}
          />
          <OrderSection
            title="Previous orders"
            orders={previous}
            emptyText={hasFilters ? "No previous orders match these filters." : "You have no previous orders."}
            cancellingId={cancellingId}
            onCancel={handleCancel}
          />
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={(next) => setQuery((prev) => ({ ...prev, page: next }))}
          />
        </>
      )}
    </main>
  );
}
