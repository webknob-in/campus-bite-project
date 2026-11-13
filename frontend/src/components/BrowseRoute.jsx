// BrowseRoute: guard for the public browsing pages (Requirements 35.2, 35.3).
// Visitors and Customers see the page; Restaurant_Owners and Delivery_Partners are sent to their
// own home page.
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { ROLES, roleHome } from "../utils/roles.js";

export default function BrowseRoute({ children }) {
  const { isAuthenticated, role } = useAuth();
  if (isAuthenticated && role !== ROLES.CUSTOMER) return <Navigate to={roleHome(role)} replace />;
  return children;
}
