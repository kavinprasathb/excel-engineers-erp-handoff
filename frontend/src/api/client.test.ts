import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { ApiError, api, isApiError, request } from "./client";

describe("the API client", () => {
  it("turns the contract's error envelope into a typed ApiError", async () => {
    server.use(
      http.post("/api/inventory/12/adjust", () =>
        HttpResponse.json(
          {
            error: {
              code: "insufficient_stock",
              message: "Only 3 in stock; cannot remove 5.",
              details: { in_stock: 3, requested: 5 },
            },
          },
          { status: 409 },
        ),
      ),
    );

    const thrown = await api.post("/inventory/12/adjust", { delta: -5 }).catch((e: unknown) => e);

    expect(isApiError(thrown)).toBe(true);
    const error = thrown as ApiError;
    expect(error.status).toBe(409);
    expect(error.code).toBe("insufficient_stock");
    expect(error.message).toBe("Only 3 in stock; cannot remove 5.");
    expect(error.details).toEqual({ in_stock: 3, requested: 5 });
  });

  it("still produces an ApiError when the body is not an envelope", async () => {
    server.use(
      http.get("/api/settings", () => new HttpResponse("<html>502</html>", { status: 502 })),
    );

    const thrown = (await api.get("/settings").catch((e: unknown) => e)) as ApiError;

    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown.status).toBe(502);
    expect(thrown.code).toBe("unknown");
    expect(thrown.message).toContain("502");
  });

  it("reports an unreachable server as a network error, not an HTTP one", async () => {
    server.use(http.get("/api/health", () => HttpResponse.error()));

    const thrown = (await api.get("/health").catch((e: unknown) => e)) as ApiError;

    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown.status).toBe(0);
    expect(thrown.isNetworkError).toBe(true);
  });

  it("marks 401 so the global handler can redirect", async () => {
    server.use(
      http.get("/api/auth/me", () =>
        HttpResponse.json(
          { error: { code: "not_authenticated", message: "Sign in to continue." } },
          { status: 401 },
        ),
      ),
    );

    const thrown = (await api.get("/auth/me").catch((e: unknown) => e)) as ApiError;

    expect(thrown.isAuthError).toBe(true);
    expect(thrown.code).toBe("not_authenticated");
  });

  it("returns undefined for a 204 rather than choking on an empty body", async () => {
    server.use(http.post("/api/auth/logout", () => new HttpResponse(null, { status: 204 })));

    await expect(api.post<void>("/auth/logout")).resolves.toBeUndefined();
  });

  it("sends the session cookie and drops empty query params", async () => {
    let seenUrl = "";
    let seenCredentials = "";
    server.use(
      http.get("/api/products", ({ request: req }) => {
        seenUrl = req.url;
        seenCredentials = req.credentials;
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25, pages: 0 });
      }),
    );

    await request("/products", { query: { q: "", page: 2, supplier_id: null, is_active: true } });

    expect(seenCredentials).toBe("include");
    expect(seenUrl).toContain("page=2");
    expect(seenUrl).toContain("is_active=true");
    expect(seenUrl).not.toContain("q=");
    expect(seenUrl).not.toContain("supplier_id");
  });
});
