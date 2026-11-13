import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { CART_KEY, TOKEN_KEY, USER_KEY } from "../api/client";
import Navbar, { linksForRole } from "../components/Navbar";
import { AuthProvider } from "../context/AuthContext";
import { ROLES } from "../utils/roles";

// Requirements 7.3, 32.1, 34.2: role-specific links, Logout for signed-in users, hamburger toggle.

const EXPECTED = {
  visitor: ["Restaurants", "Dishes", "Login", "Register"],
  [ROLES.CUSTOMER]: ["Restaurants", "Dishes", "Cart", "Dashboard", "AI Insights"],
  [ROLES.RESTAURANT_OWNER]: ["Dashboard", "Menu", "Orders"],
  [ROLES.DELIVERY_PARTNER]: ["Deliveries", "History"],
};

function signIn(role) {
  localStorage.setItem(TOKEN_KEY, "jwt");
  localStorage.setItem(USER_KEY, JSON.stringify({ id: 1, name: "Asha", role }));
}

function renderNavbar() {
  return render(
    <MemoryRouter initialEntries={["/restaurants"]}>
      <AuthProvider>
        <Navbar />
      </AuthProvider>
    </MemoryRouter>
  );
}

const linkLabels = () =>
  within(screen.getByRole("navigation", { name: "Main" }))
    .getAllByRole("link")
    .map((a) => a.textContent);

beforeEach(() => {
  localStorage.clear();
});

describe("Navbar links", () => {
  it("shows Restaurants, Dishes, Login, Register to a visitor, with no Logout", () => {
    renderNavbar();
    expect(linkLabels()).toEqual(EXPECTED.visitor);
    expect(screen.queryByRole("button", { name: "Logout" })).not.toBeInTheDocument();
  });

  it.each([ROLES.CUSTOMER, ROLES.RESTAURANT_OWNER, ROLES.DELIVERY_PARTNER])(
    "shows exactly the %s links and a Logout button",
    (role) => {
      signIn(role);
      renderNavbar();
      expect(linkLabels()).toEqual(EXPECTED[role]);
      expect(screen.getByRole("button", { name: "Logout" })).toBeInTheDocument();
      expect(screen.getByText("Asha")).toBeInTheDocument();
    }
  );

  it("points each role link at the role's own pages", () => {
    expect(linksForRole(ROLES.CUSTOMER).map((l) => l.to)).toEqual([
      "/restaurants",
      "/dishes",
      "/cart",
      "/customer/dashboard",
      "/insights",
    ]);
    expect(linksForRole(ROLES.RESTAURANT_OWNER).map((l) => l.to)).toEqual([
      "/owner/dashboard",
      "/owner/menu",
      "/owner/orders",
    ]);
    expect(linksForRole(ROLES.DELIVERY_PARTNER).map((l) => l.to)).toEqual([
      "/partner/dashboard",
      "/partner/history",
    ]);
  });

  it("gives the public links to a null or unknown role", () => {
    expect(linksForRole(null).map((l) => l.label)).toEqual(EXPECTED.visitor);
    expect(linksForRole("ADMIN").map((l) => l.label)).toEqual(EXPECTED.visitor);
  });
});

describe("Navbar behavior", () => {
  it("toggles the hamburger menu and keeps aria-expanded in sync", async () => {
    const user = userEvent.setup();
    renderNavbar();
    const toggle = screen.getByRole("button", { name: "Open menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("navigation", { name: "Main" })).not.toHaveClass("is-open");

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveAccessibleName("Close menu");
    expect(screen.getByRole("navigation", { name: "Main" })).toHaveClass("is-open");
    expect(toggle).toHaveAttribute("aria-controls", screen.getByRole("navigation", { name: "Main" }).id);

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("closes the menu when a link is used", async () => {
    const user = userEvent.setup();
    renderNavbar();
    const toggle = screen.getByRole("button", { name: "Open menu" });
    await user.click(toggle);
    await user.click(screen.getByRole("link", { name: "Dishes" }));
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });

  it("logs out: clears the stored session and cart, and shows visitor links", async () => {
    const user = userEvent.setup();
    signIn(ROLES.CUSTOMER);
    localStorage.setItem(CART_KEY, "[]");
    renderNavbar();

    await user.click(screen.getByRole("button", { name: "Logout" }));

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(USER_KEY)).toBeNull();
    expect(localStorage.getItem(CART_KEY)).toBeNull();
    expect(linkLabels()).toEqual(EXPECTED.visitor);
  });
});
