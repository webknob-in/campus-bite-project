import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import useAsync from "../hooks/useAsync.js";

// Promise whose settlement the test controls.
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useAsync", () => {
  it("starts loading and then exposes the resolved data", async () => {
    const { result } = renderHook(() => useAsync(() => Promise.resolve({ items: [1, 2] })));

    expect(result.current).toMatchObject({ data: null, loading: true, error: null });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current).toMatchObject({ data: { items: [1, 2] }, error: null });
  });

  it("exposes the backend detail as the error and clears data", async () => {
    const failure = { response: { status: 404, data: { detail: "Restaurant not found" } } };
    const { result } = renderHook(() => useAsync(() => Promise.reject(failure)));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current).toMatchObject({ data: null, error: "Restaurant not found" });
  });

  it("uses the generic network message when no response was received", async () => {
    const { result } = renderHook(() => useAsync(() => Promise.reject(new Error("Network Error"))));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toMatch(/network error/i);
  });

  it("turns a synchronous throw from the function into an error", async () => {
    const { result } = renderHook(() =>
      useAsync(() => {
        throw { response: { status: 500, data: { detail: "Internal server error" } } };
      })
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Internal server error");
  });

  it("reload runs the function again, shows loading, and clears a previous error", async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce({ response: { status: 500, data: { detail: "Boom" } } })
      .mockResolvedValueOnce("recovered");
    const { result } = renderHook(() => useAsync(fn));

    await waitFor(() => expect(result.current.error).toBe("Boom"));
    act(() => result.current.reload());
    expect(result.current).toMatchObject({ loading: true, error: null, data: null });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current).toMatchObject({ data: "recovered", error: null });
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("re-runs when deps change and ignores a stale response that arrives late", async () => {
    const first = deferred();
    const second = deferred();
    const responses = { 1: first.promise, 2: second.promise };
    const { result, rerender } = renderHook(({ id }) => useAsync(() => responses[id], [id]), {
      initialProps: { id: 1 },
    });

    rerender({ id: 2 });
    await act(async () => second.resolve("restaurant 2"));
    await waitFor(() => expect(result.current.data).toBe("restaurant 2"));

    await act(async () => first.resolve("restaurant 1")); // slow response for the old deps
    expect(result.current).toMatchObject({ data: "restaurant 2", loading: false, error: null });
  });

  it("does not run the function again when deps are unchanged", async () => {
    const fn = vi.fn().mockResolvedValue("ok");
    const { result, rerender } = renderHook(({ id }) => useAsync(fn, [id]), { initialProps: { id: 1 } });

    await waitFor(() => expect(result.current.loading).toBe(false));
    rerender({ id: 1 });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("ignores a response that settles after unmount", async () => {
    const pending = deferred();
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { unmount } = renderHook(() => useAsync(() => pending.promise));

    unmount();
    await act(async () => pending.resolve("late"));
    expect(errorSpy).not.toHaveBeenCalled();
    errorSpy.mockRestore();
  });
});
