// App: Navbar above the routed page content (Requirements 1.4, 10.5, 32.3, 35.1-35.3).
// Providers (BrowserRouter, AuthProvider, CartProvider) are set up in main.jsx.
import { Route, Routes } from "react-router-dom";
import BrowseRoute from "./components/BrowseRoute.jsx";
import Navbar from "./components/Navbar.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import PublicOnlyRoute from "./components/PublicOnlyRoute.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import NotFound from "./pages/NotFound.jsx";
import RestaurantList from "./pages/RestaurantList.jsx";
import RestaurantMenu from "./pages/RestaurantMenu.jsx";
import DishSearch from "./pages/DishSearch.jsx";
import CartCheckout from "./pages/CartCheckout.jsx";
import CustomerDashboard from "./pages/CustomerDashboard.jsx";
import OrderDetail from "./pages/OrderDetail.jsx";
import AIInsights from "./pages/AIInsights.jsx";
import OwnerDashboard from "./pages/OwnerDashboard.jsx";
import MenuManagement from "./pages/MenuManagement.jsx";
import OrderManagement from "./pages/OrderManagement.jsx";
import PartnerDashboard from "./pages/PartnerDashboard.jsx";
import DeliveryHistory from "./pages/DeliveryHistory.jsx";
import { ROLES } from "./utils/roles.js";

export default function App() {
  return (
    <>
      <Navbar />
      <main className="container">
        <Routes>
          {/* Browsing: visitors and Customers; owners and partners go to their role home. */}
          <Route
            path="/"
            element={
              <BrowseRoute>
                <RestaurantList />
              </BrowseRoute>
            }
          />
          <Route
            path="/restaurants"
            element={
              <BrowseRoute>
                <RestaurantList />
              </BrowseRoute>
            }
          />
          <Route
            path="/restaurants/:id"
            element={
              <BrowseRoute>
                <RestaurantMenu />
              </BrowseRoute>
            }
          />
          <Route
            path="/dishes"
            element={
              <BrowseRoute>
                <DishSearch />
              </BrowseRoute>
            }
          />

          {/* Auth pages: logged-in users are redirected to their role home. */}
          <Route element={<PublicOnlyRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
          </Route>

          {/* Cart (Customer only). */}
          <Route
            path="/cart"
            element={
              <ProtectedRoute allowedRoles={[ROLES.CUSTOMER]}>
                <CartCheckout />
              </ProtectedRoute>
            }
          />

          {/* Customer-only pages: dashboard, order detail, AI insights (Requirement 35.3). */}
          <Route
            path="/customer/dashboard"
            element={
              <ProtectedRoute allowedRoles={[ROLES.CUSTOMER]}>
                <CustomerDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders/:id"
            element={
              <ProtectedRoute allowedRoles={[ROLES.CUSTOMER]}>
                <OrderDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/insights"
            element={
              <ProtectedRoute allowedRoles={[ROLES.CUSTOMER]}>
                <AIInsights />
              </ProtectedRoute>
            }
          />

          {/* Restaurant owner routes (Requirement 35.4). */}
          <Route
            path="/owner/dashboard"
            element={
              <ProtectedRoute allowedRoles={[ROLES.RESTAURANT_OWNER]}>
                <OwnerDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/owner/menu"
            element={
              <ProtectedRoute allowedRoles={[ROLES.RESTAURANT_OWNER]}>
                <MenuManagement />
              </ProtectedRoute>
            }
          />
          <Route
            path="/owner/orders"
            element={
              <ProtectedRoute allowedRoles={[ROLES.RESTAURANT_OWNER]}>
                <OrderManagement />
              </ProtectedRoute>
            }
          />

          {/* Delivery partner routes (Requirements 32.4, 35.5). */}
          <Route
            path="/partner/dashboard"
            element={
              <ProtectedRoute allowedRoles={[ROLES.DELIVERY_PARTNER]}>
                <PartnerDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/partner/history"
            element={
              <ProtectedRoute allowedRoles={[ROLES.DELIVERY_PARTNER]}>
                <DeliveryHistory />
              </ProtectedRoute>
            }
          />

          {/* Anything else. */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </>
  );
}
