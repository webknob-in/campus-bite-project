import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as authApi from "../api/auth";
import client, { CART_KEY, TOKEN_KEY, USER_KEY } from "../api/client";
import { AuthProvider, useAuth } from "../context/AuthContext";

// Requirements 5.5, 5.7, 5.8: session restore, logout, and 401 handling.

const USER = { id: 7, name: "Asha", role: "CUSTOMER" };

function Probe() {
  const { isAuthenticated, role, user, token, login, logout } = useAuth();
  return (
    <div>
      <p data-testid="state">
        {isAuthenticated ? `in:${role}:${user.name}:${token}` : "out"}
      </p>
      <button onClick={() => login("a@b.co", "secret123")}>login</button>
      <button onClick={logout}>logout</button>
    </div>
  );
}

function renderProvider() {
  return render(
    <MemoryRouter initialEntries={["/home"]}>
      <AuthProvider>
        <Routes>
          <Route path="/home" element={<Probe />} />
          <Route path="/login" element={<div>login page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

const state = () => screen.getByTestId("state").textContent;

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("AuthProvider session restore", () => {
  it("restores user, token, and role from localStorage", () => {
    localStorage.setItem(TOKEN_KEY, "jwt-1");
    localStorage.setItem(USER_KEY, JSON.stringify(USER));
    renderProvider();
    expect(state()).toBe("in:CUSTOMER:Asha:jwt-1");
  });

  it("starts logged out when nothing is stored", () => {
    renderProvider();
    expect(state()).toBe("out");
  });

  it.each([
    ["corrupt user JSON", "jwt-1", "{not json"],
    ["a user without a role", "jwt-1", JSON.stringify({ id: 1 })],
    ["a token without a user", "jwt-1", null],
    ["a user without a token", null, JSON.stringify(USER)],
  ])("discards the session for %s", (_label, token, user) => {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, user);
    renderProvider();
    expect(state()).toBe("out");
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(USER_KEY)).toBeNull();
  });
});

describe("AuthProvider login and logout", () => {
  it("stores the token and user on login", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({ access_token: "new-jwt", token_type: "bearer", user: USER });
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByText("login"));

    expect(state()).toBe("in:CUSTOMER:Asha:new-jwt");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("new-jwt");
    expect(JSON.parse(localStorage.getItem(USER_KEY))).toEqual(USER);
  });

  it("logout clears token, user, and cart and resets state", async () => {
    localStorage.setItem(TOKEN_KEY, "jwt-1");
    localStorage.setItem(USER_KEY, JSON.stringify(USER));
    localStorage.setItem(CART_KEY, JSON.stringify([{ menu_item_id: 1, quantity: 2 }]));
    const user = userEvent.setup();
    renderProvider();

    await user.click(screen.getByText("logout"));

    expect(state()).toBe("out");
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(USER_KEY)).toBeNull();
    expect(localStorage.getItem(CART_KEY)).toBeNull();
  });

  it("logs out and navigates to /login when the API reports 401", async () => {
    localStorage.setItem(TOKEN_KEY, "jwt-1");
    localStorage.setItem(USER_KEY, JSON.stringify(USER));
    localStorage.setItem(CART_KEY, "[]");
    renderProvider();

    const originalAdapter = client.defaults.adapter;
    client.defaults.adapter = async (config) => {
      const { AxiosError } = await import("axios");
      const response = { status: 401, statusText: "", headers: {}, config, data: { detail: "expired" } };
      throw new AxiosError("401", AxiosError.ERR_BAD_REQUEST, config, null, response);
    };
    try {
      await act(async () => {
        await authApi.getMe().catch(() => {});
      });
    } finally {
      client.defaults.adapter = originalAdapter;
    }

    expect(screen.getByText("login page")).toBeInTheDocument();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(USER_KEY)).toBeNull();
    expect(localStorage.getItem(CART_KEY)).toBeNull();
  });
});

describe("useAuth", () => {
  it("throws outside an AuthProvider", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() =>
      render(
        <MemoryRouter>
          <Probe />
        </MemoryRouter>
      )
    ).toThrow(/AuthProvider/);
  });
});
