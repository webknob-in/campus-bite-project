import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TOKEN_KEY, USER_KEY } from "../api/client";
import App from "../App";
import { AuthProvider } from "../context/AuthContext";
import { CartProvider } from "../context/CartContext";
import { ROLES } from "../utils/roles";

// Requirement 35.3: /customer/dashboard, /orders/:id and /insights are Customer-only.

vi.mock("../api/orders.js", () => ({
  listMyOrders: vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 })),
  getOrder: vi.fn(() =>
    Promise.resolve({
      id: 5,
      status: "PLACED",
      payment_status: "paid",
      return_status: "none",
      total_amount: "60.00",
      items: [],
    })
  ),
  cancelOrder: vi.fn(),
  placeOrder: vi.fn(),
  submitReview: vi.fn(),
  requestReturn: vi.fn(),
}));

vi.mock("../api/ai.js", () => ({
  askInsight: vi.fn(),
  getInsightSummary: vi.fn(),
}));

const PATHS = ["/customer/dashboard", "/orders/5", "/insights"];

function LocationProbe() {
  return <div data-testid="location">{useLocation().pathname}</div>;
}

function renderApp(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <CartProvider>
          <App />
          <LocationProbe />
        </CartProvider>
      </AuthProvider>
    </MemoryRouter>
  );
}

function signIn(role) {
  localStorage.setItem(TOKEN_KEY, "jwt");
  localStorage.setItem(USER_KEY, JSON.stringify({ id: 1, name: "Asha", role }));
}

beforeEach(() => {
  localStorage.clear();
});

describe("customer routes", () => {
  it.each(PATHS)("redirects a visitor from %s to /login", (path) => {
    renderApp(path);
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });

  it.each(PATHS)("redirects a restaurant owner from %s to /owner/dashboard", (path) => {
    signIn(ROLES.RESTAURANT_OWNER);
    renderApp(path);
    expect(screen.getByTestId("location")).toHaveTextContent("/owner/dashboard");
  });

  it.each(PATHS)("redirects a delivery partner from %s to /partner/dashboard", (path) => {
    signIn(ROLES.DELIVERY_PARTNER);
    renderApp(path);
    expect(screen.getByTestId("location")).toHaveTextContent("/partner/dashboard");
  });

  it("shows the customer dashboard to a customer", async () => {
    signIn(ROLES.CUSTOMER);
    renderApp("/customer/dashboard");
    expect(await screen.findByRole("heading", { name: "My orders" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/customer/dashboard");
  });

  it("shows the order detail page to a customer", async () => {
    signIn(ROLES.CUSTOMER);
    renderApp("/orders/5");
    expect(await screen.findByRole("heading", { name: "Order #5" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/orders/5");
  });

  it("shows the AI insights page to a customer", async () => {
    signIn(ROLES.CUSTOMER);
    renderApp("/insights");
    expect(await screen.findByRole("heading", { name: "AI order insights" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/insights");
  });
});
