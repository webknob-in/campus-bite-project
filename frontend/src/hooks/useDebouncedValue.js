// useDebouncedValue: returns `value` after it has stopped changing for `delay` ms.
// Search boxes use it so a request is sent after the user pauses typing, not on every key.
import { useEffect, useState } from "react";

export default function useDebouncedValue(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
