import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError, isApiError } from "./client";
import { errorMessage } from "../lib/errors";
import { toastFromOutsideReact } from "../components/ui/toast-context";
import { navigateTo, currentPath } from "../lib/navigation";

declare module "@tanstack/react-query" {
  interface Register {
    defaultError: ApiError;
    queryMeta: {
      /** Suppresses the global toast — for queries whose failure the screen
          already renders itself, and for `me`, whose 401 is normal. */
      silent?: boolean;
    };
    mutationMeta: { silent?: boolean };
  }
}

/**
 * Every failure lands here, so a screen only writes an error handler when it
 * needs something *more* than a toast. A 401 means the cookie expired: clear
 * the cache so a stale page cannot flash behind the login form, and redirect.
 */
function handleError(
  error: unknown,
  silent: boolean | undefined,
  client: QueryClient,
  /** True for the `me` query, whose 401 is the ordinary logged-out answer. */
  isSessionProbe = false,
) {
  if (isApiError(error) && error.isAuthError) {
    // ProtectedRoute already redirects on a failed `me`. Clearing the cache
    // here would evict that very query, refetch it, and loop.
    if (isSessionProbe) return;
    if (currentPath() !== "/login") {
      client.clear();
      navigateTo("/login", { replace: true });
    }
    return;
  }
  if (silent) return;
  toastFromOutsideReact(errorMessage(error), "error");
}

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) =>
        handleError(error, query.meta?.silent, client, query.queryKey[0] === "me"),
    }),
    mutationCache: new MutationCache({
      onError: (error, _vars, _ctx, mutation) =>
        handleError(error, mutation.meta?.silent, client),
    }),
    defaultOptions: {
      queries: {
        retry: (failureCount, error) => {
          // Retrying a 4xx just delays the error the user needs to see.
          if (isApiError(error) && error.status >= 400 && error.status < 500) return false;
          return failureCount < 1;
        },
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
      mutations: { retry: false },
    },
  });

  return client;
}
