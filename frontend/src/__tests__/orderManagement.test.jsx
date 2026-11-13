// Unit tests for owner order management (Requirements 17.6, 18.6).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/owner.js", () => ({
  listOwnerOrders: vi.fn(),
  listDeliveryPartners: vi.fn(),
  updateOwnerOrderStatus: vi.fn(),
  assignDeliveryPartner: vi.fn(),
}));

import {
  assignDeliveryPartner,
  listDeliveryPartners,
  listOwnerOrders,
  updateOwnerOrderStatus,
} from "../api/owner.js";
import OrderManagement from "../pages/OrderManagement.jsx";

const order = (id, status) => ({
  id,
  status,
  customer_name: `Cust${id}`,
  items_summary: "1 × Dosa",
  total_amount: "100.00",
  created_at: "2024-01-01T10:00:00Z",
});

function setup(orders) {
  listOwnerOrders.mockResolvedValue({ items: orders, page: 1, page_size: 10, total: orders.length });
  listDeliveryPartners.mockResolvedValue([{ id: 7, name: "Ravi" }]);
  return render(
    <MemoryRouter>
      <OrderManagement />
    </MemoryRouter>
  );
}

const partnerSelect = () => screen.queryByLabelText(/Delivery partner for order/);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("OrderManagement", () => {
  it.each([
    ["PLACED", "Accept"],
    ["ACCEPTED", "Start preparing"],
    ["PREPARING", "Mark ready"],
  ])("shows the %s action label and no partner select", async (status, label) => {
    setup([order(1, status)]);
    expect(await screen.findByRole("button", { name: label })).toBeInTheDocument();
    expect(partnerSelect()).toBeNull();
  });

  it.each(["ASSIGNED", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED", "REFUNDED"])(
    "shows no action and no select for %s",
    async (status) => {
      setup([order(1, status)]);
      await screen.findByText("#1");
      expect(partnerSelect()).toBeNull();
      expect(screen.queryByRole("button", { name: "Assign" })).toBeNull();
    }
  );

  it("calls updateOwnerOrderStatus with the target status", async () => {
    updateOwnerOrderStatus.mockResolvedValue({});
    setup([order(5, "PLACED")]);
    await userEvent.click(await screen.findByRole("button", { name: "Accept" }));
    expect(updateOwnerOrderStatus).toHaveBeenCalledWith(5, "ACCEPTED");
  });

  it("READY shows partner select and a disabled Assign until chosen, then assigns", async () => {
    assignDeliveryPartner.mockResolvedValue({});
    setup([order(9, "READY")]);
    const select = await screen.findByLabelText("Delivery partner for order 9");
    await screen.findByRole("option", { name: "Ravi" });
    const assign = screen.getByRole("button", { name: "Assign" });
    expect(assign).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
    await userEvent.selectOptions(select, "7");
    expect(assign).toBeEnabled();
    await userEvent.click(assign);
    expect(assignDeliveryPartner).toHaveBeenCalledWith(9, 7);
  });

  it("shows a 409 error inline", async () => {
    updateOwnerOrderStatus.mockRejectedValue({
      response: { status: 409, data: { detail: "Order already updated" } },
    });
    setup([order(3, "PLACED")]);
    await userEvent.click(await screen.findByRole("button", { name: "Accept" }));
    const row = screen.getByText("#3").closest("tr");
    await waitFor(() => expect(within(row).getByRole("alert")).toHaveTextContent("Order already updated"));
  });
});
