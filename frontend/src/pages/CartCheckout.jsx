// Cart and checkout page (Requirements 10.2, 10.3, 10.5, 11.12, 33.4, 33.5).
// Editable cart lines (quantity 1-99, remove), subtotal, delivery details, and a mock card form.
// On submit the order is placed, the cart is cleared, and we go to the new order's detail page.
// Card data lives only in this component's state while the form is open. It is never logged,
// persisted, or put in the URL, and it is wiped as soon as the order is accepted.
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { useCart } from "../context/CartContext.jsx";
import { MAX_QUANTITY, MIN_QUANTITY } from "../context/cartReducer.js";
import { placeOrder } from "../api/orders.js";
import { getErrorMessage } from "../api/client.js";
import FormField from "../components/FormField.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import {
  ADDRESS_MAX,
  buildOrderPayload,
  formatPrice,
  lineTotal,
  validateCheckout,
} from "../utils/checkoutFormat.js";
import "../styles/pages/CartCheckout.css";

const EMPTY_CARD = { cardHolder: "", cardNumber: "", expiry: "", cvv: "" };

/** Quantity input that only commits whole numbers from 1 to 99. */
function QuantityInput({ line, disabled, onChange }) {
  const [draft, setDraft] = useState(null); // null: show the real quantity
  const shown = draft ?? String(line.quantity);
  const parsed = Number(shown);
  const invalid = draft !== null && !(Number.isInteger(parsed) && parsed >= MIN_QUANTITY && parsed <= MAX_QUANTITY);
  const errorId = `qty-error-${line.id}`;

  const handleChange = (event) => {
    const text = event.target.value;
    const value = Number(text);
    if (text !== "" && Number.isInteger(value) && value >= MIN_QUANTITY && value <= MAX_QUANTITY) {
      setDraft(null);
      onChange(line.id, value);
    } else {
      setDraft(text);
    }
  };

  return (
    <div className="checkout-qty">
      <input
        type="number"
        inputMode="numeric"
        min={MIN_QUANTITY}
        max={MAX_QUANTITY}
        step={1}
        value={shown}
        onChange={handleChange}
        onBlur={() => setDraft(null)}
        disabled={disabled}
        aria-label={`Quantity for ${line.name}`}
        aria-invalid={invalid ? "true" : undefined}
        aria-describedby={invalid ? errorId : undefined}
      />
      {invalid && (
        <p id={errorId} className="field-error" role="alert">
          Enter {MIN_QUANTITY} to {MAX_QUANTITY}.
        </p>
      )}
    </div>
  );
}

