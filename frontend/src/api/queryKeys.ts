/**
 * Every query key in one place, so an invalidation after a mutation can be
 * written against a prefix instead of a guessed literal array.
 */

import type { QuotationStage, StockStatus } from "./types";

export interface ListParams {
  q?: string;
  page?: number;
  page_size?: number;
  sort?: string;
  supplier_id?: number | null;
  category_id?: number | null;
  is_active?: boolean | null;
  has_supplier?: boolean | null;
  stock_status?: StockStatus;
  type?: string;
  status?: string;
  customer_id?: number | null;
  negotiated?: boolean;
  /** Quotations by the kind of their latest version. */
  stage?: QuotationStage;
}

export const queryKeys = {
  me: ["me"] as const,
  health: ["health"] as const,

  settings: ["settings"] as const,

  suppliers: {
    all: ["suppliers"] as const,
    list: (params: ListParams) => ["suppliers", "list", params] as const,
    options: ["suppliers", "options"] as const,
    detail: (id: number) => ["suppliers", "detail", id] as const,
  },

  categories: {
    all: ["categories"] as const,
    list: ["categories", "list"] as const,
  },

  products: {
    all: ["products"] as const,
    list: (params: ListParams) => ["products", "list", params] as const,
    detail: (id: number) => ["products", "detail", id] as const,
    movements: (id: number, page: number) => ["products", "movements", id, page] as const,
  },

  inventory: {
    all: ["inventory"] as const,
    list: (params: ListParams) => ["inventory", "list", params] as const,
    summary: ["inventory", "summary"] as const,
    movements: (productId: number, page: number) =>
      ["inventory", "movements", productId, page] as const,
  },

  customers: {
    all: ["customers"] as const,
    list: (params: ListParams) => ["customers", "list", params] as const,
    options: ["customers", "options"] as const,
    detail: (id: number) => ["customers", "detail", id] as const,
  },

  quotations: {
    all: ["quotations"] as const,
    list: (params: ListParams) => ["quotations", "list", params] as const,
    detail: (id: number) => ["quotations", "detail", id] as const,
    revisions: (id: number) => ["quotations", "revisions", id] as const,
    changes: (id: number) => ["quotations", "changes", id] as const,
    lineChanges: (id: number) => ["quotations", "line-changes", id] as const,
    compare: (id: number, against: number) => ["quotations", "compare", id, against] as const,
    dashboard: ["quotations", "dashboard"] as const,
  },

  // Keyed by the search term because a type-ahead re-queries per keystroke
  // (debounced); a single key would make each result evict the last.
  productLookup: (q: string) => ["products", "lookup", q] as const,
  itemSuggestions: (q: string, customerId: number | null) =>
    ["quotations", "item-suggestions", q, customerId] as const,

  imports: {
    all: ["imports"] as const,
    list: (page: number) => ["imports", "list", page] as const,
    detail: (id: string) => ["imports", "detail", id] as const,
  },
} as const;
