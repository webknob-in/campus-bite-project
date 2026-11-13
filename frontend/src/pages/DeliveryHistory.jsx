// Delivery history (Requirement 26.4): paginated delivered orders with delivered time and total.
import { useState } from "react";
import { Link } from "react-router-dom";
import { listPartnerHistory } from "../api/partner.js";
import useAsync from "../hooks/useAsync.js";
import StatusBadge from "../components/StatusBadge.jsx";
import Loader from "../components/Loader.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import Pagination from "../components/Pagination.jsx";
import { formatCurrency, formatDateTime } from "../utils/format.js";
import "../styles/pages/DeliveryHistory.css";

const PAGE_SIZE = 10;

const customerOf = (o) => o.customer_name ?? o.customer?.name ?? "";
const restaurantOf = (o) => o.restaurant_name ?? o.restaurant?.name ?? "";
const deliveredAtOf = (o) => o.delivered_at ?? o.updated_at ?? null;

export default function DeliveryHistory() {
  const [page, setPage] = useState(1);
  const history = useAsync(() => listPartnerHistory({ page, page_size: PAGE_SIZE }), [page]);

  const data = history.data;
  const rows = Array.isArray(data) ? data : data?.items ?? [];

  return (
    <div className="delivery-history">
      <div className="delivery-history-head">
        <h1>Delivery history</h1>
        <Link to="/partner/dashboard">Back to dashboard</Link>
      </div>
      {history.loading && rows.length === 0 ? (
        <Loader />
      ) : history.error ? (
        <ErrorMessage message={history.error} onRetry={history.reload} />
      ) : rows.length === 0 ? (
        <p className="text-muted">No completed deliveries yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="delivery-history-table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Customer</th>
                <th>Restaurant</th>
                <th>Delivery address</th>
                <th>Delivered</th>
                <th>Total</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((o) => (
                <tr key={o.id}>
                  <td>#{o.id}</td>
                  <td>{customerOf(o)}</td>
                  <td>{restaurantOf(o)}</td>
                  <td>{o.delivery_address}</td>
                  <td>{deliveredAtOf(o) ? formatDateTime(deliveredAtOf(o)) : "—"}</td>
                  <td>{formatCurrency(o.total_amount)}</td>
                  <td>
                    <StatusBadge type="order" status={o.status} />
                  </td>
                </tr>
              ))}
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