export default function CartCheckout() {
  const { user } = useAuth();
  const { items, restaurantName, count, subtotal, updateQuantity, removeItem, clearCart } = useCart();
  const navigate = useNavigate();

  const [values, setValues] = useState(() => ({
    address: user?.address ?? "",
    phone: user?.phone ?? "",
    ...EMPTY_CARD,
  }));
  const [touched, setTouched] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);

  if (items.length === 0) {
    return (
      <main className="checkout-page">
        <h1 className="page-title">Your cart</h1>
        <div className="checkout-empty">
          <p>Your cart is empty.</p>
          <Link to="/restaurants" className="btn">
            Browse restaurants
          </Link>
        </div>
      </main>
    );
  }

  const errors = validateCheckout(values);
  const visibleError = (name) => (submitted || touched[name] ? errors[name] : undefined);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
  };

  const handleCardNumberChange = (event) => {
    const value = event.target.value.replace(/[^\d\s]/g, "");
    setValues((current) => ({ ...current, cardNumber: value }));
  };

  const handleExpiryChange = (event) => {
    // Keep digits and slashes; collapse repeats so typing "/" after the auto-added one is harmless.
    const value = event.target.value.replace(/[^\d/]/g, "").replace(/\/{2,}/g, "/");
    setValues((current) => {
      // Add the slash after two digits when typing forward (not when deleting).
      const typingForward = value.length > current.expiry.length;
      const next = typingForward && /^\d{2}$/.test(value) ? `${value}/` : value;
      return { ...current, expiry: next };
    });
  };

  const handleCvvChange = (event) => {
    const value = event.target.value.replace(/\D/g, "").slice(0, 3);
    setValues((current) => ({ ...current, cvv: value }));
  };

  const handleBlur = (event) => {
    const { name } = event.target;
    setTouched((current) => ({ ...current, [name]: true }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (inFlight.current) return;
    setSubmitted(true);
    setSubmitError(null);
    if (Object.keys(errors).length > 0) return;

    inFlight.current = true;
    setPending(true);
    try {
      const order = await placeOrder(buildOrderPayload(items, values));
      // Drop the card details from state before leaving the page.
      setValues((current) => ({ ...current, ...EMPTY_CARD }));
      clearCart();
      navigate(`/orders/${order.id}`);
    } catch (error) {
      setSubmitError(getErrorMessage(error));
      inFlight.current = false;
      setPending(false);
    }
  };

  const field = (name, label, extra = {}) => (
    <FormField
      label={label}
      name={name}
      value={values[name]}
      onChange={handleChange}
      onBlur={handleBlur}
      error={visibleError(name)}
      disabled={pending}
      required
      {...extra}
    />
  );

  return (
    <main className="checkout-page">
      <h1 className="page-title">Your cart</h1>
      {restaurantName && (
        <p className="checkout-restaurant">
          Ordering from <strong>{restaurantName}</strong> ({count} {count === 1 ? "item" : "items"})
        </p>
      )}

      <div className="checkout-layout">
        <section className="checkout-lines" aria-labelledby="cart-items-title">
          <h2 id="cart-items-title">Items</h2>
          <ul className="checkout-line-list">
            {items.map((line) => (
              <li key={line.id} className="checkout-line">
                <div className="checkout-line-info">
                  <span className="checkout-line-name">{line.name}</span>
                  <span className="checkout-line-price">{formatPrice(line.price)} each</span>
                </div>
                <QuantityInput line={line} disabled={pending} onChange={updateQuantity} />
                <span className="checkout-line-total">{formatPrice(lineTotal(line.price, line.quantity))}</span>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => removeItem(line.id)}
                  disabled={pending}
                  aria-label={`Remove ${line.name} from cart`}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <p className="checkout-subtotal">
            <span>Subtotal</span>
            <strong>{formatPrice(subtotal)}</strong>
          </p>
        </section>

        <form className="checkout-form" onSubmit={handleSubmit} noValidate aria-labelledby="checkout-title">
          <h2 id="checkout-title">Delivery and payment</h2>

          {submitError && <ErrorMessage message={submitError} />}

          <fieldset className="checkout-fieldset" disabled={pending}>
            <legend>Delivery details</legend>
            {field("address", "Delivery address", {
              as: "textarea",
              rows: 3,
              maxLength: ADDRESS_MAX,
              autoComplete: "street-address",
            })}
            {field("phone", "Phone", { type: "tel", autoComplete: "tel" })}
          </fieldset>

          <fieldset className="checkout-fieldset" disabled={pending}>
            <legend>Payment (mock, no real charge)</legend>
            {field("cardHolder", "Card holder", { autoComplete: "off", maxLength: 100 })}
            {field("cardNumber", "Card number", {
              onChange: handleCardNumberChange,
              inputMode: "numeric",
              autoComplete: "off",
              maxLength: 23,
              placeholder: "1234 5678 9012 3456",
            })}
            <div className="checkout-card-row">
              {field("expiry", "Expiry (MM/YY)", {
                onChange: handleExpiryChange,
                inputMode: "numeric",
                autoComplete: "off",
                maxLength: 5,
                placeholder: "MM/YY",
              })}
              {field("cvv", "CVV", {
                onChange: handleCvvChange,
                inputMode: "numeric",
                autoComplete: "off",
                maxLength: 3,
                placeholder: "123",
              })}
            </div>
          </fieldset>

          <button type="submit" className="btn btn-block" disabled={pending}>
            Pay (mock) &amp; Place Order
          </button>
        </form>
      </div>
    </main>
  );
}
