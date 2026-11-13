// AuthContext: session state, persisted in localStorage (Requirements 5.4, 5.5, 5.7, 5.8, 32.5).
//
// - State `{user, token}` is restored from `campusbite_token` / `campusbite_user` on load.
//   Corrupt or incomplete stored data is discarded instead of crashing the app.
// - `login` and `register` store the token and user; `logout` removes the token, the user,
//   and the cart from localStorage.
// - An effect registers the API_Client's 401 handler: log out, then navigate to /login.
//
// AuthProvider must be rendered inside a Router because it uses `useNavigate`.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as authApi from "../api/auth.js";
import { CART_KEY, TOKEN_KEY, USER_KEY, setUnauthorizedHandler } from "../api/client.js";

const AuthContext = createContext(null);

function removeKeys(...keys) {
  try {
    keys.forEach((key) => localStorage.removeItem(key));
  } catch {
    // Storage unavailable (private mode, quota): nothing to remove.
  }
}

function readStoredSession() {
  const empty = { user: null, token: null };
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const rawUser = localStorage.getItem(USER_KEY);
    if (!token || !rawUser) {
      if (token || rawUser) removeKeys(TOKEN_KEY, USER_KEY);
      return empty;
    }
    const user = JSON.parse(rawUser);
    if (user && typeof user === "object" && !Array.isArray(user) && user.role) {
      return { user, token };
    }
  } catch {
    // Corrupt JSON or unreadable storage: fall through and discard the session.
  }
  removeKeys(TOKEN_KEY, USER_KEY);
  return empty;
}

function writeSession(token, user) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    // The session still works for this page load; it just will not survive a refresh.
  }
}

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [session, setSession] = useState(readStoredSession);

  const logout = useCallback(() => {
    removeKeys(TOKEN_KEY, USER_KEY, CART_KEY);
    setSession({ user: null, token: null });
  }, []);

  /** Logs in with email and password. Resolves to the user profile; rejects with the Axios error. */
  const login = useCallback(async (email, password) => {
    const { access_token: token, user } = await authApi.login(email, password);
    writeSession(token, user);
    setSession({ user, token });
    return user;
  }, []);

  /** Creates the account, then logs in with the same credentials. Resolves to the user profile. */
  const register = useCallback(
    async (payload) => {
      await authApi.register(payload);
      return login(payload.email, payload.password);
    },
    [login]
  );

  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout();
      navigate("/login", { replace: true });
    });
    return () => setUnauthorizedHandler();
  }, [logout, navigate]);

  const value = useMemo(
    () => ({
      user: session.user,
      token: session.token,
      isAuthenticated: Boolean(session.token && session.user),
      role: session.user?.role ?? null,
      login,
      register,
      logout,
    }),
    [session, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}

export default AuthContext;
