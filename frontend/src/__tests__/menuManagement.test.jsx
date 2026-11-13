// Unit tests for owner menu management (Requirement 16.8).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/owner.js", () => ({
  listOwnerMenuItems: vi.fn(),
  createMenuItem: vi.fn(),
  updateMenuItem: vi.fn(),
  deleteMenuItem: vi.fn(),
  setMenuItemAvailability: vi.fn(),
}));

import {
  createMenuItem,
  deleteMenuItem,
  listOwnerMenuItems,
  setMenuItemAvailability,
} from "../api/owner.js";
import MenuManagement from "../pages/MenuManagement.jsx";

const dish = { id: 4, name: "Paneer Roll", price: "80.00", is_available: true };

beforeEach(() => {
  vi.clearAllMocks();
  listOwnerMenuItems.mockResolvedValue({ items: [dish], page: 1, page_size: 10, total: 1 });
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <MenuManagement />
    </MemoryRouter>
  );

describe("MenuManagement", () => {
  it("availability switch calls setMenuItemAvailability with the inverted value", async () => {
    setMenuItemAvailability.mockResolvedValue({});
    renderPage();
    await userEvent.click(await screen.findByRole("switch", { name: "Paneer Roll available" }));
    expect(setMenuItemAvailability).toHaveBeenCalledWith(4, false);
  });

  it("blocks invalid name and price without calling the API", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Price/), "-5");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(await within(dialog).findByText("Name is required.")).toBeInTheDocument();
    expect(within(dialog).getByText(/Enter a price/)).toBeInTheDocument();
    expect(createMenuItem).not.toHaveBeenCalled();
  });

  it("valid submit calls createMenuItem with price as a string", async () => {
    createMenuItem.mockResolvedValue({});
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Add item" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Name/), "Samosa");
    await userEvent.type(within(dialog).getByLabelText(/Price/), "12.5");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(createMenuItem).toHaveBeenCalledTimes(1));
    expect(createMenuItem.mock.calls[0][0]).toMatchObject({ name: "Samosa", price: "12.50" });
  });

  it("delete asks for confirmation before calling deleteMenuItem", async () => {
    deleteMenuItem.mockResolvedValue(undefined);
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(deleteMenuItem).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Paneer Roll");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(deleteMenuItem).toHaveBeenCalledWith(4));
  });
});
