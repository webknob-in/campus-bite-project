// CartContext: cart state with localStorage persistence (Requirements 10.1-10.4, 10.6, 10.7, 32.5).
//
// - State comes from `cartReducer`, initialized from `campusbite_cart` (corrupt data gives an empty cart).
// - An effect writes the cart whenever it changes; an empty cart removes the key.
// - `addItem(menuItem, restaurant)` adds directly when the cart is empty or from the same restaurant.
//   For a different restaurant it opens a confirm dialog; the cart is replaced only after confirming.
// - When the user logs out, the in-memory cart is cleared so the old cart cannot be written back.
//
// CartProvider must be rendered inside AuthProvider.
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { CART_KEY } from "../api/client.js";
import Modal from "../components/Modal.jsx";
import { useAuth } from "./AuthContext.jsx";
import { cartCount, cartReducer, cartSubtotal, deserializeCart, initialCart, serializeCart } from "./cartReducer.js";
import "../styles/cart.css";

const CartContext = createContext(null);

function readStoredCart() {
  try {
    return deserializeCart(localStorage.getItem(CART_KEY));
  } catch {
    return initialCart;
  }
}

export function CartProvider({ children }) {
  const { isAuthenticated } = useAuth();
  const [cart, dispatch] = useReducer(cartReducer, undefined, readStoredCart);
  const [pendingSwitch, setPendingSwitch] = useState(null); // { item, restaurant } awaiting confirmation
  const cartRef = useRef(cart);
  cartRef.current = cart;

  // Persist on change.
  useEffect(() => {
    try {
      if (cart.items.length === 0) localStorage.removeItem(CART_KEY);
      else localStorage.setItem(CART_KEY, serializeCart(cart));
    } catch {
      // Storage unavailable or full: the cart still works until the page reloads.
    }
  }, [cart]);

  // Clear the cart when a signed-in user logs out.
  const wasAuthenticated = useRef(isAuthenticated);
  useEffect(() => {
    if (wasAuthenticated.current && !isAuthenticated) {
      dispatch({ type: "CLEAR" });
      setPendingSwitch(null);
    }
    wasAuthenticated.current = isAuthenticated;
  }, [isAuthenticated]);

  const addItem = useCallback((item, restaurant) => {
    const current = cartRef.current;
    if (current.restaurantId === null || current.restaurantId === restaurant.id) {
      dispatch({ type: "ADD", item, restaurant });
    } else {
      setPendingSwitch({ item, restaurant });
    }
  }, []);

  const updateQuantity = useCallback((id, quantity) => dispatch({ type: "UPDATE", id, quantity }), []);
  const removeItem = useCallback((id) => dispatch({ type: "REMOVE", id }), []);
  const clearCart = useCallback(() => dispatch({ type: "CLEAR" }), []);

  const cancelSwitch = useCallback(() => setPendingSwitch(null), []);
  const confirmSwitch = useCallback(() => {
    if (pendingSwitch) dispatch({ type: "REPLACE", item: pendingSwitch.item, restaurant: pendingSwitch.restaurant });
    setPendingSwitch(null);
  }, [pendingSwitch]);

  const value = useMemo(
    () => ({
      cart,
      items: cart.items,
      restaurantId: cart.restaurantId,
      restaurantName: cart.restaurantName,
      count: cartCount(cart),
      subtotal: cartSubtotal(cart),
      addItem,
      updateQuantity,
      removeItem,
      clearCart,
    }),
    [cart, addItem, updateQuantity, removeItem, clearCart]
  );

  return (
    <CartContext.Provider value={value}>
      {children}
      {pendingSwitch && (
        <Modal
          title="Start a new cart?"
          onClose={cancelSwitch}
          footer={
            <>
              <button type="button" className="btn btn-secondary" onClick={cancelSwitch}>
                Cancel
              </button>
              <button type="button" className="btn" onClick={confirmSwitch}>
                Clear cart and add
              </button>
            </>
          }
        >
          <p className="cart-switch-message">
            Your cart has items from {cart.restaurantName || "another restaurant"}. Adding{" "}
            {pendingSwitch.item.name} from {pendingSwitch.restaurant.name} will clear your current cart.
          </p>
        </Modal>
      )}
    </CartContext.Provider>
  );
}

export function useCart() {
  const context = useContext(CartContext);
  if (!context) throw new Error("useCart must be used within a CartProvider");
  return context;
}

export default CartContext;
