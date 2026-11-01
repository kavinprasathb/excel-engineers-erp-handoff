import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type { ListParams } from "../../api/queryKeys";
import type { Page, Ref, Supplier } from "../../api/types";

/** Everything on a supplier except what the server owns. */
export type SupplierInput = Omit<
  Supplier,
  "id" | "code" | "product_count" | "branches" | "missing_fields"
>;

export function useSuppliers(params: ListParams) {
  return useQuery({
    // The list renders its own error state, so the global toast would be a
    // second copy of the same news.
    meta: { silent: true },
    queryKey: queryKeys.suppliers.list(params),
    queryFn: ({ signal }) =>
      api.get<Page<Supplier>>("/suppliers", { ...params }, signal),
  });
}

/**
 * Unpaginated and active-only, per the contract — a dropdown that silently
 * stopped at page one is how a product gets tagged to the wrong supplier.
 */
export function useSupplierOptions(enabled = true) {
  return useQuery({
    meta: { silent: true },
    enabled,
    queryKey: queryKeys.suppliers.options,
    queryFn: ({ signal }) => api.get<Ref[]>("/suppliers/options", undefined, signal),
    staleTime: 5 * 60_000,
  });
}

/** Invalidating suppliers is never enough: a rename shows on inventory rows. */
function useSupplierInvalidation() {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: queryKeys.suppliers.all });
    client.invalidateQueries({ queryKey: queryKeys.products.all });
    client.invalidateQueries({ queryKey: queryKeys.inventory.all });
  };
}

export function useCreateSupplier() {
  const invalidate = useSupplierInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: (input: Partial<SupplierInput>) => api.post<Supplier>("/suppliers", input),
    onSuccess: invalidate,
  });
}

export function useUpdateSupplier() {
  const invalidate = useSupplierInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ id, patch }: { id: number; patch: Partial<SupplierInput> }) =>
      api.patch<Supplier>(`/suppliers/${id}`, patch),
    onSuccess: invalidate,
  });
}

export function useDeleteSupplier() {
  const invalidate = useSupplierInvalidation();
  return useMutation({
    // 409 "products still reference this" is a message the dialog must render
    // in place, next to the button that caused it.
    meta: { silent: true },
    mutationFn: (id: number) => api.del<void>(`/suppliers/${id}`),
    onSuccess: invalidate,
  });
}
