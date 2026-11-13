// Owner dashboard (Requirements 19.4, 20.5, 25.1, 25.2, 25.4, 31.10).
// Shows restaurant statistics, unresolved reminders, pending return requests, and recent
// incoming orders. Each section loads independently, so a failing section shows its own
// error and leaves the others intact. The Refresh button reloads every section.
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  approveReturn,
  getOwnerStats,
  listOwnerOrders,
  listReminders,
  listReturns,
  rejectReturn,
  resolveReminder,
} from "../api/owner.js";
import { getErrorMessage } from "../api/client.js";
import useAsync from "../hooks/useAsync.js";
import StatusBadge from "../components/StatusBadge.jsx";
import Loader from "../components/Loader.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import { ALL_STATUSES } from "../utils/orderStatus.js";
import { formatCurrency, formatDateTime } from "../utils/format.js";
import "../styles/pages/OwnerDashboard.css";

const LIST_SIZE = 20;
const RECENT_SIZE = 5;
const TOP_DISH_LIMIT = 5;

/** First value in `keys` that is present on `obj`, else `fallback`. */
function pick(obj, keys, fallback = undefined) {
  for (const key of keys) {
    if (obj?.[key] !== undefined) return obj[key];
  }
  return fallback;
}

/** Rows from a paged response (`{items}`) or a plain array. */
const itemsOf = (data) => (Array.isArray(data) ? data : data?.items ?? []);

/** Per-status counts for every Order_Status (0 when absent), from an object or a list. */
function statusCounts(raw) {
  const counts = Object.fromEntries(ALL_STATUSES.map((status) => [status, 0]));
  if (Array.isArray(raw)) {
    raw.forEach((row) => {
      if (row && Object.hasOwn(counts, row.status)) counts[row.status] = Number(row.count) || 0;
    });
  } else if (raw && typeof raw === "object") {
    ALL_STATUSES.forEach((status) => {
      counts[status] = Number(raw[status]) || 0;
    });
  }
  return counts;
}

function normalizeTopDishes(raw) {
  return (Array.isArray(raw) ? raw : [])
    .map((dish) => ({
      name: pick(dish, ["name", "item_name", "menu_item_name"], "Unnamed dish"),
      quantity: Number(pick(dish, ["quantity", "total_quantity"], 0)) || 0,
    }))
    .slice(0, TOP_DISH_LIMIT);
}

function StatCard({ label, value }) {
  return (
    <li className="owner-stat-card">
      <span className="owner-stat-label">{label}</span>
      <span className="owner-stat-value">{value}</span>
    </li>
  );
}

function SectionBody({ state, children }) {
  if (state.loading) return <Loader label="Loading..." />;
  if (state.error) return <ErrorMessage message={state.error} onRetry={state.reload} />;
  return children;
}

