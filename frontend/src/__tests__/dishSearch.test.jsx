import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/restaurants.js", () => ({ listDishes: vi.fn() }));
vi.mock("../context/AuthContext.jsx", () => ({
  useAuth: () => ({ isAuthenticated: false, role: null }),
}));
vi.mock("../context/CartContext.jsx", () => ({ useCart: () => ({ addItem: vi.fn() }) }));

import { listDishes } from "../api/restaurants.js";
import DishSearch from "../pages/DishSearch.jsx";

const dish = {
  id: 1,
  name: "Veg Biryani",
  description: "Rice",
  price: "120.00",
  is_available: true,
  restaurant_id: 3,
  restaurant_name: "Spice Hub",
};

beforeEach(() => {
  vi.clearAllMocks();
  listDishes.mockResolvedValue({ items: [dish], total: 1, page: 1, page_size: 12 });
});

const renderIt = () =>
  render(
    <MemoryRouter>
      <DishSearch />
    </MemoryRouter>
  );

describe("DishSearch", () => {
  it("lists dishes and sends the name and price filters to the API", async () => {
    renderIt();
    expect(await screen.findByText("Veg Biryani")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Search dishes"), "biryani");
    await userEvent.type(screen.getByLabelText("Min price"), "50");
    await userEvent.type(screen.getByLabelText("Max price"), "200");
    await waitFor(() =>
      expect(listDishes).toHaveBeenLastCalledWith({
        search: "biryani",
        min_price: "50",
        max_price: "200",
        page: 1,
        page_size: 12,
      })
    );
  });

  it("reports an inverted price range inline and does not call the API for it", async () => {
    renderIt();
    await screen.findByText("Veg Biryani");
    listDishes.mockClear();
    await userEvent.type(screen.getByLabelText("Min price"), "300");
    await userEvent.type(screen.getByLabelText("Max price"), "100");
    expect(await screen.findByText("Fix the price filters to see results.")).toBeInTheDocument();
    expect(listDishes).not.toHaveBeenCalledWith(expect.objectContaining({ min_price: "300", max_price: "100" }));
  });
});
