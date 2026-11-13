import { render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TOKEN_KEY, USER_KEY } from "../api/client";
import App from "../App";
import { AuthProvider } from "../context/AuthContext";
import { CartProvider } from "../context/CartContext";
import { ROLES, roleHome } from "../utils/roles";

// Requirements 32.4, 35.5: /partner/dashboard and /partner/history are partner-only.

const { page } = vi.hoisted(() => ({
  page: () => Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 }),
}));

vi.mock("../api/partner.js", () => ({
  listPartnerOrders: vi.fn(() =>
    Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 })
  ),
  getPartnerOrder: vi.fn(),
  updatePartnerOrderStatus: vi.fn(),
  listPartnerHistory: vi.fn(() =>
    Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 })
  ),
}));

vi.mock("../api/owner.js", () => ({
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
}));

vi.mock("../api/restaurants.js", () => ({
  listRestaurants: vi.fn(page),
  listDishes: vi.fn(page),
  getRestaurant: vi.fn(() => Promise.resolve({})),
  getRestaurantMenu: vi.fn(page),
  getRestaurantReviews: vi.fn(page),
}));

const PAGES = [
  ["/partner/dashboard", "My deliveries"],
  ["/partner/history", "Delivery history"],
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

describe("partner routes", () => {
  it.each(PATHS)("redirects a visitor from %s to /login", (path) => {
    renderApp(path);
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });

  it.each(PATHS)("redirects a customer from %s to /restaurants", (path) => {
    signIn(ROLES.CUSTOMER);
    renderApp(path);
    expect(screen.getByTestId("location")).toHaveTextContent("/restaurants");
  });

  it.each(PATHS)("redirects an owner from %s to /owner/dashboard", (path) => {
    signIn(ROLES.RESTAURANT_OWNER);
    renderApp(path);
    expect(screen.getByTestId("location")).toHaveTextContent("/owner/dashboard");
  });

  it.each(PAGES)("shows %s to a delivery partner", async (path, heading) => {
    signIn(ROLES.DELIVERY_PARTNER);
    renderApp(path);
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent(path);
  });
});

describe("role homes", () => {
  it.each(Object.values(ROLES))("roleHome(%s) is a real route", async (role) => {
    signIn(role);
    renderApp(roleHome(role));
    expect(await screen.findByTestId("location")).toHaveTextContent(roleHome(role));
    expect(screen.queryByText("Page not found")).not.toBeInTheDocument();
  });
});
