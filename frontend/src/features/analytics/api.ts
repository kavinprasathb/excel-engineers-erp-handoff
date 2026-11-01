import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export interface Analytics {
  from: string | null;
  to: string | null;
  conversion: {
    quoted: number;
    quoted_value_paise: number;
    pending_count: number;
    accepted_count: number;
    declined_count: number;
    pending_value_paise: number;
    accepted_value_paise: number;
    declined_value_paise: number;
    rate_all: number | null;
    rate_answered: number | null;
    reasons: { reason: string; count: number }[];
    declined: { id: number; number: string; customer: string; reason: string; value_paise: number }[];
  };
  sales: {
    orders: number;
    value_paise: number;
    average_paise: number;
    by_month: { month: string; orders: number; value_paise: number }[];
  };
  customers: {
    customer_id: number;
    customer: string;
    quotes: number;
    accepted: number;
    declined: number;
    quoted_value_paise: number;
    sales_paise: number;
    last_quote: string | null;
    rate: number | null;
    repeat: boolean;
  }[];
  products: {
    description: string;
    times_quoted: number;
    qty_quoted: number;
    value_quoted_paise: number;
    times_won: number;
    qty_won: number;
    value_won_paise: number;
    rate: number | null;
  }[];
  discount: {
    won_quotes: number;
    negotiated: number;
    first_paise: number;
    final_paise: number;
    discount_paise: number;
    discount_pct: number | null;
    rows: {
      id: number;
      number: string;
      customer: string;
      /** Versions after the original, revisions and negotiations together. */
      rounds: number;
      original_number: string;
      stage_label: string;
      revisions: number;
      negotiations: number;
      /** The revised quotation it was won on, before negotiation; null if never revised. */
      revised_paise: number | null;
      first_paise: number;
      final_paise: number;
      discount_paise: number;
      discount_pct: number | null;
    }[];
  };
  time_to_close: {
    accepted_avg_days: number | null;
    declined_avg_days: number | null;
    avg_rounds_to_win: number | null;
  };
  reorder: {
    lead_days: number;
    cover_days: number;
    window_days: number;
    count: number;
    value_paise: number;
    rows: {
      product_id: number;
      name: string;
      sku: string;
      supplier: string;
      available: number;
      on_order: number;
      sold_90_days: number;
      per_month: number;
      days_left: number | null;
      suggest: number;
      value_paise: number;
      reason: string;
      urgent: boolean;
    }[];
  };
  pipeline: {
    count: number;
    value_paise: number;
    follow_up_count: number;
    follow_up_days: number;
    rows: {
      id: number;
      number: string;
      customer: string;
      quote_date: string;
      last_change: string;
      age_days: number;
      rounds: number;
      stage_label: string;
      value_paise: number;
      follow_up: boolean;
    }[];
  };
}

export function useAnalytics(range: { from: string; to: string }, enabled = true) {
  return useQuery({
    enabled,
    meta: { silent: true },
    queryKey: ["quotations", "analytics", range.from, range.to],
    queryFn: ({ signal }) =>
      api.get<Analytics>("/analytics", { from: range.from || undefined, to: range.to || undefined }, signal),
  });
}

/** The reasons offered when declining; "Other" asks for the words. */
export const DECLINE_REASONS: readonly string[] = [
  "Price too high",
  "Lost to competitor",
  "Delivery time too long",
  "Project cancelled or on hold",
  "No response from customer",
  "Specification not matching",
];

/** Soft pastel series in fixed order (never cycled); "Other" is always light grey. */
export const SERIES = ["#8b7cf0", "#7fd3c6", "#f6c453", "#f29ac8", "#7d86e8", "#9fc5f8", "#a8dd8e"];
export const OTHER_GREY = "#d4d4d8";

/** Status in the same soft family: won, lost, still open. */
export const WON = "#6fcf97";
export const LOST = "#f29a9a";
export const OPEN = "#f6c453";

/** Same period as on screen; a plain navigation, the session cookie authenticates it. */
export function analyticsPdfUrl(range: { from: string; to: string }): string {
  const qs = new URLSearchParams();
  if (range.from) qs.set("from", range.from);
  if (range.to) qs.set("to", range.to);
  const s = qs.toString();
  return `/api/analytics/pdf${s ? `?${s}` : ""}`;
}
