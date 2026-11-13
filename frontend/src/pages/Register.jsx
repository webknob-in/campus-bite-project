// Register page (Requirements 4.2, 4.3, 5.9, 33.4, 33.5, 35.1).
// Role picker (Customer / Restaurant Owner / Delivery Partner); Restaurant Owners also give the
// restaurant details, sent as a nested `restaurant` object (RegisterIn in the design).
// AuthContext.register creates the account and logs in; then we navigate to the role home.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { getErrorMessage } from "../api/client.js";
import { ROLES, roleHome } from "../utils/roles.js";
import FormField from "../components/FormField.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import "../styles/pages/Login.css";
import "../styles/pages/Register.css";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_PATTERN = /^[0-9+\-\s]{7,20}$/;

const ROLE_OPTIONS = [
  { value: ROLES.CUSTOMER, label: "Customer", description: "Browse restaurants and order food." },
  {
    value: ROLES.RESTAURANT_OWNER,
    label: "Restaurant Owner",
    description: "Manage your restaurant, menu, and orders.",
  },
  {
    value: ROLES.DELIVERY_PARTNER,
    label: "Delivery Partner",
    description: "Pick up and deliver orders.",
  },
];

const INITIAL_VALUES = {
  role: ROLES.CUSTOMER,
  name: "",
  email: "",
  password: "",
  phone: "",
  address: "",
  restaurantName: "",
  restaurantDescription: "",
  restaurantCuisine: "",
  restaurantAddress: "",
  restaurantImageUrl: "",
};

function lengthError(label, value, min, max) {
  const length = value.trim().length;
  if (length === 0) return `${label} is required.`;
  if (length < min) return `${label} must be at least ${min} characters.`;
  if (length > max) return `${label} must be at most ${max} characters.`;
  return undefined;
}

function isHttpUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function validateRegister(values) {
  const errors = {};
  const set = (key, message) => {
    if (message) errors[key] = message;
  };

  set("name", lengthError("Name", values.name, 2, 100));

  if (!values.email.trim()) errors.email = "Email is required.";
  else if (!EMAIL_PATTERN.test(values.email.trim())) errors.email = "Enter a valid email address.";

  if (!values.password) errors.password = "Password is required.";
  else if (values.password.length < 8) errors.password = "Password must be at least 8 characters.";
  else if (values.password.length > 72) errors.password = "Password must be at most 72 characters.";

  if (!values.phone.trim()) errors.phone = "Phone number is required.";
  else if (!PHONE_PATTERN.test(values.phone.trim())) {
    errors.phone = "Enter 7 to 20 digits; spaces, + and - are allowed.";
  }

  if (values.address.trim().length > 300) errors.address = "Address must be at most 300 characters.";

  if (values.role === ROLES.RESTAURANT_OWNER) {
    set("restaurantName", lengthError("Restaurant name", values.restaurantName, 2, 120));
    set("restaurantDescription", lengthError("Description", values.restaurantDescription, 1, 1000));
    set("restaurantCuisine", lengthError("Cuisine", values.restaurantCuisine, 2, 60));
    set("restaurantAddress", lengthError("Restaurant address", values.restaurantAddress, 5, 300));
    const imageUrl = values.restaurantImageUrl.trim();
    if (imageUrl && !isHttpUrl(imageUrl)) {
      errors.restaurantImageUrl = "Enter a valid http(s) URL.";
    }
  }
  return errors;
}

export function buildRegisterPayload(values) {
  const payload = {
    name: values.name.trim(),
    email: values.email.trim(),
    password: values.password,
    phone: values.phone.trim(),
    role: values.role,
  };
  const address = values.address.trim();
  if (address && values.role !== ROLES.RESTAURANT_OWNER) payload.address = address;

  if (values.role === ROLES.RESTAURANT_OWNER) {
    const imageUrl = values.restaurantImageUrl.trim();
    payload.restaurant = {
      name: values.restaurantName.trim(),
      description: values.restaurantDescription.trim(),
      cuisine: values.restaurantCuisine.trim(),
      address: values.restaurantAddress.trim(),
      ...(imageUrl ? { image_url: imageUrl } : {}),
    };
  }
  return payload;
}

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [values, setValues] = useState(INITIAL_VALUES);
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [pending, setPending] = useState(false);

  const isOwner = values.role === ROLES.RESTAURANT_OWNER;

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    if (errors[name]) setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (pending) return;

    const found = validateRegister(values);
    setErrors(found);
    setSubmitError(null);
    if (Object.keys(found).length > 0) return;

    setPending(true);
    try {
      const user = await register(buildRegisterPayload(values));
      navigate(roleHome(user.role), { replace: true });
    } catch (error) {
      setSubmitError(getErrorMessage(error));
      setPending(false);
    }
  };

  const field = (name, label, extra = {}) => (
    <FormField
      label={label}
      name={name}
      value={values[name]}
      onChange={handleChange}
      error={errors[name]}
      disabled={pending}
      {...extra}
    />
  );

  return (
    <main className="auth-page">
      <section className="auth-card auth-card--wide" aria-labelledby="register-title">
        <h1 id="register-title" className="page-title">
          Create your account
        </h1>
        <p className="auth-subtitle">Join CampusBite as a customer, restaurant owner, or delivery partner.</p>

        {submitError && <ErrorMessage message={submitError} />}

        <form onSubmit={handleSubmit} noValidate className="auth-form">
          <fieldset className="role-picker" disabled={pending}>
            <legend>I am a</legend>
            <div className="role-picker-options">
              {ROLE_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={`role-card${values.role === option.value ? " role-card--selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="role"
                    value={option.value}
                    checked={values.role === option.value}
                    onChange={handleChange}
                  />
                  <span className="role-card-title">{option.label}</span>
                  <span className="role-card-description">{option.description}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {field("name", "Full name", { autoComplete: "name", required: true, maxLength: 100 })}
          {field("email", "Email", { type: "email", autoComplete: "email", required: true })}
          {field("password", "Password", {
            type: "password",
            autoComplete: "new-password",
            required: true,
            hint: "At least 8 characters.",
          })}
          {field("phone", "Phone", { type: "tel", autoComplete: "tel", required: true })}
          {!isOwner &&
            field("address", "Address (optional)", { autoComplete: "street-address", maxLength: 300 })}

          {isOwner && (
            <fieldset className="restaurant-details" disabled={pending}>
              <legend>Restaurant details</legend>
              {field("restaurantName", "Restaurant name", { required: true, maxLength: 120 })}
              {field("restaurantDescription", "Description", {
                as: "textarea",
                rows: 3,
                required: true,
                maxLength: 1000,
              })}
              {field("restaurantCuisine", "Cuisine", { required: true, maxLength: 60 })}
              {field("restaurantAddress", "Restaurant address", { required: true, maxLength: 300 })}
              {field("restaurantImageUrl", "Image URL (optional)", { type: "url", inputMode: "url" })}
            </fieldset>
          )}

          <button type="submit" className="btn btn-block" disabled={pending}>
            {pending ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="auth-switch">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </section>
    </main>
  );
}
