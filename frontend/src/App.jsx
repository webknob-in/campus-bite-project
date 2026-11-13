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

          {/* Task 14.6: remaining customer routes (orders, customer dashboard, insights). */}
          {/* Task 15.4: restaurant owner routes (/owner/*). */}
          {/* Task 16.3: delivery partner routes (/partner/*). */}

          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </>
  );
}
