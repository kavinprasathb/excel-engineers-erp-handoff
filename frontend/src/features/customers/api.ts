import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type { ListParams } from "../../api/queryKeys";
import type { Customer, CustomerCreate, CustomerPatch, Page, Ref } from "../../api/types";

export function useCustomers(params: ListParams) {
  return useQuery({
    // The list renders its own error state, so the global toast would be a
    // second copy of the same news.
    meta: { silent: true },
    queryKey: queryKeys.customers.list(params),
    queryFn: ({ signal }) =>
      api.get<Page<Customer>>("/customers", { ...params }, signal),
  });
}

/**
 * Unpaginated and active-only, per the contract — a dropdown that silently
 * stopped at page one is how a document gets addressed to the wrong company.
 */
export function useCustomerOptions(enabled = true) {
  return useQuery({
    meta: { silent: true },
    enabled,
    queryKey: queryKeys.customers.options,
    queryFn: ({ signal }) => api.get<Ref[]>("/customers/options", undefined, signal),
    staleTime: 5 * 60_000,
  });
}

function useCustomerInvalidation() {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: queryKeys.customers.all });
  };
}

export function useCreateCustomer() {
  const invalidate = useCustomerInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: (input: CustomerCreate) => api.post<Customer>("/customers", input),
    onSuccess: invalidate,
  });
}

export function useUpdateCustomer() {
  const invalidate = useCustomerInvalidation();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ id, patch }: { id: number; patch: CustomerPatch }) =>
      api.patch<Customer>(`/customers/${id}`, patch),
    onSuccess: invalidate,
  });
}

export function useDeleteCustomer() {
  const invalidate = useCustomerInvalidation();
  return useMutation({
    // Any refusal is a message the dialog renders in place, next to the
    // button that caused it.
    meta: { silent: true },
    mutationFn: (id: number) => api.del<void>(`/customers/${id}`),
    onSuccess: invalidate,
  });
}
