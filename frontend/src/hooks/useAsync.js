// useAsync: runs an async function and exposes its outcome as `{data, loading, error, reload}`.
// Pages use it to show the Loader while a request is pending and the ErrorMessage when it
// fails (Requirements 32.2, 33.2, 33.3).
import { useCallback, useEffect, useState } from "react";
import { getErrorMessage } from "../api/client.js";

const PENDING = { data: null, loading: true, error: null };

/**
 * @param {() => Promise<any> | any} fn  Loader function, for example `() => getOrder(id)`.
 *   It is called on mount, whenever a value in `deps` changes, and on `reload()`. The closure
 *   from the render that triggered the run is used, so it always sees current props and state.
 * @param {Array} [deps]  Values that re-run `fn` when they change (like `useEffect` deps).
 *   The array length must stay the same between renders.
 * @returns {{data: any, loading: boolean, error: string | null, reload: () => void}}
 *   - `loading` is true from the start of a run until it settles.
 *   - `data` is the resolved value, or `null` while loading and after a failure.
 *   - `error` is a user-facing message from `getErrorMessage`, or `null`.
 *   - `reload` runs `fn` again; it is safe to pass straight to `ErrorMessage` `onRetry`.
 *
 * A run that is superseded (deps changed, `reload()` called again) or that finishes after the
 * component unmounted is ignored, so a slow earlier response cannot overwrite a newer one and no
 * state is set after unmount.
 */
export default function useAsync(fn, deps = []) {
  const [state, setState] = useState(PENDING);
  const [reloadCount, setReloadCount] = useState(0);

  useEffect(() => {
    let active = true;

    // Reuse the current state object when it is already "pending" to skip a redundant render.
    setState((prev) => (prev.loading && prev.data === null && prev.error === null ? prev : PENDING));

    // Wrapping in a promise turns a synchronous throw from `fn` into a normal failure.
    new Promise((resolve) => resolve(fn())).then(
      (data) => {
        if (active) setState({ data, loading: false, error: null });
      },
      (err) => {
        if (active) setState({ data: null, loading: false, error: getErrorMessage(err) });
      }
    );

    return () => {
      active = false;
    };
    // `fn` is intentionally excluded: callers pass an inline arrow that changes every render,
    // and `deps` is the caller's declaration of when to re-run.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadCount]);

  const reload = useCallback(() => setReloadCount((count) => count + 1), []);

  return { data: state.data, loading: state.loading, error: state.error, reload };
}
