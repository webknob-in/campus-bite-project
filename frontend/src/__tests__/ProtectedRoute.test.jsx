import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { CART_KEY, TOKEN_KEY, USER_KEY } from "../api/client";
import ProtectedRoute from "../components/ProtectedRoute";
import { AuthProvider } from "../context/AuthContext";
import { ROLES } from "../utils/roles";

// Requirements 7.1, 7.2: visitors go to /login, wrong roles go to their own home.

function signIn(role) {
  localStorage.setItem(TOKEN_KEY, "jwt");
  localStorage.setItem(USER_KEY, JSON.stringify({ id: 1, name: "Test", role }));
}

function LoginProbe() {
  const { state } = useLocation();
  return <div>login page from {state?.from?.pathname ?? "nowhere"}</div>;
}

function renderAt(path, allowedRoles) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route path="/restaurants" element={<div>customer home</div>} />
          <Route path="/owner/dashboard" element={<div>owner home</div>} />
          <Route path="/partner/dashboard" element={<div>partner home</div>} />
          <Route
            path="/owner/menu"
            element={
              <ProtectedRoute allowedRoles={allowedRoles}>
                <div>secret owner menu</div>
              </ProtectedRoute>
            }
          />
          <Route element={<ProtectedRoute allowedRoles={allowedRoles} />}>
            <Route path="/nested" element={<div>nested content</div>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
});

describe("ProtectedRoute", () => {
  it("redirects a visitor to /login and remembers the attempted location", () => {
    renderAt("/owner/menu", [ROLES.RESTAURANT_OWNER]);
    expect(screen.getByText("login page from /owner/menu")).toBeInTheDocument();
    expect(screen.queryByText("secret owner menu")).not.toBeInTheDocument();
  });

  it("renders children for an allowed role", () => {
    signIn(ROLES.RESTAURANT_OWNER);
    renderAt("/owner/menu", [ROLES.RESTAURANT_OWNER]);
    expect(screen.getByText("secret owner menu")).toBeInTheDocument();
  });

  it.each([
    [ROLES.CUSTOMER, "customer home"],
    [ROLES.DELIVERY_PARTNER, "partner home"],
  ])("sends %s to their role home when the role is not allowed", (role, home) => {
    signIn(role);
    renderAt("/owner/menu", [ROLES.RESTAURANT_OWNER]);
    expect(screen.getByText(home)).toBeInTheDocument();
    expect(screen.queryByText("secret owner menu")).not.toBeInTheDocument();
  });

  it("allows any authenticated user when allowedRoles is omitted", () => {
    signIn(ROLES.DELIVERY_PARTNER);
    renderAt("/owner/menu", undefined);
    expect(screen.getByText("secret owner menu")).toBeInTheDocument();
  });

  it("renders nested routes through <Outlet /> when used as a layout route", () => {
    signIn(ROLES.CUSTOMER);
    renderAt("/nested", [ROLES.CUSTOMER]);
    expect(screen.getByText("nested content")).toBeInTheDocument();
  });

  it("discards a stored token without a user and treats the visitor as logged out", () => {
    localStorage.setItem(TOKEN_KEY, "jwt");
    localStorage.setItem(CART_KEY, "[]");
    renderAt("/owner/menu", [ROLES.RESTAURANT_OWNER]);
    expect(screen.getByText(/login page/)).toBeInTheDocument();
  });
});
