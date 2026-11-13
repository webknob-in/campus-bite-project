import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TOKEN_KEY, USER_KEY } from "../api/client";
import App from "../App";
import { AuthProvider } from "../context/AuthContext";
import { CartProvider } from "../context/CartContext";
import { ROLES } from "../utils/roles";

// Requirement 35.4: /owner/dashboard, /owner/menu and /owner/orders are owner-only.

vi.mock("../api/owner.js", () => {
  const page = () => Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 });
  return {
    listOwnerMenuItems: vi.fn(page),
    createMenuItem: vi.fn(),
    updateMenuItem: vi.fn(),
    deleteMenuItem: vi.fn(),
    setMenuItemAvailability: vi.fn(),
    listOwnerOrders: vi.fn(page),
    updateOwnerOrderStatus: vi.fn(),
    listDeliveryPartners: vi.fn(() => Promise.resolve([])),
    assignDeliveryPartner: vi.fn(),
    listReturns: vi.fn(page),
    approveReturn: vi.fn(),
    rejectReturn: vi.fn(),
    getOwnerStats: vi.fn(() => Promise.resolve({})),
    listReminders: vi.fn(() => Promise.resolve([])),
    resolveReminder: vi.fn(),
  };
});

const PAGES = [
  ["/owner/dashboard", "Owner dashboard"],
  ["/owner/menu", "Menu management"],
  ["/owner/orders", "Manage orders"],
];
const PATHS = PAGES.map(([p]) => p);

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

describe("owner routes", () => {
  it.each(PATHS)("redirects a visitor from %s to /login", (path) => {
    renderApp(path);
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });

  it.each(PATHS)("redirects a customer from %s to /restaurants", (path) => {
    signIn(ROLES.CUSTOMER);
    renderApp(path);
    expect(screen.getByTestId("location")).toHaveTextContent("/restaurants");
  });

  it.each(PATHS)("redirects a delivery partner from %s to /partner/dashboard", (path) => {
    signIn(ROLES.DELIVERY_PARTNER);
    renderApp(path);
    expect(screen.getByTestId("location")).toHaveTextContent("/partner/dashboard");
  });

  it.each(PAGES)("shows %s to an owner", async (path, heading) => {
    signIn(ROLES.RESTAURANT_OWNER);
    renderApp(path);
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent(path);
  });
});
