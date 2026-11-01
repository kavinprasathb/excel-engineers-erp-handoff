import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type { ListParams } from "../../api/queryKeys";
import type { InventoryRow, InventorySummary, Movement, Page } from "../../api/types";

export function useInventorySummary() {
  return useQuery({
    // The cards render their own failure; a toast on top would be a duplicate.
    meta: { silent: true },
    queryKey: queryKeys.inventory.summary,
    queryFn: ({ signal }) => api.get<InventorySummary>("/inventory/summary", undefined, signal),
  });
}

export function useInventory(params: ListParams) {
  return useQuery({
    meta: { silent: true },
    queryKey: queryKeys.inventory.list(params),
    queryFn: ({ signal }) => api.get<Page<InventoryRow>>("/inventory", { ...params }, signal),
  });
}

export function useMovements(productId: number | null, page: number) {
  return useQuery({
    meta: { silent: true },
    enabled: productId !== null,
    queryKey: queryKeys.inventory.movements(productId ?? -1, page),
    queryFn: ({ signal }) =>
      api.get<Page<Movement>>(`/inventory/${productId}/movements`, { page }, signal),
  });
}

/**
 * Patches one row into every cached inventory list without a refetch.
 *
 * The rows come back complete from both `adjust` and `supplier`, so refetching
 * would only re-fetch what we are already holding — and on the supplier flow
 * it would also make the amber pill flicker back before the new name lands.
 */
function useWriteRowIntoLists() {
  const client = useQueryClient();
  return (row: InventoryRow) => {
    client.setQueriesData<Page<InventoryRow>>(
      { queryKey: [...queryKeys.inventory.all, "list"] },
      (prev) => {
        if (!prev) return prev;
        let touched = false;
        const items = prev.items.map((item) => {
          if (item.product_id !== row.product_id) return item;
          touched = true;
          return row;
        });
        // Returning the same reference when nothing matched keeps React Query
        // from re-rendering every other page of the list.
        return touched ? { ...prev, items } : prev;
      },
    );
  };
}

export interface AdjustStockVars {
  productId: number;
  /** Signed: the UI composes it from an add/remove toggle plus a positive qty. */
  delta: number;
  note: string;
}

export function useAdjustStock() {
  const client = useQueryClient();
  const writeRow = useWriteRowIntoLists();
  return useMutation({
    // `insufficient_stock` belongs inside the modal, beside the quantity that
    // caused it — not in a toast the user has already navigated away from.
    meta: { silent: true },
    mutationFn: ({ productId, delta, note }: AdjustStockVars) =>
      api.post<InventoryRow>(`/inventory/${productId}/adjust`, { delta, note }),
    onSuccess: (row) => {
      writeRow(row);
      // The counts on the cards and the movement log both changed.
      client.invalidateQueries({ queryKey: queryKeys.inventory.summary });
      client.invalidateQueries({ queryKey: [...queryKeys.inventory.all, "movements"] });
      client.invalidateQueries({ queryKey: queryKeys.products.all });
      // Added stock is held for waiting orders straight away.
      client.invalidateQueries({ queryKey: ["orders"] });
    },
  });
}

export interface SetSupplierVars {
  productId: number;
  supplierId: number | null;
}

export function useSetSupplier() {
  const client = useQueryClient();
  const writeRow = useWriteRowIntoLists();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ productId, supplierId }: SetSupplierVars) =>
      api.patch<InventoryRow>(`/inventory/${productId}/supplier`, { supplier_id: supplierId }),
    onSuccess: (row) => {
      writeRow(row);
      // missing_supplier_count is now one lower; the products list shows the
      // same relation and is stale too.
      client.invalidateQueries({ queryKey: queryKeys.inventory.summary });
      client.invalidateQueries({ queryKey: queryKeys.products.all });
    },
  });
}
