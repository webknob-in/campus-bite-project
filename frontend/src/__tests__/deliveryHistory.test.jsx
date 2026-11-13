import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/partner.js", () => ({ listPartnerHistory: vi.fn() }));

import { listPartnerHistory } from "../api/partner.js";
import DeliveryHistory from "../pages/DeliveryHistory.jsx";
import { formatCurrency, formatDateTime } from "../utils/format.js";

const row = (id) => ({
  id,
  status: "DELIVERED",
  customer_name: `Cust${id}`,
  restaurant_name: "Rest",
  delivery_address: "Hostel 5",
  delivered_at: "2024-05-01T10:30:00Z",
  total_amount: "1234.50",
});

const renderIt = () =>
  render(
    <MemoryRouter>
      <DeliveryHistory />
    </MemoryRouter>
  );

beforeEach(() => vi.clearAllMocks());

describe("DeliveryHistory", () => {
  it("renders rows with delivered time and formatted total", async () => {
    listPartnerHistory.mockResolvedValue({ items: [row(7)], total: 1, page: 1, page_size: 10 });
    renderIt();
    expect(await screen.findByText("#7")).toBeInTheDocument();
    expect(screen.getByText("Cust7")).toBeInTheDocument();
    expect(screen.getByText(formatCurrency("1234.50"))).toBeInTheDocument();
    expect(screen.getByText(formatDateTime("2024-05-01T10:30:00Z"))).toBeInTheDocument();
  });

  it("shows empty state", async () => {
    listPartnerHistory.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 });
    renderIt();
    expect(await screen.findByText("No completed deliveries yet.")).toBeInTheDocument();
  });

  it("shows error and retries", async () => {
    listPartnerHistory.mockRejectedValueOnce({ response: { status: 500, data: { detail: "Boom" } } });
    listPartnerHistory.mockResolvedValue({ items: [row(8)], total: 1, page: 1, page_size: 10 });
    renderIt();
    expect(await screen.findByText("Boom")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("#8")).toBeInTheDocument();
  });

  it("paginates with page param", async () => {
    listPartnerHistory.mockResolvedValue({ items: [row(1)], total: 25, page: 1, page_size: 10 });
    renderIt();
    await screen.findByText("#1");
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(listPartnerHistory).toHaveBeenLastCalledWith({ page: 2, page_size: 10 })
    );
  });
});
