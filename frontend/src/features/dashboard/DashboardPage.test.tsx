import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/render";
import DashboardPage from "./DashboardPage";

const page = <T,>(items: T[]) => ({ items, total: items.length, page: 1, page_size: 25, pages: 1 });

const DASH = {
  buckets: {
    awaiting: { count: 2, total_paise: 200_000_00 },
    negotiating: { count: 1, total_paise: 50_000_00 },
    accepted: { count: 3, total_paise: 300_000_00 },
    declined: { count: 0, total_paise: 0 },
  },
  awaiting: [
    { id: 1, number: "Q-1", customer: "Acme", stage: 0, status: "pending", quote_date: "2020-01-01", updated_at: "2020-01-01", total_paise: 100_000_00, decline_reason: "" },
  ],
  negotiating: [],
  accepted: [],
  declined: [],
};

const ORDER = {
  id: 9,
  number: "ORD-9",
  status: "ready",
  quotation_id: 1,
  quotation_number: "Q-1",
  customer: { id: 1, name: "Acme Pumps" },
  delivered_at: null,
  created_at: "2026-09-30T10:00:00Z",
  total_paise: 12_345_00,
  lines: [],
};

function common(role: "admin" | "staff") {
  let analyticsCalls = 0;
  server.use(
    http.get("/api/auth/me", () => HttpResponse.json({ id: 1, email: "a@b.c", full_name: "A", role })),
    http.get("/api/quotations/dashboard", () => HttpResponse.json(DASH)),
    http.get("/api/orders", ({ request }) => {
      const s = new URL(request.url).searchParams.get("status");
      return HttpResponse.json(page(s === "waiting_stock" ? [] : [ORDER]));
    }),
    http.get("/api/purchase-orders", () => HttpResponse.json(page([]))),
    http.get("/api/inventory/summary", () =>
      HttpResponse.json({ total_products: 5, low_stock_count: 2, out_of_stock_count: 1, missing_supplier_count: 0, total_stock_value_paise: null }),
    ),
    http.get("/api/notifications", () =>
      HttpResponse.json({
        total: 1,
        counts: { critical: 0, warning: 1, info: 0 },
        by_category: { quotes: 1 },
        items: [
          { key: "quote-noreply-1", category: "quotes", severity: "warning", title: "Q-1 · Acme", detail: "No reply", link: "/quotations/1", days: 20 },
        ],
      }),
    ),
    http.get("/api/analytics", () => {
      analyticsCalls += 1;
      return HttpResponse.json({
        sales: { orders: 4, value_paise: 987_654_00, average_paise: 0, by_month: [] },
        products: [
          { description: "Mono-block pump", times_quoted: 3, qty_quoted: 9, value_quoted_paise: 1, times_won: 2, qty_won: 6, value_won_paise: 60_000_00, rate: 1 },
        ],
      });
    }),
  );
  return () => analyticsCalls;
}

describe("DashboardPage", () => {
  it("renders for staff without calling analytics", async () => {
    const calls = common("staff");
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("Dealer Dashboard")).toBeInTheDocument();
    expect(await screen.findByText("Accepted quotes")).toBeInTheDocument();
    expect(await screen.findByText("ORD-9")).toBeInTheDocument();
    expect(await screen.findByText("Q-1 · Acme")).toBeInTheDocument();
    expect(await screen.findByText(/1 need follow-up/)).toBeInTheDocument();
    expect(screen.getByText("Sales figures are visible to the owner.")).toBeInTheDocument();
    expect(screen.getByText("Product sales are visible to the owner.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Sales period")).not.toBeInTheDocument();
    expect(calls()).toBe(0);
  });

  it("renders owner sales and top products from analytics", async () => {
    const calls = common("admin");
    renderWithProviders(<DashboardPage />);
    expect(await screen.findByText("Total sales")).toBeInTheDocument();
    expect(await screen.findByText("Mono-block pump")).toBeInTheDocument();
    expect(screen.getByText("₹9,87,654")).toBeInTheDocument();
    expect(screen.getByLabelText("Sales period")).toBeInTheDocument();
    expect(screen.getByText("No orders delivered in this period yet.")).toBeInTheDocument();
    expect(calls()).toBeGreaterThan(0);
  });
});
