import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { TOKEN_KEY, USER_KEY } from "../api/client";
import { AuthProvider } from "../context/AuthContext";
import { CartProvider, useCart } from "../context/CartContext";

// Requirements 10.4, 49.3: switching restaurants asks for confirmation.

const R1 = { id: 1, name: "Spice Hub" };
const R2 = { id: 2, name: "Pizza Point" };
const DOSA = { id: 11, name: "Dosa", price: "40.00" };
const IDLI = { id: 12, name: "Idli", price: "30.00" };
const PIZZA = { id: 21, name: "Margherita", price: "120.00" };

function Harness() {
  const { items, restaurantName, addItem } = useCart();
  return (
    <div>
      <button onClick={() => addItem(DOSA, R1)}>add dosa</button>
      <button onClick={() => addItem(IDLI, R1)}>add idli</button>
      <button onClick={() => addItem(PIZZA, R2)}>add pizza</button>
      <p data-testid="restaurant">{restaurantName ?? "none"}</p>
      <ul>
        {items.map((l) => (
          <li key={l.id}>
            {l.name} x{l.quantity}
          </li>
        ))}
      </ul>
    </div>
  );
}

function setup() {
  render(
    <MemoryRouter>
      <AuthProvider>
        <CartProvider>
          <Harness />
        </CartProvider>
      </AuthProvider>
    </MemoryRouter>
  );
  return userEvent.setup();
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem(TOKEN_KEY, "jwt");
  localStorage.setItem(USER_KEY, JSON.stringify({ id: 1, name: "Asha", role: "customer" }));
});

describe("cart restaurant switching", () => {
  it("adds from the same restaurant without a modal and increments the quantity", async () => {
    const user = setup();
    await user.click(screen.getByText("add dosa"));
    await user.click(screen.getByText("add dosa"));
    await user.click(screen.getByText("add idli"));
    expect(screen.getByText("Dosa x2")).toBeInTheDocument();
    expect(screen.getByText("Idli x1")).toBeInTheDocument();
    expect(screen.queryByText("Start a new cart?")).not.toBeInTheDocument();
  });

  it("shows the confirm modal for another restaurant and keeps the cart on Cancel", async () => {
    const user = setup();
    await user.click(screen.getByText("add dosa"));
    await user.click(screen.getByText("add pizza"));
    expect(screen.getByText("Start a new cart?")).toBeInTheDocument();
    expect(screen.getByText("Dosa x1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Start a new cart?")).not.toBeInTheDocument();
    expect(screen.getByText("Dosa x1")).toBeInTheDocument();
    expect(screen.queryByText("Margherita x1")).not.toBeInTheDocument();
    expect(screen.getByTestId("restaurant")).toHaveTextContent("Spice Hub");
  });

  it("replaces the cart only after confirming", async () => {
    const user = setup();
    await user.click(screen.getByText("add dosa"));
    await user.click(screen.getByText("add pizza"));
    await user.click(screen.getByRole("button", { name: "Clear cart and add" }));
    expect(screen.queryByText("Start a new cart?")).not.toBeInTheDocument();
    expect(screen.queryByText("Dosa x1")).not.toBeInTheDocument();
    expect(screen.getByText("Margherita x1")).toBeInTheDocument();
    expect(screen.getByTestId("restaurant")).toHaveTextContent("Pizza Point");
  });
});
