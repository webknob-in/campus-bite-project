import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { TOKEN_KEY, USER_KEY } from "../api/client";
import PublicOnlyRoute from "../components/PublicOnlyRoute";
import { AuthProvider } from "../context/AuthContext";
import { ROLES, roleHome } from "../utils/roles";

// Requirement 1.4: logged-in users are redirected away from /login and /register.

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route element={<PublicOnlyRoute />}>
            <Route path="/login" element={<div>login form</div>} />
            <Route path="/register" element={<div>register form</div>} />
          </Route>
          <Route path="/restaurants" element={<div>customer home</div>} />
          <Route path="/owner/dashboard" element={<div>owner home</div>} />
          <Route path="/partner/dashboard" element={<div>partner home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

function signIn(role) {
  localStorage.setItem(TOKEN_KEY, "jwt");
  localStorage.setItem(USER_KEY, JSON.stringify({ id: 1, name: "T", role }));
}

beforeEach(() => {
  localStorage.clear();
});

describe("PublicOnlyRoute", () => {
  it("shows /login and /register to a visitor", () => {
    renderAt("/login");
    expect(screen.getByText("login form")).toBeInTheDocument();
  });

  it("shows /register to a visitor", () => {
    renderAt("/register");
    expect(screen.getByText("register form")).toBeInTheDocument();
  });

  it.each([
    [ROLES.CUSTOMER, "customer home"],
    [ROLES.RESTAURANT_OWNER, "owner home"],
    [ROLES.DELIVERY_PARTNER, "partner home"],
  ])("redirects a logged-in %s from /login to their home", (role, home) => {
    signIn(role);
    renderAt("/login");
    expect(screen.getByText(home)).toBeInTheDocument();
    expect(screen.queryByText("login form")).not.toBeInTheDocument();
  });

  it("redirects a logged-in user from /register", () => {
    signIn(ROLES.CUSTOMER);
    renderAt("/register");
    expect(screen.getByText("customer home")).toBeInTheDocument();
  });
});

describe("roleHome", () => {
  it("maps each role to its home page and unknown roles to /login", () => {
    expect(roleHome(ROLES.CUSTOMER)).toBe("/restaurants");
    expect(roleHome(ROLES.RESTAURANT_OWNER)).toBe("/owner/dashboard");
    expect(roleHome(ROLES.DELIVERY_PARTNER)).toBe("/partner/dashboard");
    expect(roleHome(null)).toBe("/login");
  });
});
