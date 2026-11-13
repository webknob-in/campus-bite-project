// Navbar: role-based navigation (Requirements 3.3, 7.3, 32.1, 34.2).
// - Visitor: Restaurants, Dishes, Login, Register.
//   Customer: Restaurants, Dishes, Cart, Dashboard, AI Insights.
//   Owner: Dashboard, Menu, Orders.  Partner: Deliveries, History.
// - Authenticated users also get a Logout button, which clears the session and goes to /login.
// - At 768px and below the links collapse behind a hamburger button (`aria-expanded`,
//   `aria-controls`); the menu closes when the route changes or a link is used.
// - `NavBadge` shows the Cart item count next to the Cart link (hidden at 0). It reads the cart
//   context directly and falls back to 0 when no CartProvider is mounted.
import { useContext, useEffect, useId, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import CartContext from "../context/CartContext.jsx";
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

/** Cart item count; 0 when no CartProvider is mounted (e.g. isolated Navbar tests). */
function useCartCount() {
  return useContext(CartContext)?.count ?? 0;
}

function NavBadge({ to }) {
  const count = useCartCount();
  if (to !== "/cart" || count <= 0) return null;
  return (
    <span className="navbar-badge" role="img" aria-label={`${count} ${count === 1 ? "item" : "items"} in cart`}>
      {count}
    </span>
  );
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
