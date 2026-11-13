// Login page (Requirements 5.9, 33.4, 33.5, 35.1).
// Validates email and password inline, shows backend errors with getErrorMessage, and on success
// navigates to the page the user was sent from (ProtectedRoute's `state.from`) or to the role home.
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { getErrorMessage } from "../api/client.js";
import { roleHome } from "../utils/roles.js";
import FormField from "../components/FormField.jsx";
import ErrorMessage from "../components/ErrorMessage.jsx";
import "../styles/pages/Login.css";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateLogin({ email, password }) {
  const errors = {};
  if (!email.trim()) errors.email = "Email is required.";
  else if (!EMAIL_PATTERN.test(email.trim())) errors.email = "Enter a valid email address.";
  if (!password) errors.password = "Password is required.";
  return errors;
}

/** Turns the `from` location left by ProtectedRoute into a path, or null if there is none. */
function fromPath(from) {
  if (!from) return null;
  if (typeof from === "string") return from;
  if (typeof from.pathname === "string") return `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`;
  return null;
}

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [values, setValues] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [pending, setPending] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    if (errors[name]) setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (pending) return;

    const found = validateLogin(values);
    setErrors(found);
    setSubmitError(null);
    if (Object.keys(found).length > 0) return;

    setPending(true);
    try {
      const user = await login(values.email.trim(), values.password);
      navigate(fromPath(location.state?.from) ?? roleHome(user.role), { replace: true });
    } catch (error) {
      setSubmitError(getErrorMessage(error));
      setPending(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="login-title">
        <h1 id="login-title" className="page-title">
          Log in
        </h1>
        <p className="auth-subtitle">Welcome back to CampusBite.</p>

        {submitError && <ErrorMessage message={submitError} />}

        <form onSubmit={handleSubmit} noValidate className="auth-form">
          <FormField
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            value={values.email}
            onChange={handleChange}
            error={errors.email}
            disabled={pending}
            required
          />
          <FormField
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={values.password}
            onChange={handleChange}
            error={errors.password}
            disabled={pending}
            required
          />
          <button type="submit" className="btn btn-block" disabled={pending}>
            {pending ? "Logging in..." : "Log in"}
          </button>
        </form>

        <p className="auth-switch">
          New to CampusBite? <Link to="/register">Create an account</Link>
        </p>
      </section>
    </main>
  );
}
