import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./context/AuthContext.jsx";
import { CartProvider } from "./context/CartContext.jsx";
// Order matters: base rules first so component and cart styles can override them.
import "./styles/base.css";
import "./styles/components.css";
import "./styles/cart.css";

// AuthProvider uses useNavigate, so it sits inside the Router; CartProvider reads the
// auth state, so it sits inside AuthProvider.
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <App />
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
);
