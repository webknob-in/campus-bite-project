// App: Navbar above the routed page content (Requirements 1.4, 32.3, 35.1).
// Providers (BrowserRouter, AuthProvider, CartProvider) are set up in main.jsx.
import { Navigate, Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import PublicOnlyRoute from "./components/PublicOnlyRoute.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import NotFound from "./pages/NotFound.jsx";

export default function App() {
  return (
    <>
      <Navbar />
      <main className="container">
        <Routes>
          {/* Task 13.7: replace this temporary "/" redirect with the real "/" and the public
              browsing routes (/restaurants, /restaurants/:id, /dishes). */}
          <Route path="/" element={<Navigate to="/login" replace />} />

          {/* Auth pages: logged-in users are redirected to their role home. */}
          <Route element={<PublicOnlyRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
          </Route>

          {/* Task 14.6: customer routes (cart, checkout, orders, customer dashboard, insights). */}
          {/* Task 15.4: restaurant owner routes (/owner/*). */}
          {/* Task 16.3: delivery partner routes (/partner/*). */}

          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </>
  );
}