function StatsSection({ state }) {
  const stats = state.data ?? {};
  const total = pick(stats, ["total_orders", "total"], 0);
  const today = pick(stats, ["orders_today", "today_orders", "today"], 0);
  const revenue = pick(stats, ["net_revenue", "revenue"], 0);
  const rating = pick(stats, ["average_rating", "avg_rating"], null);
  const counts = statusCounts(pick(stats, ["status_counts", "orders_by_status", "per_status"], {}));
  const topDishes = normalizeTopDishes(pick(stats, ["top_dishes", "top_items"], []));
  const hasRating = rating !== null && rating !== undefined && Number.isFinite(Number(rating));

  return (
    <section className="owner-section" aria-labelledby="owner-stats-heading">
      <h2 id="owner-stats-heading" className="owner-section-title">
        Statistics
      </h2>
      <SectionBody state={state}>
        <ul className="owner-stat-cards" aria-label="Summary">
          <StatCard label="Total orders" value={total} />
          <StatCard label="Today's orders" value={today} />
          <StatCard label="Net revenue" value={formatCurrency(revenue)} />
          <StatCard
            label="Average rating"
            value={hasRating ? `${Number(rating).toFixed(1)} / 5` : "No ratings yet"}
          />
        </ul>

        <div className="owner-stats-columns">
          <div>
            <h3 className="owner-subtitle">Orders by status</h3>
            <ul className="owner-status-counts" aria-label="Orders by status">
              {ALL_STATUSES.map((status) => (
                <li key={status} data-status={status}>
                  <StatusBadge type="order" status={status} />
                  <span className="owner-status-count">{counts[status]}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="owner-subtitle">Top dishes</h3>
            {topDishes.length === 0 ? (
              <p className="text-muted">No dishes ordered yet.</p>
            ) : (
              <ol className="owner-top-dishes">
                {topDishes.map((dish, index) => (
                  <li key={`${dish.name}-${index}`}>
                    <span className="owner-dish-name">{dish.name}</span>
                    <span className="owner-dish-qty text-muted">{dish.quantity} sold</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </SectionBody>
    </section>
  );
}

function RemindersSection({ state, onAnnounce }) {
  const [removed, setRemoved] = useState(() => new Set());
  const [busyId, setBusyId] = useState(null);
  const [actionError, setActionError] = useState("");

  async function handleResolve(reminder) {
    setActionError("");
    setBusyId(reminder.id);
    try {
      await resolveReminder(reminder.id);
      setRemoved((prev) => new Set(prev).add(reminder.id));
      onAnnounce(`Reminder for order #${reminder.order_id} resolved.`);
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  const reminders = itemsOf(state.data).filter((r) => !removed.has(r.id));

  return (
    <section className="owner-section" aria-labelledby="owner-reminders-heading">
      <h2 id="owner-reminders-heading" className="owner-section-title">
        Reminders
      </h2>
      <SectionBody state={state}>
        {actionError && <ErrorMessage message={actionError} />}
        <div aria-live="polite">
          {reminders.length === 0 ? (
            <p className="empty-state text-muted">No unresolved reminders.</p>
          ) : (
            <ul className="owner-reminder-list">
              {reminders.map((reminder) => (
                <li key={reminder.id} className="owner-reminder">
                  <div className="owner-reminder-info">
                    <Link to="/owner/orders" className="owner-reminder-order">
                      Order #{reminder.order_id}
                    </Link>
                    <span className="owner-reminder-status">
                      <span className="text-muted">Stuck at</span>{" "}
                      <StatusBadge type="order" status={reminder.status_at_reminder} />
                    </span>
                    <span className="text-muted owner-reminder-date">
                      {formatDateTime(reminder.created_at)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={busyId === reminder.id}
                    onClick={() => handleResolve(reminder)}
                  >
                    {busyId === reminder.id ? "Resolving..." : "Resolve"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </SectionBody>
    </section>
  );
}

const returnId = (ret) => pick(ret, ["order_id", "id"]);

function ReturnsSection({ state, onAnnounce }) {
  const [removed, setRemoved] = useState(() => new Set());
  const [busy, setBusy] = useState(null); // `${orderId}:approve|reject`
  const [actionError, setActionError] = useState("");

  async function decide(ret, kind) {
    const orderId = returnId(ret);
    const approving = kind === "approve";
    const question = approving
      ? `Approve the return for order #${orderId} and refund ${formatCurrency(ret.total_amount)}?`
      : `Reject the return request for order #${orderId}?`;
    if (!window.confirm(question)) return;
    setActionError("");
    setBusy(`${orderId}:${kind}`);
    try {
      await (approving ? approveReturn : rejectReturn)(orderId);
      setRemoved((prev) => new Set(prev).add(orderId));
      onAnnounce(`Return for order #${orderId} ${approving ? "approved" : "rejected"}.`);
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  const returns = itemsOf(state.data).filter((r) => !removed.has(returnId(r)));

  return (
    <section className="owner-section" aria-labelledby="owner-returns-heading">
      <h2 id="owner-returns-heading" className="owner-section-title">
        Pending returns
      </h2>
      <SectionBody state={state}>
        {actionError && <ErrorMessage message={actionError} />}
        <div aria-live="polite">
          {returns.length === 0 ? (
            <p className="empty-state text-muted">No pending return requests.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <caption className="visually-hidden">Pending return requests</caption>
                <thead>
                  <tr>
                    <th scope="col">Order</th>
                    <th scope="col">Reason</th>
                    <th scope="col">Total</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {returns.map((ret) => {
                    const orderId = returnId(ret);
                    const rowBusy = busy?.startsWith(`${orderId}:`);
                    return (
                      <tr key={orderId}>
                        <td>#{orderId}</td>
                        <td className="owner-return-reason">
                          {pick(ret, ["reason", "return_reason"], "")}
                        </td>
                        <td>{formatCurrency(ret.total_amount)}</td>
                        <td>
                          <div className="owner-row-actions">
                            <button
                              type="button"
                              className="btn btn-sm"
                              disabled={rowBusy}
                              onClick={() => decide(ret, "approve")}
                            >
                              {busy === `${orderId}:approve` ? "Approving..." : "Approve"}
                            </button>
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              disabled={rowBusy}
                              onClick={() => decide(ret, "reject")}
                            >
                              {busy === `${orderId}:reject` ? "Rejecting..." : "Reject"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </SectionBody>
    </section>
  );
}

function RecentOrdersSection({ state }) {
  const orders = itemsOf(state.data);
  return (
    <section className="owner-section" aria-labelledby="owner-orders-heading">
      <h2 id="owner-orders-heading" className="owner-section-title">
        Recent incoming orders
      </h2>
      <SectionBody state={state}>
        {orders.length === 0 ? (
          <p className="empty-state text-muted">No new orders waiting.</p>
        ) : (
          <ul className="owner-order-list">
            {orders.map((order) => (
              <li key={order.id} className="owner-order">
                <span className="owner-order-id">Order #{order.id}</span>
                <StatusBadge type="order" status={order.status} />
                <span className="owner-order-total">{formatCurrency(order.total_amount)}</span>
                <span className="text-muted owner-order-date">{formatDateTime(order.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="owner-section-footer">
          <Link to="/owner/orders">Manage all orders</Link>
        </p>
      </SectionBody>
    </section>
  );
}

export default function OwnerDashboard() {
  const [announcement, setAnnouncement] = useState("");

  const stats = useAsync(() => getOwnerStats(), []);
  const reminders = useAsync(() => listReminders({ resolved: false, page: 1, page_size: LIST_SIZE }), []);
  const returns = useAsync(() => listReturns({ status: "requested", page: 1, page_size: LIST_SIZE }), []);
  const orders = useAsync(
    () => listOwnerOrders({ status: "PLACED", page: 1, page_size: RECENT_SIZE }),
    []
  );

  const refreshing = stats.loading || reminders.loading || returns.loading || orders.loading;

  function refresh() {
    setAnnouncement("");
    stats.reload();
    reminders.reload();
    returns.reload();
    orders.reload();
  }

  return (
    <main className="container owner-dashboard-page">
      <header className="owner-dashboard-header">
        <h1 className="page-title">Owner dashboard</h1>
        <div className="owner-dashboard-actions">
          <Link to="/owner/menu" className="btn btn-secondary btn-sm">
            Manage menu
          </Link>
          <Link to="/owner/orders" className="btn btn-secondary btn-sm">
            Manage orders
          </Link>
          <button type="button" className="btn btn-sm" disabled={refreshing} onClick={refresh}>
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      <p className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>

      <StatsSection state={stats} />
      <RemindersSection state={reminders} onAnnounce={setAnnouncement} />
      <ReturnsSection state={returns} onAnnounce={setAnnouncement} />
      <RecentOrdersSection state={orders} />
    </main>
  );
}
