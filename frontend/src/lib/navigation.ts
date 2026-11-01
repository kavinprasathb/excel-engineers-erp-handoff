/**
 * A slot for the router's `navigate`, so code outside the component tree — the
 * QueryClient's global error handler — can redirect without a full page reload.
 * Falls back to a hard navigation if nothing has registered yet.
 */

type Navigate = (to: string, opts?: { replace?: boolean }) => void;

let navigate: Navigate | null = null;

export function registerNavigate(fn: Navigate | null): void {
  navigate = fn;
}

export function navigateTo(to: string, opts?: { replace?: boolean }): void {
  if (navigate) {
    navigate(to, opts);
    return;
  }
  if (typeof window !== "undefined") window.location.assign(to);
}

export function currentPath(): string {
  return typeof window === "undefined" ? "/" : window.location.pathname;
}
