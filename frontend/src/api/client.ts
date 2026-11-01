/**
 * The one place a `fetch` is issued.
 *
 * Every failure — network, non-2xx, malformed body — surfaces as an `ApiError`,
 * so callers have exactly one thing to catch and `unknown` never leaks into a
 * component. The session is an httpOnly cookie, hence `credentials: "include"`
 * and no Authorization header anywhere in this app.
 */

import type { ApiErrorEnvelope } from "./types";

const BASE = "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** 0 is our sentinel for "the request never reached the server". */
  get isNetworkError(): boolean {
    return this.status === 0;
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }
}

/** Narrowing helper so callers never need a cast. */
export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

function looksLikeEnvelope(body: unknown): body is ApiErrorEnvelope {
  if (typeof body !== "object" || body === null) return false;
  const err = (body as { error?: unknown }).error;
  return typeof err === "object" && err !== null && "message" in err;
}

async function toApiError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // A proxy or crash can return HTML; fall through to the generic message.
  }

  if (looksLikeEnvelope(body)) {
    const { code, message, details } = body.error;
    return new ApiError(res.status, code || "unknown", message, details);
  }

  return new ApiError(res.status, "unknown", `Request failed (HTTP ${res.status}).`);
}

export interface RequestOptions {
  method?: string;
  /** Serialised as JSON. Use `formData` for multipart instead. */
  body?: unknown;
  formData?: FormData;
  query?: Record<string, string | number | boolean | null | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query: RequestOptions["query"]): string {
  const url = `${BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    // An empty filter is an absent filter, not `?q=`.
    if (value === null || value === undefined || value === "") continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, formData, query, signal } = opts;

  const headers: Record<string, string> = {};
  let payload: BodyInit | undefined;
  if (formData) {
    // Let the browser set the multipart boundary; setting Content-Type breaks it.
    payload = formData;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: payload,
      signal,
      credentials: "include",
    });
  } catch (cause) {
    // Aborts are the caller's own doing and must stay distinguishable from a
    // dead network, otherwise React Query shows a toast on every navigation.
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    const message = cause instanceof Error ? cause.message : "Network request failed.";
    throw new ApiError(0, "network_error", message, cause);
  }

  if (!res.ok) throw await toApiError(res);

  // 204 and friends have no body; `as T` is the honest cast for a void endpoint.
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }

  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError(res.status, "invalid_response", "The server returned malformed JSON.");
  }
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"], signal?: AbortSignal) =>
    request<T>(path, { query, signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", formData }),
};
