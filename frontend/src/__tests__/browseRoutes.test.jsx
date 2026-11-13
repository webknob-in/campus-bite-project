import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CART_KEY, TOKEN_KEY, USER_KEY } from "../api/client";
import App from "../App";
import { AuthProvider } from "../context/AuthContext";
import { CartProvider } from "../context/CartContext";
import { ROLES } from "../utils/roles";
import { formatPrice as formatCheckoutPrice } from "../utils/checkoutFormat";
import { formatPrice } from "../utils/money";

// Requirements 10.5, 35.2, 35.3: browsing routes, /cart guard, Cart badge.

vi.mock("../api/restaurants.js", () => ({
  listRestaurants: vi.fn(() =>
    Promise.resolve({
      items: [{ id: 1, name: "Campus Diner", cuisine: "Indian", is_open: true, address: "Block A" }],
      total: 1,
      page: 1,
      page_size: 12,
    })
  ),
  listDishes: vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, page_size: 12 })),
  getRestaurant: vi.fn(() => Promise.resolve({ id: 1, name: "Campus Diner" })),
  getRestaurantMenu: vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, page_size: 12 })),
  getRestaurantReviews: vi.fn(() => Promise.resolve({ items: [], total: 0, page: 1, page_size: 10 })),
}));

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

describe("browsing and cart routes", () => {
  it("shows the restaurant list at / to a visitor", async () => {
    renderApp("/");
    expect(await screen.findByText("Campus Diner")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/");
  });

  it("redirects a restaurant owner from /restaurants to /owner/dashboard", () => {
    signIn(ROLES.RESTAURANT_OWNER);
    renderApp("/restaurants");
    expect(screen.getByTestId("location")).toHaveTextContent("/owner/dashboard");
    expect(screen.queryByText("Campus Diner")).not.toBeInTheDocument();
  });

  it("redirects a visitor from /cart to /login", () => {
    renderApp("/cart");
    expect(screen.getByTestId("location")).toHaveTextContent("/login");
  });

  it("shows the cart item count in the Navbar for a customer", async () => {
    signIn(ROLES.CUSTOMER);
    localStorage.setItem(
      CART_KEY,
      JSON.stringify({
        restaurantId: 1,
        restaurantName: "Campus Diner",
        items: [
          { id: 10, name: "Dosa", price: "50.00", quantity: 2 },
          { id: 11, name: "Tea", price: "10.00", quantity: 1 },
        ],
      })
    );
    renderApp("/restaurants");
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("img", { name: "3 items in cart" })).toHaveTextContent("3");
    expect(await screen.findByText("Campus Diner")).toBeInTheDocument();
  });

  it("hides the cart badge when the cart is empty", () => {
    signIn(ROLES.CUSTOMER);
    renderApp("/restaurants");
    expect(screen.queryByRole("img", { name: /in cart/ })).not.toBeInTheDocument();
  });
});

describe("price formatting uses INR", () => {
  it.each([formatPrice, formatCheckoutPrice])("formats decimal strings with the rupee symbol", (format) => {
    expect(format("12.50")).toBe("₹12.50");
    expect(format(7)).toBe("₹7.00");
    expect(format("abc")).not.toMatch(/\$/);
  });
});
