import { AxiosError } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import client, { NETWORK_ERROR_MESSAGE, TOKEN_KEY, getErrorMessage, setUnauthorizedHandler } from "../api/client";

// Requirements 5.6, 5.8, 49.2, 49.4. Interceptor and getErrorMessage behavior through the
// shared Axios instance, with the network adapter replaced. Endpoint wrappers are covered
// in api.layer.test.js.

const originalAdapter = client.defaults.adapter;
let sent;

function respondWith(status, data = {}) {
  client.defaults.adapter = async (config) => {
    sent.push(config);
    const response = { status, statusText: "", headers: {}, config, data };
    if (status >= 400) {
      throw new AxiosError(`status ${status}`, AxiosError.ERR_BAD_REQUEST, config, null, response);
    }
    return response;
  };
}

function failWithNetworkError() {
  client.defaults.adapter = async (config) => {
    sent.push(config);
    throw new AxiosError("Network Error", AxiosError.ERR_NETWORK, config, {});
  };
}

beforeEach(() => {
  sent = [];
  localStorage.clear();
  respondWith(200);
});

afterEach(() => {
  client.defaults.adapter = originalAdapter;
  setUnauthorizedHandler();
  localStorage.clear();
});

describe("request interceptor", () => {
  it("attaches Authorization: Bearer <token> when a token is stored", async () => {
    localStorage.setItem(TOKEN_KEY, "abc.def.ghi");
    await client.get("/anything");
    expect(sent[0].headers.get("Authorization")).toBe("Bearer abc.def.ghi");
  });

  it("omits the Authorization header when no token is stored", async () => {
    await client.get("/anything");
    expect(sent[0].headers.get("Authorization")).toBeFalsy();
  });

  it("reads the token on every request, so a later login is picked up", async () => {
    await client.get("/a");
    localStorage.setItem(TOKEN_KEY, "later");
    await client.get("/b");
    expect(sent[0].headers.get("Authorization")).toBeFalsy();
    expect(sent[1].headers.get("Authorization")).toBe("Bearer later");
  });
});

describe("401 handling", () => {
  it("invokes the registered handler once and still rejects the call", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    localStorage.setItem(TOKEN_KEY, "expired");
    respondWith(401, { detail: "Token expired" });

    await expect(client.get("/auth/me")).rejects.toMatchObject({ response: { status: 401 } });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not invoke the handler once it has been cleared", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    setUnauthorizedHandler();
    localStorage.setItem(TOKEN_KEY, "expired");
    respondWith(401);

    await expect(client.get("/auth/me")).rejects.toBeDefined();
    expect(handler).not.toHaveBeenCalled();
  });

  it("ignores 401 responses when no token is stored", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    respondWith(401, { detail: "Invalid email or password" });

    await expect(client.post("/auth/login", {})).rejects.toBeDefined();
    expect(handler).not.toHaveBeenCalled();
  });

  it("does not treat a network failure as a 401", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    localStorage.setItem(TOKEN_KEY, "jwt");
    failWithNetworkError();

    await expect(client.get("/x")).rejects.toBeDefined();
    expect(handler).not.toHaveBeenCalled();
  });
});

describe("getErrorMessage with real Axios errors", () => {
  it("returns a string detail as is", async () => {
    respondWith(409, { detail: "Email already registered" });
    const error = await client.post("/auth/register", {}).catch((e) => e);
    expect(getErrorMessage(error)).toBe("Email already registered");
  });

  it("joins the msg values of a list detail", async () => {
    respondWith(422, { detail: [{ msg: "Field required" }, { msg: "Invalid phone" }] });
    const error = await client.post("/auth/register", {}).catch((e) => e);
    expect(getErrorMessage(error)).toBe("Field required, Invalid phone");
  });

  it("returns the network message when the request never got a response", async () => {
    failWithNetworkError();
    const error = await client.get("/x").catch((e) => e);
    expect(error.response).toBeUndefined();
    expect(getErrorMessage(error)).toBe(NETWORK_ERROR_MESSAGE);
  });

  it("reads detail.message from an object detail", () => {
    expect(getErrorMessage({ response: { status: 400, data: { detail: { message: "Restaurant closed" } } } })).toBe(
      "Restaurant closed"
    );
  });
});
