// Delivery partner dashboard (Requirements 26.1, 26.2, 26.3).
// Paginated cards of assigned orders with customer/restaurant details and a next-status button.
import { useState } from "react";
import { Link } from "react-router-dom";
import { listPartnerOrders, updatePartnerOrderStatus } from "../api/partner.js";
import { getErrorMessage } from "../api/client.js";
import useAsync from "../hooks/useAsync.js";
import StatusBadge from "../components/StatusBadge.jsx";
import Loader from "../components/Loader.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import Pagination from "../components/Pagination.jsx";
import { nextPartnerAction } from "../utils/orderStatus.js";
import { formatCurrency } from "../utils/format.js";
import "../styles/pages/PartnerDashboard.css";

const PAGE_SIZE = 10;

const customerOf = (o) => o.customer_name ?? o.customer?.name ?? "";
const restaurantOf = (o) => o.restaurant_name ?? o.restaurant?.name ?? "";
const restaurantAddressOf = (o) => o.restaurant_address ?? o.restaurant?.address ?? "";
const phoneOf = (o) => o.delivery_phone ?? o.customer_phone ?? o.customer?.phone ?? "";

function itemsOf(order) {
  if (typeof order.items_summary === "string") return order.items_summary;
  if (Array.isArray(order.items)) {
    return order.items
      .map((i) => `${i.quantity ?? 1} × ${i.name ?? i.menu_item_name ?? i.dish_name ?? ""}`.trim())
      .join(", ");
  }
  return "";
}

function DeliveryCard({ order, pending, error, onAdvance }) {
  const action = nextPartnerAction(order.status);
  const phone = phoneOf(order);
  return (
    <li className="partner-card card">
      <div className="partner-card-head">
        <h2>Order #{order.id}</h2>
        <StatusBadge type="order" status={order.status} />
      </div>
      <p>
        <strong>Customer:</strong> {customerOf(order)}
      </p>
      <p>
        <strong>Phone:</strong> {phone ? <a href={`tel:${phone}`}>{phone}</a> : "—"}
      </p>
      <p>
        <strong>Deliver to:</strong> {order.delivery_address}
      </p>
      <p>
        <strong>Pick up from:</strong> {restaurantOf(order)}
        {restaurantAddressOf(order) ? `, ${restaurantAddressOf(order)}` : ""}
      </p>
      <p className="text-muted">{itemsOf(order)}</p>
      <p>
        <strong>Total:</strong> {formatCurrency(order.total_amount)}
      </p>
      {action && (
        <button
          type="button"
          className="btn btn-primary"
          disabled={pending}
          onClick={() => onAdvance(order, action.target)}
        >
          {action.label}
        </button>
      )}
      {error && (
        <p className="partner-card-error" role="alert">
          {error}
        </p>
      )}
    </li>
  );
}

export default function PartnerDashboard() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [pendingId, setPendingId] = useState(null);
  const [errors, setErrors] = useState({});

  const orders = useAsync(
    () => listPartnerOrders({ status, page, page_size: PAGE_SIZE }),
    [status, page]
  );

  async function onAdvance(order, target) {
    setPendingId(order.id);
    setErrors((prev) => ({ ...prev, [order.id]: null }));
    try {
      await updatePartnerOrderStatus(order.id, target);
      orders.reload();
    } catch (err) {
      setErrors((prev) => ({ ...prev, [order.id]: getErrorMessage(err) }));
      if (err?.response?.status === 409) orders.reload();
    } finally {
      setPendingId(null);
    }
  }

  const data = orders.data;
  const rows = Array.isArray(data) ? data : data?.items ?? [];

  return (
    <div className="partner-dashboard">
      <div className="partner-dashboard-head">
        <h1>My deliveries</h1>
        <Link to="/partner/history">Delivery history</Link>
      </div>
      <label className="partner-filter">
        Status
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All</option>
          <option value="ASSIGNED">Assigned</option>
          <option value="OUT_FOR_DELIVERY">Out for delivery</option>
        </select>
      </label>
      {orders.loading && rows.length === 0 ? (
        <Loader />
      ) : orders.error ? (
        <ErrorMessage message={orders.error} onRetry={orders.reload} />
      ) : rows.length === 0 ? (
        <p className="text-muted">No deliveries assigned.</p>
      ) : (
        <ul className="partner-list">
          {rows.map((order) => (
            <DeliveryCard
              key={order.id}
              order={order}
              pending={pendingId === order.id}
              error={errors[order.id]}
              onAdvance={onAdvance}
            />
          ))}
        </ul>
      )}
      <Pagination
        page={data?.page ?? page}
        pageSize={data?.page_size ?? PAGE_SIZE}
        total={data?.total ?? 0}
        onPageChange={setPage}
      />
    </div>
  );
}
