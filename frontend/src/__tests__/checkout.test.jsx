import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CART_KEY, TOKEN_KEY, USER_KEY } from "../api/client";
import { placeOrder } from "../api/orders";
import { AuthProvider } from "../context/AuthContext";
import { CartProvider } from "../context/CartContext";
import CartCheckout from "../pages/CartCheckout";

// Requirements 11.12, 49.3: checkout validation and order placement.

vi.mock("../api/orders.js", () => ({ placeOrder: vi.fn() }));

function Where() {
  return <div data-testid="location">{useLocation().pathname}</div>;
}

function seedCart() {
  localStorage.setItem(
    CART_KEY,
    JSON.stringify({
      restaurantId: 1,
      restaurantName: "Spice Hub",
      items: [
        { id: 11, name: "Dosa", price: "40.00", quantity: 2 },
        { id: 12, name: "Idli", price: "30.00", quantity: 1 },
      ],
    })
  );
}

function setup() {
  render(
    <MemoryRouter initialEntries={["/cart"]}>
      <AuthProvider>
        <CartProvider>
          <Routes>
            <Route path="/cart" element={<CartCheckout />} />
            <Route path="/orders/:id" element={<div>order page</div>} />
            <Route path="/restaurants" element={<div>restaurants</div>} />
          </Routes>
          <Where />
        </CartProvider>
      </AuthProvider>
    </MemoryRouter>
  );
  return userEvent.setup();
}

async function fillValid(user, { cardNumber = "4111 1111 1111 1111" } = {}) {
  await user.type(screen.getByLabelText(/delivery address/i), "12 Main Road, Block A");
  await user.type(screen.getByLabelText(/phone/i), "9876543210");
  await user.type(screen.getByLabelText(/card holder/i), "Asha Rao");
  await user.type(screen.getByLabelText(/card number/i), cardNumber);
  await user.type(screen.getByLabelText(/expiry/i), "1240");
  await user.type(screen.getByLabelText(/cvv/i), "123");
}

const submit = (user) => user.click(screen.getByRole("button", { name: /place order/i }));

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  localStorage.setItem(TOKEN_KEY, "jwt");
  localStorage.setItem(USER_KEY, JSON.stringify({ id: 1, name: "Asha", role: "customer" }));
});

describe("CartCheckout", { timeout: 30000 }, () => {
  it("shows the empty state for an empty cart", () => {
    setup();
    expect(screen.getByText("Your cart is empty.")).toBeInTheDocument();
  });

  it("shows inline errors for an invalid card and does not place the order", async () => {
    seedCart();
    const user = setup();
    await fillValid(user, { cardNumber: "1234" });
    await submit(user);
    expect(await screen.findByText("Card number must be exactly 16 digits.")).toBeInTheDocument();
    expect(placeOrder).not.toHaveBeenCalled();
  });

  it("shows required errors when the form is empty", async () => {
    seedCart();
    const user = setup();
    await submit(user);
    expect(screen.getByText("Card number is required.")).toBeInTheDocument();
    expect(screen.getByText("Expiry date is required.")).toBeInTheDocument();
    expect(screen.getByText("CVV is required.")).toBeInTheDocument();
    expect(placeOrder).not.toHaveBeenCalled();
  });

  it("places the order once, clears the cart and navigates to the order", async () => {
    seedCart();
    placeOrder.mockResolvedValue({ id: 77 });
    const user = setup();
    await fillValid(user);
    await submit(user);

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/orders/77"));
    expect(placeOrder).toHaveBeenCalledTimes(1);
    const payload = placeOrder.mock.calls[0][0];
    expect(payload.items).toEqual([
      { menu_item_id: 11, quantity: 2 },
      { menu_item_id: 12, quantity: 1 },
    ]);
    expect(payload.delivery_address).toBe("12 Main Road, Block A");
    expect(payload.delivery_phone).toBe("9876543210");
    expect(payload.payment).toEqual({
      card_holder: "Asha Rao",
      card_number: "4111111111111111",
      expiry: "12/40",
      cvv: "123",
    });
    expect(localStorage.getItem(CART_KEY)).toBeNull();
  });

  it("displays a backend error and keeps the cart", async () => {
    seedCart();
    placeOrder.mockRejectedValue({ response: { status: 400, data: { detail: "Item unavailable" } } });
    const user = setup();
    await fillValid(user);
    await submit(user);

    expect(await screen.findByText("Item unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/cart");
    expect(screen.getByText("Dosa")).toBeInTheDocument();
    expect(localStorage.getItem(CART_KEY)).not.toBeNull();
  });

  it("disables submit while pending so the order is not placed twice", async () => {
    seedCart();
    let resolve;
    placeOrder.mockReturnValue(new Promise((r) => (resolve = r)));
    const user = setup();
    await fillValid(user);
    await submit(user);

    const button = screen.getByRole("button", { name: /place order/i });
    expect(button).toBeDisabled();
    await user.click(button);
    expect(placeOrder).toHaveBeenCalledTimes(1);

    resolve({ id: 5 });
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/orders/5"));
  });
});
