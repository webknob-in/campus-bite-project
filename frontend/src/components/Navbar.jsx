// Navbar: role-based navigation (Requirements 3.3, 7.3, 32.1, 34.2).
// - Visitor: Restaurants, Dishes, Login, Register.
//   Customer: Restaurants, Dishes, Cart, Dashboard, AI Insights.
//   Owner: Dashboard, Menu, Orders.  Partner: Deliveries, History.
// - Authenticated users also get a Logout button, which clears the session and goes to /login.
// - At 768px and below the links collapse behind a hamburger button (`aria-expanded`,
//   `aria-controls`); the menu closes when the route changes or a link is used.
// - Extension point: `NavBadge` renders extra content next to a link. Task 13.7 adds the
//   Cart item count there.
import { useEffect, useId, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { ROLES } from "../utils/roles.js";

const RESTAURANTS = { to: "/restaurants", label: "Restaurants" };
const DISHES = { to: "/dishes", label: "Dishes" };

const VISITOR_LINKS = [RESTAURANTS, DISHES, { to: "/login", label: "Login" }, { to: "/register", label: "Register" }];

const ROLE_LINKS = {
  [ROLES.CUSTOMER]: [
    RESTAURANTS,
    DISHES,
    { to: "/cart", label: "Cart" },
    { to: "/customer/dashboard", label: "Dashboard" },
    { to: "/insights", label: "AI Insights" },
  ],
  [ROLES.RESTAURANT_OWNER]: [
    { to: "/owner/dashboard", label: "Dashboard" },
    { to: "/owner/menu", label: "Menu" },
    { to: "/owner/orders", label: "Orders" },
  ],
  [ROLES.DELIVERY_PARTNER]: [
    { to: "/partner/dashboard", label: "Deliveries" },
    { to: "/partner/history", label: "History" },
  ],
};

/** Links permitted for a role; visitors (null or unknown role) get the public links. */
export function linksForRole(role) {
  return ROLE_LINKS[role] ?? VISITOR_LINKS;
}

// eslint-disable-next-line no-unused-vars
function NavBadge({ to }) {
  return null; // Task 13.7: show the Cart item count when `to === "/cart"`.
}

export default function Navbar() {
  const { isAuthenticated, role, user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const menuId = useId();

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  const links = linksForRole(isAuthenticated ? role : null);

  function handleLogout() {
    setOpen(false);
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-brand">
          CampusBite
        </Link>
        <button
          type="button"
          className="navbar-toggle"
          aria-expanded={open}
          aria-controls={menuId}
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          <span className="navbar-toggle-bar" aria-hidden="true" />
          <span className="navbar-toggle-bar" aria-hidden="true" />
          <span className="navbar-toggle-bar" aria-hidden="true" />
        </button>
        <nav id={menuId} className={`navbar-menu${open ? " is-open" : ""}`} aria-label="Main">
          <ul className="navbar-links">
            {links.map((link) => (
              <li key={link.to}>
                <NavLink to={link.to} className="navbar-link" onClick={() => setOpen(false)}>
                  {link.label}
                  <NavBadge to={link.to} />
                </NavLink>
              </li>
            ))}
          </ul>
          {isAuthenticated && (
            <div className="navbar-user">
              {user?.name && <span className="navbar-user-name">{user.name}</span>}
              <button type="button" className="btn btn-secondary btn-sm" onClick={handleLogout}>
                Logout
              </button>
            </div>
          )}
        </nav>
      </div>
    </header>
  );
}
