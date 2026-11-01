import { useCallback, useEffect, useRef } from "react";

/**
 * Returns a stable function that defers its call by `delay`, cancelling the
 * previous one. Used to keep a search box responsive while the URL — and the
 * request it drives — only updates once the user stops typing.
 */
export function useDebouncedCallback<A extends unknown[]>(
  fn: (...args: A) => void,
  delay = 300,
): (...args: A) => void {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef(fn);

  // Kept current in an effect rather than during render, so the deferred call
  // always runs the newest closure without a render-phase side effect.
  useEffect(() => {
    latest.current = fn;
  });

  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current);
    },
    [],
  );

  return useCallback(
    (...args: A) => {
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = setTimeout(() => latest.current(...args), delay);
    },
    [delay],
  );
}
