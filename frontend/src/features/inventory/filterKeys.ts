import type { StockStatus, StockType } from "../../api/types";
import type { ListParamsApi } from "../../lib/useListParams";

/**
 * Which query-string keys count as "a filter" on this screen.
 *
 * Lives apart from the filter bar so the table can ask "is anything filtered?"
 * — the difference between "no products match this filter" and "no products
 * yet" — without importing a component.
 */
export const INVENTORY_FILTER_KEYS = [
  "q",
  "supplier_id",
  "category_id",
  "stock_status",
  "has_supplier",
  "stock_type",
] as const;

/**
 * The list query the table and the quick view share. Both build it from the
 * same URL, so React Query serves them from one request.
 */
export function inventoryListParams(params: ListParamsApi) {
  const hasSupplierRaw = params.get("has_supplier");
  return {
    q: params.get("q") || undefined,
    supplier_id: params.getNumber("supplier_id"),
    category_id: params.getNumber("category_id"),
    stock_status: (params.get("stock_status") || undefined) as StockStatus | undefined,
    has_supplier: hasSupplierRaw === "" ? null : hasSupplierRaw === "true",
    stock_type: (params.get("stock_type") || undefined) as StockType | undefined,
    page: params.page,
  };
}
