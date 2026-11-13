// Order management for restaurant owners (Requirements 17.6, 18.6, 25.3).
// Filterable, paginated order table with a per-row next-status button and, at READY,
// a delivery partner picker plus Assign button. Backend errors (409/400/404) show inline.
import { useState } from "react";
import {
  assignDeliveryPartner,
  listDeliveryPartners,
  listOwnerOrders,
  updateOwnerOrderStatus,
} from "../api/owner.js";
import { getErrorMessage } from "../api/client.js";
import useAsync from "../hooks/useAsync.js";
import OrderFilters from "../components/OrderFilters.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import Loader from "../components/Loader.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import Pagination from "../components/Pagination.jsx";
import { nextOwnerAction } from "../utils/orderStatus.js";
import { formatCurrency, formatDateTime } from "../utils/format.js";
import "../styles/pages/OrderManagement.css";

const PAGE_SIZE = 10;
const EMPTY_FILTERS = { status: "", date_from: "", date_to: "" };

const customerOf = (o) => o.customer_name ?? o.customer?.name ?? "";
const partnerOf = (o) => o.delivery_partner_name ?? o.delivery_partner?.name ?? "";

function itemsOf(order) {
  if (typeof order.items_summary === "string") return order.items_summary;
  if (Array.isArray(order.items)) {
    return order.items
      .map((i) => `${i.quantity ?? 1} × ${i.name ?? i.menu_item_name ?? i.dish_name ?? ""}`.trim())
      .join(", ");
  }
  return "";
}

function OrderRow({ order, partners, pending, error, onAdvance, onAssign }) {
  const [partnerId, setPartnerId] = useState("");
  const action = nextOwnerAction(order.status);
  const isReady = order.status === "READY";

  return (
    <tr>
      <td>#{order.id}</td>
      <td>{customerOf(order)}</td>
      <td>{itemsOf(order)}</td>
      <td>{formatCurrency(order.total_amount)}</td>
      <td>
        <StatusBadge type="order" status={order.status} />
      </td>
      <td>{partnerOf(order) || "—"}</td>
      <td>{formatDateTime(order.created_at)}</td>
      <td className="order-mgmt-actions">
        {action && (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={pending}
            onClick={() => onAdvance(order, action.target)}
          >
            {action.label}
          </button>
        )}
        {isReady && (
          <span className="order-mgmt-assign">
            <select
              aria-label={`Delivery partner for order ${order.id}`}
              value={partnerId}
              disabled={pending}
              onChange={(e) => setPartnerId(e.target.value)}
            >
              <option value="">Select partner</option>
              {partners.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={pending || partnerId === ""}
              onClick={() => onAssign(order, Number(partnerId))}
            >
              Assign
            </button>
          </span>
        )}
        {error && (
          <p className="order-mgmt-row-error" role="alert">
            {error}
          </p>
        )}
      </td>
    </tr>
  );
}

export default function OrderManagement() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [pendingId, setPendingId] = useState(null);
  const [rowErrors, setRowErrors] = useState({});

  const orders = useAsync(
    () => listOwnerOrders({ ...filters, page, page_size: PAGE_SIZE }),
    [filters.status, filters.date_from, filters.date_to, page]
  );
  const partnerState = useAsync(() => listDeliveryPartners(), []);
  const partners = Array.isArray(partnerState.data)
    ? partnerState.data
    : partnerState.data?.items ?? [];

  function changeFilters(next) {
    setFilters(next);
    setPage(1);
  }

  async function run(order, request) {
    setPendingId(order.id);
    setRowErrors((prev) => ({ ...prev, [order.id]: null }));
    try {
      await request();
      orders.reload();
    } catch (err) {
      setRowErrors((prev) => ({ ...prev, [order.id]: getErrorMessage(err) }));
      if (err?.response?.status === 409) orders.reload();
    } finally {
      setPendingId(null);
    }
  }

  const onAdvance = (order, target) => run(order, () => updateOwnerOrderStatus(order.id, target));
  const onAssign = (order, partnerId) => run(order, () => assignDeliveryPartner(order.id, partnerId));

  const data = orders.data;
  const rows = Array.isArray(data) ? data : data?.items ?? [];

  return (
    <div className="order-mgmt">
      <h1>Manage orders</h1>
      <OrderFilters
        value={filters}
        onChange={changeFilters}
        onReset={() => changeFilters(EMPTY_FILTERS)}
      />
      {orders.loading && rows.length === 0 ? (
        <Loader />
      ) : orders.error ? (
        <ErrorMessage message={orders.error} onRetry={orders.reload} />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Customer</th>
                <th>Items</th>
                <th>Total</th>
                <th>Status</th>
                <th>Partner</th>
                <th>Placed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-muted">
                    No orders found.
                  </td>
                </tr>
              ) : (
                rows.map((order) => (
                  <OrderRow
                    key={order.id}
                    order={order}
                    partners={partners}
                    pending={pendingId === order.id}
                    error={rowErrors[order.id]}
                    onAdvance={onAdvance}
                    onAssign={onAssign}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
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
