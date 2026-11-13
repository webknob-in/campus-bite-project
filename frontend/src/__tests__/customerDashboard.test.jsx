import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { cancelOrder, listMyOrders } from "../api/orders.js";
import CustomerDashboard from "../pages/CustomerDashboard";

// Requirement 13.4: Cancel offered only for PLACED orders.

vi.mock("../api/orders.js", () => ({ listMyOrders: vi.fn(), cancelOrder: vi.fn() }));

const STATUSES = ["PLACED", "ACCEPTED", "PREPARING", "READY", "ASSIGNED", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED", "REFUNDED"];
const order = (id, status) => ({
  id,
  status,
  payment_status: "paid",
  return_status: "none",
  total_amount: "50.00",
  created_at: "2024-01-01T10:00:00Z",
  restaurant_name: "Cafe",
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <CustomerDashboard />
    </MemoryRouter>
  );

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("CustomerDashboard cancel", () => {
  it("shows Cancel only for PLACED orders", async () => {
    listMyOrders.mockResolvedValue({
      items: STATUSES.map((s, i) => order(i + 1, s)),
      total: 9,
      page: 1,
      page_size: 10,
    });
    renderPage();
    await screen.findByRole("article", { name: "Order #1" });
    expect(screen.getAllByRole("button", { name: "Cancel order" })).toHaveLength(1);
    const placed = screen.getByRole("article", { name: "Order #1" });
    expect(placed).toContainElement(screen.getByRole("button", { name: "Cancel order" }));
  });

  it("cancel flow calls cancelOrder and reloads", async () => {
    listMyOrders.mockResolvedValue({ items: [order(7, "PLACED")], total: 1, page: 1, page_size: 10 });
    cancelOrder.mockResolvedValue({});
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Cancel order" }));
    expect(window.confirm).toHaveBeenCalled();
    expect(cancelOrder).toHaveBeenCalledWith(7);
    await vi.waitFor(() => expect(listMyOrders).toHaveBeenCalledTimes(2));
  });

  it("does not cancel when confirmation is declined", async () => {
    window.confirm.mockReturnValue(false);
    listMyOrders.mockResolvedValue({ items: [order(7, "PLACED")], total: 1, page: 1, page_size: 10 });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Cancel order" }));
    expect(cancelOrder).not.toHaveBeenCalled();
  });
});
