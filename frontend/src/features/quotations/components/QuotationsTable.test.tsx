import { describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/render";
import { QuotationsTable } from "./QuotationsTable";
import type { ListParamsApi } from "../../../lib/useListParams";
import type { QuotationSummary } from "../../../api/types";

function params(values: Record<string, string> = {}): ListParamsApi {
  return {
    get: (k) => values[k] ?? "",
    getNumber: () => null,
    set: vi.fn(),
    page: 1,
    setPage: vi.fn(),
    hasFilters: (keys) => keys.some((k) => values[k]),
    clear: vi.fn(),
  };
}

const ROW: QuotationSummary = {
  id: 1,
  number: "ESQSP-26-70",
  format: "spares",
  type: "spares",
  revision: 0,
  rev_no: 0,
  neg_no: 0,
  base_number: "ESQSP-26-70",
  stage_label: "Initial quote",
  created_at: "2026-04-20T10:00:00Z",
  customer: { id: 1, name: "Steel Authority of India Ltd." },
  quote_date: "2026-04-20",
  subject: "Offer for RNS Coupling",
  status: "pending",
  total_paise: 1476000,
  updated_at: "2026-04-20T10:00:00Z",
};

describe("QuotationsTable", () => {
  it("renders the number, status, the letter's date format and whole rupees", async () => {
    server.use(
      http.get("/api/quotations", () =>
        HttpResponse.json({ items: [ROW], total: 1, page: 1, page_size: 25, pages: 1 }),
      ),
    );
    renderWithProviders(<QuotationsTable params={params()} onOpen={vi.fn()} onCreate={vi.fn()} />);
    // DataList renders the table and the mobile cards: two copies of everything.
    expect(await screen.findAllByText("ESQSP-26-70")).toHaveLength(2);
    expect(screen.getAllByText("Pending")).toHaveLength(2);
    expect(screen.getAllByText("20.04.2026")).toHaveLength(2);
    expect(screen.getAllByText("₹14,760")).toHaveLength(2);
  });

  it("drops a junk status from the URL instead of sending it", async () => {
    let sent: string | null = null;
    server.use(
      http.get("/api/quotations", ({ request }) => {
        sent = new URL(request.url).searchParams.get("status");
        return HttpResponse.json({ items: [], total: 0, page: 1, page_size: 25, pages: 0 });
      }),
    );
    renderWithProviders(
      <QuotationsTable params={params({ status: "junk" })} onOpen={vi.fn()} onCreate={vi.fn()} />,
    );
    expect(await screen.findByText(/nothing matches this filter/i)).toBeInTheDocument();
    expect(sent).toBeNull();
  });
});
