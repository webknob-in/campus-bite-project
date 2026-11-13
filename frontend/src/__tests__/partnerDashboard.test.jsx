import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/partner.js", () => ({
  listPartnerOrders: vi.fn(),
  updatePartnerOrderStatus: vi.fn(),
}));

import { listPartnerOrders, updatePartnerOrderStatus } from "../api/partner.js";
import PartnerDashboard from "../pages/PartnerDashboard.jsx";

const order = (id, status, extra = {}) => ({
  id,
  status,
  customer_name: `Cust${id}`,
  delivery_phone: "9876543210",
  delivery_address: "Hostel 5",
  restaurant_name: "Rest",
  total_amount: "120.00",
  ...extra,
});
const page = (items, extra = {}) => ({ items, total: items.length, page: 1, page_size: 10, ...extra });

const renderIt = () =>
  render(
    <MemoryRouter>
      <PartnerDashboard />
    </MemoryRouter>
  );

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PartnerDashboard", () => {
  it("ASSIGNED shows Out for Delivery, calls the API, then reloads", async () => {
    listPartnerOrders.mockResolvedValue(page([order(1, "ASSIGNED")]));
    updatePartnerOrderStatus.mockResolvedValue({});
    renderIt();
    await userEvent.click(await screen.findByRole("button", { name: "Out for Delivery" }));
    expect(updatePartnerOrderStatus).toHaveBeenCalledWith(1, "OUT_FOR_DELIVERY");
    await waitFor(() => expect(listPartnerOrders).toHaveBeenCalledTimes(2));
  });

  it("OUT_FOR_DELIVERY shows Mark Delivered and calls with DELIVERED", async () => {
    listPartnerOrders.mockResolvedValue(page([order(2, "OUT_FOR_DELIVERY")]));
    updatePartnerOrderStatus.mockResolvedValue({});
    renderIt();
    await userEvent.click(await screen.findByRole("button", { name: "Mark Delivered" }));
    expect(updatePartnerOrderStatus).toHaveBeenCalledWith(2, "DELIVERED");
  });

  it("shows no action button for other statuses and a tel: link", async () => {
    listPartnerOrders.mockResolvedValue(page([order(3, "DELIVERED")]));
    renderIt();
    await screen.findByText("Order #3");
    expect(screen.queryByRole("button", { name: /Out for Delivery|Mark Delivered/ })).toBeNull();
    expect(screen.getByRole("link", { name: "9876543210" })).toHaveAttribute("href", "tel:9876543210");
  });

  it("status filter refetches at page 1 with status param", async () => {
    listPartnerOrders.mockResolvedValue(page([order(1, "ASSIGNED")], { total: 25 }));
    renderIt();
    await screen.findByText("Order #1");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(listPartnerOrders).toHaveBeenLastCalledWith({ status: "", page: 2, page_size: 10 })
    );
    await userEvent.selectOptions(screen.getByLabelText("Status"), "ASSIGNED");
    await waitFor(() =>
      expect(listPartnerOrders).toHaveBeenLastCalledWith({ status: "ASSIGNED", page: 1, page_size: 10 })
    );
  });

  it("shows 409 error inline and reloads the list", async () => {
    listPartnerOrders.mockResolvedValue(page([order(1, "ASSIGNED")]));
    updatePartnerOrderStatus.mockRejectedValue({
      response: { status: 409, data: { detail: "Order already updated" } },
    });
    renderIt();
    await userEvent.click(await screen.findByRole("button", { name: "Out for Delivery" }));
    expect(await screen.findByText("Order already updated")).toBeInTheDocument();
    await waitFor(() => expect(listPartnerOrders).toHaveBeenCalledTimes(2));
  });

  it("pagination next/prev refetch with page param", async () => {
    listPartnerOrders.mockImplementation(async (p) =>
      page([order(1, "ASSIGNED")], { total: 25, page: p.page })
    );
    renderIt();
    await screen.findByText("Order #1");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(listPartnerOrders).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
    await screen.findByText("Page 2 of 3");
    await userEvent.click(screen.getByRole("button", { name: "Previous" }));
    await waitFor(() => expect(listPartnerOrders).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1 })));
  });
});
