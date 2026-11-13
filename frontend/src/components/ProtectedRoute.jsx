// ProtectedRoute: route guard (Requirements 7.1, 7.2).
//   <ProtectedRoute allowedRoles={[ROLES.CUSTOMER]}><Cart /></ProtectedRoute>
//   <Route element={<ProtectedRoute allowedRoles={[ROLES.CUSTOMER]} />}>...</Route>   (renders <Outlet />)
// - Visitors go to /login; the attempted location is passed as `state.from` so Login can return there.
// - Authenticated users whose role is not in `allowedRoles` go to their own home page.
// - Without `allowedRoles`, any authenticated user is allowed.
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { roleHome } from "../utils/roles.js";

export default function ProtectedRoute({ allowedRoles, children }) {
  const { isAuthenticated, role } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />;
  if (allowedRoles && !allowedRoles.includes(role)) return <Navigate to={roleHome(role)} replace />;
  return children ?? <Outlet />;
}
