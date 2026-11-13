import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getOrder, requestReturn } from "../api/orders.js";
import OrderDetail from "../pages/OrderDetail";

// Requirements 12.4, 12.5, 13.4: detail page actions, ledger and modal validation.

vi.mock("../api/orders.js", () => ({
  getOrder: vi.fn(),
  cancelOrder: vi.fn(),
  submitReview: vi.fn(),
  requestReturn: vi.fn(),
}));

const base = {
  id: 9,
  status: "DELIVERED",
  payment_status: "paid",
  return_status: "none",
  total_amount: "80.00",
  created_at: "2024-01-01T10:00:00Z",
  items: [],
  review: null,
};

function renderPage(order) {
  getOrder.mockResolvedValue({ ...base, ...order });
  return render(
    <MemoryRouter initialEntries={["/orders/9"]}>
      <Routes>
        <Route path="/orders/:id" element={<OrderDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => vi.clearAllMocks());

describe("OrderDetail", () => {
  it("offers review and return for a delivered order", async () => {
    renderPage({});
    expect(await screen.findByRole("button", { name: "Add review" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request return" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel order" })).toBeNull();
  });

  it("hides review when a review exists and return when already requested", async () => {
    renderPage({ review: { rating: 4, comment: "Nice" }, return_status: "requested", return_reason: "cold" });
    await screen.findByText("Your review");
    expect(screen.queryByRole("button", { name: "Add review" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Request return" })).toBeNull();
  });

  it("hides review and return for non-delivered orders and offers cancel for PLACED", async () => {
    renderPage({ status: "PLACED" });
    expect(await screen.findByRole("button", { name: "Cancel order" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add review" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Request return" })).toBeNull();
  });

  it("shows ledger entries", async () => {
    renderPage({
      ledger_entries: [
        { id: 1, entry_type: "PAYMENT", amount: "80.00", transaction_ref: "TX-1", card_last4: "4242", created_at: "2024-01-01T10:00:00Z" },
        { id: 2, entry_type: "REFUND", amount: "80.00", transaction_ref: "TX-2", card_last4: "4242", created_at: "2024-01-02T10:00:00Z" },
      ],
    });
    expect(await screen.findByText("TX-1")).toBeInTheDocument();
    expect(screen.getByText("TX-2")).toBeInTheDocument();
    expect(screen.getByText("Payment")).toBeInTheDocument();
    expect(screen.getByText("Refund")).toBeInTheDocument();
  });

  it("validates the return reason before submitting", async () => {
    renderPage({});
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Request return" }));
    const dialogSubmit = screen.getAllByRole("button", { name: "Request return" }).at(-1);
    await user.click(dialogSubmit);
    expect(await screen.findByText(/explain why/i)).toBeInTheDocument();
    expect(requestReturn).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText(/Reason for return/), "abc");
    expect(await screen.findByText(/at least 5 characters/)).toBeInTheDocument();
    expect(requestReturn).not.toHaveBeenCalled();
  });
});
