// Unit tests for the owner dashboard (Requirements 20.5, 19.4).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/owner.js", () => ({
  getOwnerStats: vi.fn(),
  listReminders: vi.fn(),
  listReturns: vi.fn(),
  listOwnerOrders: vi.fn(),
  approveReturn: vi.fn(),
  rejectReturn: vi.fn(),
  resolveReminder: vi.fn(),
}));

import {
  approveReturn,
  getOwnerStats,
  listOwnerOrders,
  listReminders,
  listReturns,
  rejectReturn,
  resolveReminder,
} from "../api/owner.js";
import OwnerDashboard from "../pages/OwnerDashboard.jsx";

const page = (items) => ({ items, page: 1, page_size: 20, total: items.length });

beforeEach(() => {
  vi.clearAllMocks();
  getOwnerStats.mockResolvedValue({
    total_orders: 3,
    status_counts: { PLACED: 2, DELIVERED: 1 },
    top_dishes: [],
  });
  listReminders.mockResolvedValue(
    page([{ id: 11, order_id: 21, status_at_reminder: "PLACED", created_at: "2024-01-01T10:00:00Z" }])
  );
  listReturns.mockResolvedValue(page([{ order_id: 31, reason: "cold", total_amount: "90.00" }]));
  listOwnerOrders.mockResolvedValue(page([]));
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(() => vi.restoreAllMocks());

const renderPage = () =>
  render(
    <MemoryRouter>
      <OwnerDashboard />
    </MemoryRouter>
  );

describe("OwnerDashboard", () => {
  it("Approve confirms, calls approveReturn and removes the row", async () => {
    approveReturn.mockResolvedValue({});
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(window.confirm).toHaveBeenCalled();
    expect(approveReturn).toHaveBeenCalledWith(31);
    await waitFor(() => expect(screen.queryByText("#31")).toBeNull());
  });

  it("does nothing when the confirmation is declined", async () => {
    window.confirm.mockReturnValue(false);
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(approveReturn).not.toHaveBeenCalled();
    expect(screen.getByText("#31")).toBeInTheDocument();
  });

  it("Reject calls rejectReturn", async () => {
    rejectReturn.mockResolvedValue({});
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
    expect(rejectReturn).toHaveBeenCalledWith(31);
  });

  it("Resolve calls resolveReminder and removes the reminder", async () => {
    resolveReminder.mockResolvedValue({});
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Resolve" }));
    expect(resolveReminder).toHaveBeenCalledWith(11);
    await waitFor(() => expect(screen.queryByText("Order #21")).toBeNull());
  });

  it("a failing stats call does not blank other sections", async () => {
    getOwnerStats.mockRejectedValue({ response: { status: 500, data: {} } });
    renderPage();
    expect(await screen.findByText("#31")).toBeInTheDocument();
    expect(screen.getByText("Order #21")).toBeInTheDocument();
    expect(screen.getByText("Request failed (500)")).toBeInTheDocument();
  });

  it("shows counts for all 9 statuses", async () => {
    renderPage();
    const list = await screen.findByRole("list", { name: "Orders by status" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(9);
    const counts = Object.fromEntries(
      items.map((li) => [li.getAttribute("data-status"), li.querySelector(".owner-status-count").textContent])
    );
    expect(counts.PLACED).toBe("2");
    expect(counts.DELIVERED).toBe("1");
    expect(counts.REFUNDED).toBe("0");
  });
});
