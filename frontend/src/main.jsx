import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles/base.css";

// Placeholder entry point. Task 12.7 wraps <App /> with BrowserRouter,
// AuthProvider, and CartProvider.
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
