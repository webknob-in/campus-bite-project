// PublicOnlyRoute: for /login and /register (Requirement 1.4).
// Logged-in users are redirected to the home page for their role; visitors see the page.
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { roleHome } from "../utils/roles.js";

export default function PublicOnlyRoute({ children }) {
  const { isAuthenticated, role } = useAuth();
  if (isAuthenticated) return <Navigate to={roleHome(role)} replace />;
  return children ?? <Outlet />;
}
